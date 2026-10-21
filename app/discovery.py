"""Public model search. Metadata only; model repositories never execute code."""
import concurrent.futures,hashlib,io,json,math,re,struct,time,urllib.parse
from html.parser import HTMLParser
import requests
from hf_access import access as hf_access
from bootstrap import ROOT,read,write

GIB=1024**3
HF='https://huggingface.co'
REGISTRY='https://registry.ollama.ai/v2/library/'
ARCHITECTURES={'llama','qwen2','qwen2moe','qwen3','qwen3moe','qwen35','qwen35moe','gemma','gemma2','gemma3','phi3','mistral','deepseek2','gpt-oss'}

def remote(url,params=None):
    response=requests.get(url,params=params,headers=hf_access.headers(url,{'Accept':'application/json'}),timeout=(8,20))
    response.raise_for_status()
    if len(response.content)>8*1024**2:raise ValueError('Ответ каталога слишком большой.')
    return response.json()

def fit(size,device,*,kind='chat',ram=None,vram=None,installed=False):
    # The chat engine uses 65,536 tokens. Reserve memory for q8 KV, graphs and the
    # desktop, instead of treating the GGUF weight size as the full GPU footprint.
    weight=size/GIB;need_ram=ram or max(8,math.ceil(weight+5));need_vram=vram or math.ceil(weight+(4 if kind=='chat' else 2))
    disk=device.get('free_disk_gb',0);available_ram=device.get('ram_gb',0);gpu=device.get('vram_gb',0)
    if not installed and disk<weight+2:return {'level':'limited','rank':0,'reason':'Недостаточно места для модели и запаса.'}
    if available_ram<need_ram:return {'level':'limited','rank':1,'reason':f'Рекомендуется от {need_ram} ГБ RAM. На этом ПК модель может не поместиться.'}
    if device.get('gpu_accelerated',device.get('cuda')) and gpu>=need_vram-.1:return {'level':'recommended','rank':3,'reason':'Подходит по памяти. Скорость и работа инструментов проверяются после загрузки.'}
    if kind!='chat':return {'level':'limited','rank':1,'reason':f'Для этого режима рекомендуется совместимый GPU от {need_vram} ГБ памяти.'}
    return {'level':'cpu','rank':2,'reason':'Возможна работа с RAM или частичной загрузкой в GPU; скорость ниже.'}

def repo_name(value):
    value=str(value).strip().removeprefix(HF+'/').strip('/')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value):raise ValueError('Нужен репозиторий owner/name.')
    return value

def hf_candidates(repo,device):
    meta=remote(HF+'/api/models/'+repo_name(repo),{'blobs':'true'})
    gguf=meta.get('gguf') or {};architecture=gguf.get('architecture');context=gguf.get('context_length') or 0
    if not isinstance(context,int):context=0
    files=[]
    for file in meta.get('siblings',[]):
        name=file['rfilename'];lfs=file.get('lfs') or {};size=file.get('size') or lfs.get('size');sha=lfs.get('sha256')
        basename=name.rsplit('/',1)[-1].lower()
        if basename.endswith('.imatrix.gguf') or re.match(r'imatrix[_.-]',basename):continue
        if not name.endswith('.gguf') or any(s in name.lower() for s in ['mmproj','-of-','encoder','embedding','vae']) or re.match(r'(mtp|draft|dflash)[-_]',name.rsplit('/',1)[-1],re.I):continue
        if not isinstance(size,int) or not re.fullmatch(r'[a-f0-9]{64}',sha or ''):continue
        assessment=fit(size,device)
        compatible=architecture in ARCHITECTURES and context>=64000
        files.append({'key':repo+'/'+name,'provider':'huggingface','repo':repo,'filename':name,'name':name.rsplit('/',1)[-1],
            'bytes':size,'sha256':sha,'revision':meta['sha'],'source':HF+'/'+repo,'license':meta.get('cardData',{}).get('license','see model card'),
            'architecture':architecture,'context':context,'compatibility':'supported_family' if compatible else 'review',
            'compatibility_note':'Семейство поддерживается; GGUF и загрузка проверяются при установке.' if compatible else 'Совместимость с движком или контекстом 64К не подтверждена.',
            'recommendation':assessment,'can_add':compatible})
    # Prefer usable quantizations, then the best precision that fits the memory budget.
    preferred=lambda f: bool(re.search(r'(Q[4568]_K|Q8_0|IQ[34]|Q4_0)',f['name'],re.I))
    files.sort(key=lambda f:(f['recommendation']['rank'],f['can_add'],preferred(f),f['bytes']),reverse=True)
    return files[:2]

