"""Hardware-aware choices from supported packages, with no automatic model activation."""
import asyncio,concurrent.futures,math,pathlib,shutil,threading,time
from aiohttp import web
from bootstrap import ROOT,read,write
from platform_support import hardware,native_binary
from hf_access import access
from cloud_vault import account_options

GIB=1024**3
TASKS=('code','chat','image','video')
LABELS={'huihui-qwen38-coder':'Huihui Qwen 3.8 · Coder 27B','qwen35-4b':'Qwen 3.5 · 4B',
        'qwen35-08b':'Qwen 3.5 · 0.8B','qwen-image21':'Qwen Image 2.1 Turbo','wan21-t2v-13b':'Wan 2.1 · Video 1.3B'}

def disk_at(folder):
    folder=pathlib.Path(folder)
    while not folder.exists() and folder!=folder.parent:folder=folder.parent
    return shutil.disk_usage(folder).free

class ModelAdvisor:
    def __init__(self,library):
        self.library=library;self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future=None;self.lock=threading.Lock();self.state=read(ROOT/'data/model-advisor.json',{'state':'idle'})
        if self.state.get('state')=='checking':self.state['state']='idle'

    def start(self):
        with self.lock:
            if self.future and not self.future.done():return self.snapshot()
            self.state={**self.state,'state':'checking','error':None}
            self.future=self.pool.submit(self.scan)
        return self.snapshot()

    def scan(self):
        try:
            device=hardware(ROOT);self.library.device=device;write(ROOT/'data/hardware.json',device)
            engines={};preferred='metal' if device.get('metal') else 'cuda' if device.get('cuda') else 'vulkan' if device.get('vulkan') else 'cpu'
            for kind in ('llama','sd'):
                for backend in dict.fromkeys([preferred,'vulkan' if device.get('cuda') else preferred,'cpu']):
                    try:native_binary(ROOT,kind,backend);engines[kind]=backend;break
                    except (FileNotFoundError,OSError):continue
            self.state={'state':'complete','checked_at':time.time(),'hardware':device,'engines':engines}
            write(ROOT/'data/model-advisor.json',self.state)
        except Exception:self.state={**self.state,'state':'error','error':'Не удалось проверить ПК. Повторите проверку.'}

    def choices(self,task):
        device=self.state.get('hardware') or self.library.device
        engines=self.state.get('engines',{})
        ram=device.get('ram_gb',0);vram=device.get('vram_gb',0)
        accelerated=device.get('gpu_accelerated',device.get('cuda',False))
        rows=[]
        for item in list(self.library.catalog):
            if item['kind']!=('chat' if task in ('code','chat') else task):continue
            folder=self.library.folder(item);installed=self.library.ready(item)
            total=sum(f['bytes'] for f in item['files']);remaining=0
            for file in item['files']:
                final=folder/file['name'];part=folder/(file['name']+'.part')
                if installed or final.is_file() and final.stat().st_size==file['bytes']:continue
                remaining+=max(0,file['bytes']-(part.stat().st_size if part.is_file() else 0))
            free=disk_at(folder);need_disk=remaining+(0 if installed else 2*GIB)
            need_ram=item.get('recommended_ram_gb',max(8,math.ceil(total/GIB)+5))
            need_vram=item.get('recommended_vram_gb',math.ceil(total/GIB)+4)
            engine=engines.get('llama' if item['kind']=='chat' else 'sd')
            # Snapshot RAM/VRAM are separate limits. Unified memory is never added to RAM.
            reasons=[];level='recommended'
            if ram<need_ram:level='limited';reasons.append('Недостаточно RAM для выбранного комплекта.')
            if not installed and free<need_disk:level='limited';reasons.append('Недостаточно свободного места на диске моделей.')
            if not engine and self.state.get('state')=='complete':level='limited';reasons.append('Совместимый движок отсутствует в этой сборке.')
            if not accelerated or vram<need_vram-.1:
                if item['kind']=='chat':
                    if level!='limited':level='cpu'
                    reasons.append('Часть вычислений будет в RAM или на CPU. Генерация будет медленнее.')
                else:level='limited';reasons.append('Недостаточно памяти совместимого GPU для этого генератора.')
            if not reasons:reasons.append('Подходит по RAM, памяти GPU и доступному месту.')
            score={"recommended":300,"cpu":150,"limited":0}[level]
            # Prefer the installed specialist for code; 4B balances latency and quality for chat.
            score+=({'huihui-qwen38-coder':50,'qwen35-4b':30,'qwen35-08b':10} if task=='code' else
                    {'qwen35-4b':50,'huihui-qwen38-coder':35,'qwen35-08b':10}).get(item['id'],20)
            if level=='cpu':
                # On CPU/RAM favour the smaller everyday model over a 27B download.
                score+=10 if item['id']=='qwen35-4b' else -35 if item['id']=='huihui-qwen38-coder' else 0
            rows.append({'id':item['id'],'name':LABELS.get(item['id'],item['name']),'kind':item['kind'],'task':task,'installed':installed,
                'fit':level,'reasons':reasons,'score':score,'total':total,'remaining':remaining,'free_disk':free,'disk_required':need_disk,
                'needs_ram':need_ram,'needs_vram':need_vram,'context':item.get('context'),'source':item['source'],'license':str(item.get('license','')),
                'folder':str(folder),'job':self.library.jobs.get(item['id']) or {},'can_download':level!='limited' and not installed,
                'note':('Для сложного кода; больше памяти и времени на обработку контекста.' if item['id']=='huihui-qwen38-coder' else
                        'Быстрый повседневный помощник; меньше запас для сложных задач.' if item['id']=='qwen35-4b' else
                        'Самый лёгкий вариант; сложный код требует тщательной проверки.' if item['id']=='qwen35-08b' else
                        'Модель GGUF для чата и кода. После загрузки нужна проверка работы.' if item['kind']=='chat' else
                        'Генерация изображений. Модели кода и генерации используют GPU по очереди.' if item['kind']=='image' else
                        'Короткие ролики 480p. Время зависит от числа кадров и GPU.')})
        rows.sort(key=lambda row:row['score'],reverse=True)
        for i,row in enumerate(rows):row['best']=i==0 and row['fit']!='limited'
        return rows

    def snapshot(self):
        device=self.state.get('hardware') or self.library.device
        return {**self.state,'hardware':device,'recommendations':{task:self.choices(task) for task in TASKS},'huggingface':access.status(),
                'estimate_only':True,'system_changes':False}

    def register(self,app):
        async def status(request):return web.json_response(self.snapshot())
        async def scan(request):return web.json_response(self.start())
        async def connect(request):
            data=await request.json();options=account_options(data,token_required=True)
            return web.json_response(await asyncio.to_thread(access.check,data['token'],**options))
        async def check(request):return web.json_response(await asyncio.to_thread(access.check))
        async def disconnect(request):return web.json_response(access.disconnect())
        app.router.add_get('/api/advisor',status);app.router.add_post('/api/advisor/scan',scan)
        app.router.add_post('/api/advisor/huggingface/connect',connect);app.router.add_post('/api/advisor/huggingface/check',check)
        app.router.add_post('/api/advisor/huggingface/disconnect',disconnect)
