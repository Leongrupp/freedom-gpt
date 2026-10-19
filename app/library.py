"""Local hardware assessment, verified resumable downloads and owned model processes."""
import asyncio,concurrent.futures,hashlib,json,math,os,pathlib,shutil,subprocess,sys,threading,time,urllib.parse,uuid
import psutil,requests
from aiohttp import web
from bootstrap import ROOT,STACK,HOME,config,read,write,write_hermes
sys.path.insert(0,str(STACK/'creative-kit'))
from gpu_lease import active as image_job_active
GIB=1024**3

def hardware():
 memory=psutil.virtual_memory();gpus=[];cpu='';notes=[]
 try:
  raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'],text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
  for line in raw.strip().splitlines():
   name,total,free,driver=[p.strip() for p in line.split(',')];gpus.append({'name':name,'vram_gb':round(float(total)/1024,1),'free_gb':round(float(free)/1024,1),'driver':driver,'cuda':True})
 except Exception:notes.append('CUDA не обнаружена. Доступен CPU; скорость генерации будет ниже.')
 try:
  script="[pscustomobject]@{cpu=(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name);gpu=@(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)} | ConvertTo-Json -Compress"
  info=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-Command',script],text=True,encoding='utf8',errors='replace',timeout=15,creationflags=subprocess.CREATE_NO_WINDOW));cpu=info['cpu']
  if not gpus:gpus=[{'name':name,'vram_gb':None,'cuda':False} for name in info.get('gpu',[])]
 except Exception:cpu=os.environ.get('PROCESSOR_IDENTIFIER','CPU')
 return {'cpu':cpu,'physical_cores':psutil.cpu_count(logical=False),'threads':psutil.cpu_count(),
         'ram_gb':math.ceil(memory.total/GIB),'ram_available_gb':round(memory.available/GIB,1),'gpus':gpus,
         'vram_gb':max((g.get('vram_gb') or 0 for g in gpus),default=0),'cuda':any(g.get('cuda') for g in gpus),
         'free_disk_gb':round(shutil.disk_usage(ROOT).free/GIB,1),'notes':notes,'storage':str(ROOT),'estimate_only':True}
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as source:
  for block in iter(lambda:source.read(4*1024**2),b''):h.update(block)
 return h.hexdigest()