class OllamaLinks(HTMLParser):
    def __init__(self):super().__init__();self.models=[]
    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        value=dict(attrs).get('href','')
        match=re.fullmatch(r'/library/([a-z0-9][a-z0-9._-]*)',value)
        if match and match[1] not in self.models:self.models.append(match[1])

def ollama_manifest(name,tag):
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*',name) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}',tag):raise ValueError('Неверное имя Ollama.')
    meta=remote(REGISTRY+name+'/manifests/'+tag)
    layer=next((f for f in meta.get('layers',[]) if f.get('mediaType')=='application/vnd.ollama.image.model'),None)
    if not layer or not re.fullmatch(r'sha256:[a-f0-9]{64}',layer.get('digest','')) or not isinstance(layer.get('size'),int):raise ValueError('В реестре нет самостоятельного файла модели.')
    return layer

def registry_header(name,layer):
    # Bounded GGUF metadata only, no full model download for the discovery step.
    with requests.get(REGISTRY+name+'/blobs/'+layer['digest'],headers={'Range':'bytes=0-131071'},stream=True,timeout=(8,15)) as response:
        response.raise_for_status();prefix=response.raw.read(131072)
    stream=io.BytesIO(prefix)
    def number(fmt):
        size=struct.calcsize(fmt);value=stream.read(size)
        if len(value)!=size:raise ValueError('Incomplete GGUF header')
        return struct.unpack('<'+fmt,value)[0]
    def string():
        size=number('Q')
        if size>131072:raise ValueError('GGUF field exceeds prefix')
        data=stream.read(size)
        if len(data)!=size:raise ValueError('Incomplete GGUF field')
        return data.decode('utf8','replace')
    if stream.read(4)!=b'GGUF' or number('I') not in {2,3}:raise ValueError('Registry layer is not GGUF')
    number('Q');count=number('Q');architecture=None;context=0
    formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
    for _ in range(min(count,10000)):
        key=string();kind=number('I');value=None
        if kind in formats:value=number(formats[kind])
        elif kind==8:value=string()
        elif kind==9:
            sub,n=number('I'),number('Q')
            if n>1000000:raise ValueError('Large GGUF array')
            if sub in formats:stream.seek(struct.calcsize(formats[sub])*n,1)
            elif sub==8:
                for _ in range(n):string()
            else:raise ValueError('Unknown GGUF array')
        else:raise ValueError('Unknown GGUF field')
        if key=='general.architecture':architecture=value
        if key.endswith('.context_length') and isinstance(value,int):context=value
        if architecture and context:return architecture,context
    raise ValueError('GGUF architecture/context not found in prefix')

def ollama_candidates(query,device):
    response=requests.get('https://ollama.com/search',params={'q':query},timeout=(8,15));response.raise_for_status()
    if len(response.content)>4*1024**2:raise ValueError('Ответ каталога слишком большой.')
    parser=OllamaLinks();parser.feed(response.text)
    result=[]
    for name in parser.models[:4]:
        try:
            layer=ollama_manifest(name,'latest');size=layer['size'];architecture=None;context=0
            try:architecture,context=registry_header(name,layer)
            except Exception:pass
            compatible=architecture in ARCHITECTURES and context>=64000
            result.append({'key':'ollama:'+name+':latest','provider':'ollama','repo':name,'filename':'latest','name':name+':latest','bytes':size,
                'sha256':layer['digest'][7:],'source':'https://ollama.com/library/'+name,'license':'see model card','context':context,'architecture':architecture,
                'recommendation':fit(size,device),'compatibility':'supported_family' if compatible else 'review','compatibility_note':'Семейство поддерживается; GGUF и загрузка проверяются при установке.' if compatible else 'Совместимость с движком или контекстом 64К не подтверждена.',
                'can_add':compatible})
        except Exception:continue
    return result

class Discovery:
    def __init__(self,library):self.library=library;self.state={'state':'idle','results':[],'errors':[]};self.future=None
    def start(self,query='',provider='all',task='chat'):
        query=str(query).strip()[:100]
        if provider not in {'all','huggingface','ollama'} or task not in {'chat','code','image','video'}:raise ValueError('Неизвестный фильтр поиска.')
        if self.future and not self.future.done():return dict(self.state)
        self.state={'state':'searching','query':query,'provider':provider,'task':task,'results':[],'errors':[],'started_at':time.time()}
        self.future=self.library.pool.submit(self._search,query,provider,task)
        return dict(self.state)
    def _search(self,query,provider,task):
        key=hashlib.sha256(json.dumps([query,provider,task]).encode()).hexdigest()[:24];cache=ROOT/'.cache/model-search'/(key+'.json')
        rows=[];errors=[]
        try:
            device=self.library.device
            if task in {'image','video'}:
                # Multi-component diffusion models need an explicit tested adapter, not an arbitrary GGUF.
                rows=[{**m,'key':m['id'],'provider':'catalog','can_add':False,'catalog_id':m['id'],'bytes':sum(f['bytes'] for f in m['files']),
                    'recommendation':fit(sum(f['bytes'] for f in m['files']),device,kind=task,ram=m['recommended_ram_gb'],vram=m['recommended_vram_gb'],installed=self.library.ready(m))}
                    for m in self.library.catalog if m['kind']==task and (not query or query.lower() in m['name'].lower())]
            else:
                search=query or ('Qwen3-Coder' if task=='code' else 'Qwen3.5')
                if provider in {'all','huggingface'}:
                    try:
                        repos=remote(HF+'/api/models',{'search':search,'filter':'gguf','sort':'downloads','direction':-1,'limit':6})
                        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                            futures=[pool.submit(hf_candidates,m['id'],device) for m in repos if isinstance(m,dict) and m.get('id')]
                            for future in futures:
                                try:rows.extend(future.result())
                                except Exception as exc:errors.append('Hugging Face: '+type(exc).__name__)
                    except Exception as exc:errors.append('Hugging Face: '+type(exc).__name__)
                if provider in {'all','ollama'}:
                    try:rows.extend(ollama_candidates(query or ('qwen coder' if task=='code' else 'qwen'),device))
                    except Exception as exc:errors.append('Ollama: '+type(exc).__name__)
            rows.sort(key=lambda m:(m['recommendation'].get('rank',0),m.get('can_add',True)),reverse=True)
            if errors and not rows:raise ValueError('; '.join(errors))
            result={**self.state,'state':'complete','results':rows,'errors':errors,'offline':False,'checked_at':time.time()}
            write(cache,result);self.state=result
        except Exception as exc:
            saved=read(cache,{})
            self.state={**self.state,**saved,'state':'complete' if saved else 'error','offline':True,'errors':[str(exc)],'query':query,'provider':provider,'task':task}
    def snapshot(self):
        state=dict(self.state);state['results']=[dict(m,recommendation=fit(m['bytes'],self.library.device,kind=m.get('kind','chat'),ram=m.get('recommended_ram_gb'),vram=m.get('recommended_vram_gb'))) for m in state.get('results',[])]
        return state
    def add(self,key):
        row=next((m for m in self.state.get('results',[]) if m['key']==key),None)
        if not row or not row.get('can_add'):raise ValueError('Выберите доступную модель из результатов поиска.')
        if row['provider']=='huggingface':return self.library.add_hf(row['repo'],row['filename'])
        layer=ollama_manifest(row['repo'],row['filename']);sha=layer['digest'][7:];ident='ollama-'+sha[:16]
        if self.library.model(ident):return self.library.model(ident)
        size=layer['size'];item={'id':ident,'name':row['name'],'kind':'chat','quantization':'Ollama · проверка GGUF при загрузке','context':65536,
            'source':row['source'],'license':row['license'],'recommended_ram_gb':max(8,math.ceil(size/GIB)+5),'recommended_vram_gb':math.ceil(size/GIB)+2,
            'files':[{'name':'model.gguf','bytes':size,'sha256':sha,'url':REGISTRY+row['repo']+'/blobs/'+layer['digest']}]}
        self.library.catalog.append(item);self.library.save_custom();return item