class Library:
 def __init__(self):
  self.catalog=read(ROOT/'catalog.json',[])+read(ROOT/'data/custom-models.json',[])
  self.device=read(ROOT/'data/hardware.json',{})
  self.jobs={};self.cancel={};self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
  self.transition=threading.Lock();self.activation=None
 def model(self,ident):
  return next((item for item in self.catalog if item['id']==ident),None)
 def folder(self,item):return STACK/'creative-kit/models' if item['kind']=='image' else STACK/'models'/item['id']
 def ready(self,item):
  verified=read(self.folder(item)/'.verified.json',{})
  return all((self.folder(item)/f['name']).is_file() and (self.folder(item)/f['name']).stat().st_size==f['bytes'] and verified.get(f['name'],{}).get('sha256')==f['sha256'] and verified.get(f['name'],{}).get('mtime_ns')==(self.folder(item)/f['name']).stat().st_mtime_ns for f in item['files'])
 def recommendation(self,item):
  h=self.device;ram=h.get('ram_gb',0);vram=h.get('vram_gb',0);need=item.get('recommended_ram_gb',16)
  if ram<need:return {'level':'limited','reason':f'Рекомендуется от {need} ГБ RAM. На этом ПК модель может не поместиться.'}
  if vram>=item.get('recommended_vram_gb',8)-.1:return {'level':'recommended','reason':'Подходит по объёму RAM и VRAM. Оценка скорости зависит от видеокарты и контекста.'}
  if item['kind']=='image':return {'level':'limited','reason':'Для этой сборки генератора рекомендуется NVIDIA с 12 ГБ VRAM. Работа на CPU значительно медленнее.'}
  return {'level':'cpu','reason':'Возможна частичная загрузка на GPU или работа на CPU. Скорость будет ниже.'}
 def snapshot(self):
  rows=[]
  for item in self.catalog:
   folder=self.folder(item);total=sum(f['bytes'] for f in item['files']);done=sum(min(f['bytes'],(folder/f['name']).stat().st_size if (folder/f['name']).exists() else (folder/(f['name']+'.part')).stat().st_size if (folder/(f['name']+'.part')).exists() else 0) for f in item['files'])
   rows.append({**item,'installed':self.ready(item),'bytes':done,'total':total,'percent':round(done/total*100,1) if total else 0,'recommendation':self.recommendation(item),'job':self.jobs.get(item['id'])})
  selected='huihui-qwen38-coder' if self.device.get('vram_gb',0)>=15.9 and self.device.get('ram_gb',0)>=31 else 'qwen35-4b' if self.device.get('ram_gb',0)>=12 else 'qwen35-08b'
  return {'hardware':self.device,'models':rows,'active':config().get('active'),'external_model':config().get('external_model'),'recommended':selected,'activation':self.activation,'first_run':not config().get('onboarded'),'root':str(ROOT),'license_notice':'Лицензии и источники указаны у каждой модели. Модели загружаются отдельно от приложения.'}
 def scan(self):
  self.device=hardware();write(ROOT/'data/hardware.json',self.device);return self.snapshot()
 def download(self,ident):
  item=self.model(ident)
  if not item:raise ValueError('Модель не найдена.')
  if self.jobs.get(ident,{}).get('state') in ['downloading','verifying']:return
  missing=sum(max(0,f['bytes']-((self.folder(item)/(f['name']+'.part')).stat().st_size if (self.folder(item)/(f['name']+'.part')).exists() else f['bytes'] if (self.folder(item)/f['name']).exists() else 0)) for f in item['files'])
  if shutil.disk_usage(ROOT).free<missing+2*GIB:raise ValueError('Недостаточно места. Для загрузки и запаса нужно '+str(round((missing+2*GIB)/GIB,1))+' ГБ.')
  self.cancel[ident]=threading.Event();self.jobs[ident]={'state':'downloading','speed':0};self.pool.submit(self._download,item)
 def _download(self,item):
  ident=item['id'];folder=self.folder(item);folder.mkdir(parents=True,exist_ok=True);verified=read(folder/'.verified.json',{})
  try:
   for f in item['files']:
    final=folder/f['name'];part=folder/(f['name']+'.part')
    if final.exists() and final.stat().st_size==f['bytes'] and digest(final)==f['sha256']:
     verified[f['name']]={'sha256':f['sha256'],'mtime_ns':final.stat().st_mtime_ns};continue
    if final.exists():raise ValueError('Файл с таким именем уже существует и не прошёл проверку. Он сохранён; выберите новую папку модели.')
    for attempt in range(5):
     if self.cancel[ident].is_set():raise InterruptedError()
     start=part.stat().st_size if part.exists() else 0
     if start==f['bytes']:break
     try:
      with requests.get(f['url'],headers={'Range':f'bytes={start}-','User-Agent':'FreedomGPT/1.1'},stream=True,timeout=(20,35)) as response:
       response.raise_for_status()
       if start and response.status_code!=206:raise ValueError('Сервер не поддержал продолжение. Частичный файл сохранён.')
       if response.status_code==206 and not response.headers.get('Content-Range','').startswith(f'bytes {start}-'):raise ValueError('Неверный диапазон ответа.')
       last=time.monotonic();count=0
       with part.open('ab') as stream:
        for block in response.iter_content(64*1024):
         if self.cancel[ident].is_set():raise InterruptedError()
         if not block:continue
         if stream.tell()+len(block)>f['bytes']:raise ValueError('Размер файла превысил размер издателя.')
         stream.write(block);count+=len(block)
         if time.monotonic()-last>1:self.jobs[ident].update(speed=round(count/(time.monotonic()-last)));last=time.monotonic();count=0
      if part.stat().st_size!=f['bytes']:raise IOError('Загрузка прервалась; файл сохранён для продолжения.')
      break
     except (requests.RequestException,IOError):
      if attempt==4:raise
      if self.cancel[ident].wait(min(10,2+attempt)):raise InterruptedError()
    self.jobs[ident]['state']='verifying'
    if part.stat().st_size!=f['bytes'] or digest(part)!=f['sha256']:raise ValueError('SHA256 не совпал. Частичный файл сохранён; запуск запрещён.')
    if item['kind']=='chat':
     from gguf_info import model_context
     model_context(part)
    os.replace(part,final);verified[f['name']]={'sha256':f['sha256'],'mtime_ns':final.stat().st_mtime_ns};write(folder/'.verified.json',verified);self.jobs[ident]['state']='downloading'
   write(folder/'.verified.json',verified)
   if item['kind']=='image':write(STACK/'creative-kit/manifest.json',[{'path':str(folder/f['name']),**f} for f in item['files']])
   self.jobs[ident]={'state':'complete','speed':0}
  except InterruptedError:self.jobs[ident]={'state':'paused','speed':0}
  except Exception as exc:self.jobs[ident]={'state':'error','error':str(exc),'speed':0}
 def stop_model(self):
  import bootstrap
  if bootstrap.PRIVATE:return
  marker=STACK/'.tmp/stop-server';marker.touch();record=read(STACK/'.tmp/supervisor-process.json',{})
  try:
   process=psutil.Process(record['pid'])
   if abs(process.create_time()-record['created'])>1 or str(ROOT/'engine_supervisor.py').lower() not in ' '.join(process.cmdline()).lower():raise ValueError('Не удалось подтвердить владельца процесса модели.')
   try:process.wait(timeout=8)
   except psutil.TimeoutExpired:
    children=process.children();process.terminate()
    for child in children:
     if child.name().lower()=='llama-server.exe':child.terminate()
  except (KeyError,psutil.NoSuchProcess):pass
 def engine_config(self,item):
  device=hardware();self.device=device;vram=max((g.get('free_gb') or 0 for g in device.get('gpus',[]) if g.get('cuda')),default=0);weight=sum(f['bytes'] for f in item['files'] if f['name']=='model.gguf')/GIB
  context=65536
  ngl='all' if device.get('cuda') and vram>=weight+2 else str(max(0,int(24*max(0,vram-2)/max(weight,1)))) if device.get('cuda') else '0'
  required_ram=4 if ngl=='all' else max(0,weight-max(0,vram-2))+4
  if device.get('ram_available_gb',0)<required_ram:raise ValueError('Недостаточно свободной RAM для этого режима: нужно примерно '+str(round(required_ram,1))+' ГБ. Закройте другие модели/тяжёлые приложения или выберите более лёгкую модель.')
  return {'model':str(self.folder(item)/'model.gguf'),'mmproj':str(self.folder(item)/'mmproj.gguf') if any(f['name']=='mmproj.gguf' for f in item['files']) else None,
          'context':context,'port':config()['model_port'],'alias':'freedom-local','threads':max(1,min(16,device.get('physical_cores') or 4)),
          'ngl':ngl,'mtp':bool(item.get('mtp') and ngl=='all'),'kv_cache':'q8_0'}
 def start_model(self,item):
  cfg=self.engine_config(item);write(STACK/'server-settings.json',cfg);write_hermes(cfg['context'])
  (STACK/'.tmp/stop-server').unlink(missing_ok=True)
  with (ROOT/'logs/model-supervisor.log').open('ab') as log:
   process=subprocess.Popen([sys.executable,'-s',str(ROOT/'engine_supervisor.py')],cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
  write(STACK/'.tmp/supervisor-process.json',{'pid':process.pid,'created':psutil.Process(process.pid).create_time()})
 def activate(self,ident):
  import bootstrap
  if bootstrap.PRIVATE:
   if ident=='huihui-qwen38-coder':
    bootstrap.ensure_private_model();self.activation={'id':ident,'state':'ready'};return {'ok':True}
   raise ValueError('Эта личная установка сохраняет текущий сервер модели. Другую модель можно подключить через локальный API.')
  if image_job_active():raise ValueError('Дождитесь завершения генерации изображения перед переключением модели.')
  if self.activation and self.activation.get('state')=='loading':raise ValueError('Дождитесь загрузки предыдущей модели.')
  item=self.model(ident)
  if not item or item['kind']!='chat' or not self.ready(item):raise ValueError('Сначала полностью загрузите и проверьте модель.')
  if self.device.get('ram_gb',0)<item.get('recommended_ram_gb',8):raise ValueError('Для этой модели недостаточно RAM. Выберите более лёгкую модель.')
  self.activation={'id':ident,'state':'loading'};self.pool.submit(self._activate,item)
 def _activate(self,item):
  with self.transition:
   before=config();old=before.get('active')
   try:
    try:
     slots=requests.get(f"http://127.0.0.1:{config()['model_port']}/slots",timeout=2).json()
     if any(s.get('is_processing') for s in slots):raise ValueError('Модель выполняет задачу. Остановите ответ перед переключением.')
    except requests.RequestException:pass
    self.stop_model();own=config();own.pop('external_url',None);own.pop('external_model',None);own.pop('external_context',None);write(ROOT/'data/settings.json',own);self.start_model(item)
    for _ in range(240):
     try:
      if requests.get(f"http://127.0.0.1:{config()['model_port']}/health",timeout=1).json().get('status')=='ok':break
     except requests.RequestException:pass
     time.sleep(1)
    else:raise ValueError('Модель не загрузилась. Подробности в stack/logs; прежняя модель будет восстановлена.')
    cfg=config();cfg.update(active=item['id'],onboarded=True);write(ROOT/'data/settings.json',cfg);self.activation={'id':item['id'],'state':'ready'}
   except Exception as exc:
    self.activation={'id':item['id'],'state':'error','error':str(exc)}
    try:
     self.stop_model();write(ROOT/'data/settings.json',before);write_hermes()
     if old and self.model(old) and self.ready(self.model(old)):self.start_model(self.model(old))
    except Exception:pass
 def connect_local(self,url,model,context=65536):
  parsed=urllib.parse.urlsplit(url)
  if parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Разрешён только локальный HTTP API без логина и пароля, например http://127.0.0.1:1234/v1.')
  base=url.rstrip('/')
  response=requests.get(base+'/models',timeout=8);response.raise_for_status();names=[m['id'] for m in response.json().get('data',[])]
  if model not in names:raise ValueError('Модель не найдена. Доступные идентификаторы: '+', '.join(names[:15]))
  context=int(context)
  try:
   slots=requests.get(base.removesuffix('/v1')+'/slots',timeout=3).json()
   if isinstance(slots,list) and slots:context=min(int(s['n_ctx']) for s in slots)
  except (requests.RequestException,ValueError,KeyError,TypeError):pass
  if context<64000:raise ValueError('Freedom GPT требует контекст не менее 64 000 токенов. Увеличьте контекст локального сервера или выберите другую модель.')
  self.stop_model();cfg=config();cfg.update(external_url=base,external_model=model,external_context=context,active=None,onboarded=True);write(ROOT/'data/settings.json',cfg);write_hermes(context);return {'ok':True,'context':context}
 def import_local(self,path,name=None):
  source=pathlib.Path(path).resolve()
  if not source.is_file() or source.suffix.lower()!='.gguf':raise ValueError('Выберите существующий файл GGUF.')
  with source.open('rb') as stream:
   if stream.read(4)!=b'GGUF':raise ValueError('Файл не имеет заголовка GGUF.')
  from gguf_info import model_context
  model_context(source)
  if shutil.disk_usage(ROOT).free<source.stat().st_size+GIB:raise ValueError('Недостаточно места для импорта.')
  ident='import-'+uuid.uuid4().hex[:12];folder=STACK/'models'/ident;folder.mkdir(parents=True)
  # A complete copy remains independent if the source disk is disconnected.
  shutil.copy2(source,folder/'model.gguf');sha=digest(folder/'model.gguf')
  item={'id':ident,'name':str(name or source.stem)[:100],'kind':'chat','quantization':'Импорт GGUF','context':65536,'recommended_ram_gb':max(8,math.ceil(source.stat().st_size/GIB)+5),'recommended_vram_gb':math.ceil(source.stat().st_size/GIB)+2,
        'source':'Локальный файл','license':'Проверьте лицензию исходной модели','files':[{'name':'model.gguf','bytes':source.stat().st_size,'sha256':sha,'url':None}]}
  self.catalog.append(item);write(ROOT/'data/custom-models.json',[m for m in self.catalog if m['id'].startswith('import-') or m['id'].startswith('hf-')]);write(folder/'.verified.json',{'model.gguf':{'sha256':sha,'mtime_ns':(folder/'model.gguf').stat().st_mtime_ns}});return item
 def hf_files(self,value):
  value=value.strip().removeprefix('https://huggingface.co/').strip('/')
  parts=value.split('/')
  if len(parts)!=2 or not all(__import__('re').fullmatch(r'[A-Za-z0-9_.-]+',p) for p in parts):raise ValueError('Введите owner/repository или ссылку на репозиторий Hugging Face.')
  response=requests.get('https://huggingface.co/api/models/'+value,params={'blobs':'true'},timeout=30);response.raise_for_status();meta=response.json()
  return {'repo':value,'revision':meta['sha'],'license':meta.get('cardData',{}).get('license','see model card'),
          'files':[{'name':f['rfilename'],'bytes':f.get('size') or f.get('lfs',{}).get('size'),'sha256':f.get('lfs',{}).get('sha256')} for f in meta['siblings'] if f['rfilename'].endswith('.gguf') and f.get('lfs',{}).get('sha256') and 'mmproj' not in f['rfilename'].lower()]}
 def add_hf(self,repo,filename):
  meta=self.hf_files(repo);file=next((f for f in meta['files'] if f['name']==filename),None)
  if not file:raise ValueError('Файл не найден или у него нет SHA256 издателя.')
  if '-of-' in filename:raise ValueError('Для этой первой версии выберите единый GGUF. Разделённые GGUF требуют ручной подготовки.')
  ident='hf-'+uuid.uuid4().hex[:12];size=file['bytes'];item={'id':ident,'name':pathlib.PurePosixPath(filename).stem[:100],'kind':'chat','quantization':'GGUF · Hugging Face','context':65536,'recommended_ram_gb':max(8,math.ceil(size/GIB)+5),'recommended_vram_gb':math.ceil(size/GIB)+2,'source':'https://huggingface.co/'+meta['repo'],'license':meta['license'],'files':[{'name':'model.gguf','bytes':size,'sha256':file['sha256'],'url':'https://huggingface.co/'+meta['repo']+'/resolve/'+meta['revision']+'/'+urllib.parse.quote(filename)}]}
  self.catalog.append(item);write(ROOT/'data/custom-models.json',[m for m in self.catalog if m['id'].startswith(('import-','hf-'))]);return item

library=Library()
def register(app):
 async def get(request):return web.json_response({**library.snapshot(),'model_ready':bool(request.app.get('runtime',{}).get('metrics',{}).get('model_ready'))})
 async def scan(request):return web.json_response(await asyncio.to_thread(library.scan))
 async def download(request):library.download((await request.json())['id']);return web.json_response({'ok':True})
 async def pause(request):
  event=library.cancel.get((await request.json())['id'])
  if event:event.set()
  return web.json_response({'ok':True})
 async def activate(request):library.activate((await request.json())['id']);return web.json_response({'ok':True})
 async def imported(request):
  value=await request.json();return web.json_response(await asyncio.to_thread(library.import_local,value['path'],value.get('name')))
 async def hf(request):return web.json_response(await asyncio.to_thread(library.hf_files,(await request.json())['repo']))
 async def hf_add(request):
  value=await request.json();return web.json_response(await asyncio.to_thread(library.add_hf,value['repo'],value['filename']))
 async def connect(request):
  value=await request.json();return web.json_response(await asyncio.to_thread(library.connect_local,value['url'],value['model'],value.get('context',65536)))
 app.router.add_get('/api/library',get)
 for path,handler in [('scan',scan),('download',download),('pause',pause),('activate',activate),('import',imported),('hf',hf),('hf-add',hf_add),('connect',connect)]:app.router.add_post('/api/library/'+path,handler)
