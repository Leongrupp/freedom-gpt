"""Local hardware assessment, verified resumable downloads and owned model processes."""
import asyncio,concurrent.futures,hashlib,json,math,os,pathlib,shutil,subprocess,sys,threading,time,urllib.parse,uuid
import psutil,requests
from hf_access import access as hf_access
from aiohttp import web
from bootstrap import ROOT,STACK,HOME,config,read,write,write_hermes
from platform_support import PROCESS_FLAGS,file_lock,hardware as platform_hardware,native_binary
sys.path.insert(0,str(STACK/'creative-kit'))
from gpu_lease import active as image_job_active
GIB=1024**3

def hardware():return platform_hardware(ROOT)

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
  self.transition=threading.Lock();self.activation=None;self.download_locks={};self.catalog_lock=threading.RLock()
  from discovery import Discovery
  self.discovery=Discovery(self)
 def save_custom(self):
  with self.catalog_lock:
   bundled={m['id'] for m in read(ROOT/'catalog.json',[])}
   write(ROOT/'data/custom-models.json',[m for m in self.catalog if m['id'] not in bundled])
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
  if item['kind'] in {'image','video'}:return {'level':'limited','reason':f"Для этого режима рекомендуется NVIDIA от {item.get('recommended_vram_gb',12)} ГБ VRAM."}
  return {'level':'cpu','reason':'Возможна частичная загрузка на GPU или работа на CPU. Скорость будет ниже.'}
 def snapshot(self):
  rows=[]
  for item in self.catalog:
   folder=self.folder(item);total=sum(f['bytes'] for f in item['files']);done=sum(min(f['bytes'],(folder/f['name']).stat().st_size if (folder/f['name']).exists() else (folder/(f['name']+'.part')).stat().st_size if (folder/(f['name']+'.part')).exists() else 0) for f in item['files'])
   rows.append({**item,'installed':self.ready(item),'bytes':done,'total':total,'percent':round(done/total*100,1) if total else 0,'recommendation':self.recommendation(item),'job':self.jobs.get(item['id'])})
  selected='huihui-qwen38-coder' if self.device.get('vram_gb',0)>=15.9 and self.device.get('ram_gb',0)>=31 else 'qwen35-4b' if self.device.get('ram_gb',0)>=12 else 'qwen35-08b'
  return {'hardware':self.device,'models':rows,'active':config().get('active'),'external_model':config().get('external_model'),'recommended':selected,'activation':self.activation,'first_run':not config().get('onboarded'),'root':str(ROOT),'license_notice':'Лицензии и источники указаны у каждой модели. Модели загружаются отдельно от приложения.'}
 def scan(self,task='code'):
  self.device=hardware();write(ROOT/'data/hardware.json',self.device)
  self.discovery.start(task=task);return self.snapshot()
 def download(self,ident):
  item=self.model(ident)
  if not item:raise ValueError('Модель не найдена.')
  if self.jobs.get(ident,{}).get('state') in ['downloading','verifying']:return
  missing=0
  for f in item['files']:
   part=self.folder(item)/(f['name']+'.part');final=self.folder(item)/f['name']
   size=part.stat().st_size if part.exists() else f['bytes'] if final.exists() else 0
   missing+=f['bytes']-(size if 0<=size<=f['bytes'] else 0)
  from model_advisor import disk_at
  if disk_at(self.folder(item))<missing+2*GIB:raise ValueError('Недостаточно места. Для загрузки и запаса нужно '+str(round((missing+2*GIB)/GIB,1))+' ГБ.')
  try:lock=file_lock(self.folder(item)/'.download.lock')
  except OSError:raise ValueError('Эта модель уже скачивается в другом процессе. Дождитесь завершения текущей загрузки.')
  self.download_locks[ident]=lock
  self.cancel[ident]=threading.Event();self.jobs[ident]={'state':'downloading','speed':0};self.pool.submit(self._download,item)
 def _download(self,item):
  ident=item['id'];folder=self.folder(item);folder.mkdir(parents=True,exist_ok=True);verified=read(folder/'.verified.json',{})
  try:
   for f in item['files']:
    final=folder/f['name'];part=folder/(f['name']+'.part')
    if final.exists() and final.stat().st_size==f['bytes'] and digest(final)==f['sha256']:
     verified[f['name']]={'sha256':f['sha256'],'mtime_ns':final.stat().st_mtime_ns};continue
    if final.exists():raise ValueError('Файл с таким именем уже существует и не прошёл проверку. Он сохранён; выберите новую папку модели.')
    if part.exists() and part.stat().st_size>f['bytes']:
     os.replace(part,part.with_name(part.name+'.failed-size-'+uuid.uuid4().hex[:10]))
    for attempt in range(5):
     if self.cancel[ident].is_set():raise InterruptedError()
     start=part.stat().st_size if part.exists() else 0
     if start==f['bytes']:break
     try:
      with requests.get(f['url'],headers=hf_access.headers(f['url'],{'Range':f'bytes={start}-'}),stream=True,timeout=(20,35)) as response:
       if response.status_code in (401,403):raise ValueError('Нет доступа к модели. Подключите Hugging Face в подборе моделей и откройте карточку модели для получения доступа.')
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
    if part.stat().st_size!=f['bytes'] or digest(part)!=f['sha256']:
     preserved=part.with_name(part.name+'.failed-sha256-'+uuid.uuid4().hex[:10])
     os.replace(part,preserved)
     raise ValueError('SHA256 не совпал. Повреждённая копия сохранена отдельно; нажмите скачать снова. Запуск запрещён.')
    if item['kind']=='chat' and f['name']=='model.gguf':
     from gguf_info import model_context
     model_context(part)
    os.replace(part,final);verified[f['name']]={'sha256':f['sha256'],'mtime_ns':final.stat().st_mtime_ns};write(folder/'.verified.json',verified);self.jobs[ident]['state']='downloading'
   write(folder/'.verified.json',verified)
   if item['kind']=='image':write(STACK/'creative-kit/manifest.json',[{'path':str(folder/f['name']),**f} for f in item['files']])
   self.jobs[ident]={'state':'complete','speed':0}
  except InterruptedError:self.jobs[ident]={'state':'paused','speed':0}
  except Exception as exc:self.jobs[ident]={'state':'error','error':str(exc),'speed':0}
  finally:
   lock=self.download_locks.pop(ident,None)
   if lock:lock.close()
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
     if child.name().lower() in {'llama-server.exe','llama-server'}:child.terminate()
  except (KeyError,psutil.NoSuchProcess):pass
 def engine_config(self,item):
  device=hardware();self.device=device;vram=max((g.get('free_gb') or 0 for g in device.get('gpus',[]) if g.get('cuda') or g.get('metal') or g.get('vulkan')),default=0);weight=sum(f['bytes'] for f in item['files'] if f['name']=='model.gguf')/GIB
  context=min(65536,int(item.get('context') or 65536))
  ngl='all' if device.get('gpu_accelerated') and vram>=weight+4 else str(max(0,int(24*max(0,vram-2)/max(weight,1)))) if device.get('gpu_accelerated') else '0'
  overhead=max(2,min(5,1.5+weight*.35))
  required_ram=weight+overhead if device.get('unified_memory') else 4 if ngl=='all' else max(0,weight-max(0,vram-2))+overhead
  backend='metal' if device.get('metal') else 'cuda' if device.get('cuda') else 'vulkan' if device.get('vulkan') else 'cpu'
  from system_check import system
  backend=system.snapshot().get('text_backend') or backend
  if backend=='cpu':ngl='0';required_ram=weight+overhead
  native_binary(ROOT,'llama',backend)
  if device.get('ram_available_gb',0)<required_ram:raise ValueError('Недостаточно свободной RAM для этого режима: нужно примерно '+str(round(required_ram,1))+' ГБ. Закройте другие модели/тяжёлые приложения или выберите более лёгкую модель.')
  return {'model':str(self.folder(item)/'model.gguf'),'mmproj':str(self.folder(item)/'mmproj.gguf') if any(f['name']=='mmproj.gguf' for f in item['files']) else None,
          'context':context,'port':config()['model_port'],'alias':'freedom-local','threads':max(1,min(16,device.get('physical_cores') or 4)),
          'backend':backend,'ngl':ngl,'mtp':bool(item.get('mtp') and ngl=='all'),'kv_cache':'q8_0'}
 def start_model(self,item):
  cfg=self.engine_config(item);write(STACK/'server-settings.json',cfg);write_hermes(cfg['context'])
  (STACK/'.tmp/stop-server').unlink(missing_ok=True)
  with (ROOT/'logs/model-supervisor.log').open('ab') as log:
   process=subprocess.Popen([sys.executable,'-s',str(ROOT/'engine_supervisor.py')],cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=log,creationflags=PROCESS_FLAGS)
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
  context=model_context(source);sha=digest(source);size=source.stat().st_size
  with self.catalog_lock:
   existing=next((m for m in self.catalog if m['kind']=='chat' and any(f.get('sha256')==sha for f in m['files']) and self.ready(m)),None)
   if existing:return existing
   base=(STACK/'models').resolve();base.mkdir(parents=True,exist_ok=True)
   if shutil.disk_usage(base).free<size+GIB:raise ValueError('Недостаточно места для импорта.')
   ident='import-'+uuid.uuid4().hex[:12];folder=base/ident;staging=base/('.'+ident);staging.mkdir()
   assert staging.resolve().parent==base and staging.name.startswith('.import-')
   try:
    # Install only a complete independent copy; keep the original file untouched.
    target=staging/'model.gguf';shutil.copy2(source,target)
    if target.stat().st_size!=size or digest(target)!=sha:raise ValueError('Исходный файл изменился во время импорта. Повторите импорт после завершения записи файла.')
    model_context(target)
    item={'id':ident,'name':str(name or source.stem)[:100],'kind':'chat','quantization':'Импорт GGUF','context':min(65536,context),'recommended_ram_gb':max(8,math.ceil(size/GIB)+5),'recommended_vram_gb':math.ceil(size/GIB)+2,
          'source':'Локальный файл','license':'Проверьте лицензию исходной модели','files':[{'name':'model.gguf','bytes':size,'sha256':sha,'url':None}]}
    write(staging/'.verified.json',{'model.gguf':{'sha256':sha,'mtime_ns':target.stat().st_mtime_ns}})
    os.replace(staging,folder);self.catalog.append(item)
    try:self.save_custom()
    except Exception:
     self.catalog.remove(item);os.replace(folder,staging);raise
    return item
   finally:
    if staging.exists() and staging.resolve().parent==base and staging.name.startswith('.import-'):shutil.rmtree(staging)
 def hf_files(self,value):
  value=value.strip().removeprefix('https://huggingface.co/').strip('/')
  parts=value.split('/')
  if len(parts)!=2 or not all(__import__('re').fullmatch(r'[A-Za-z0-9_.-]+',p) for p in parts):raise ValueError('Введите owner/repository или ссылку на репозиторий Hugging Face.')
  url='https://huggingface.co/api/models/'+value
  response=requests.get(url,params={'blobs':'true'},headers=hf_access.headers(url),timeout=30)
  if response.status_code in (401,403):raise ValueError('Нет доступа к репозиторию. Подключите Hugging Face в подборе моделей и проверьте доступ на странице модели.')
  response.raise_for_status();meta=response.json()
  if not isinstance(meta,dict) or not isinstance(meta.get('sha'),str):raise ValueError('Hugging Face вернул неполные сведения о модели.')
  card=meta.get('cardData') or {};card=card if isinstance(card,dict) else {}
  return {'repo':value,'revision':meta['sha'],'license':card.get('license','see model card'),
          'architecture':(meta.get('gguf') or {}).get('architecture'),'context':(meta.get('gguf') or {}).get('context_length'),
          'files':[{'name':f['rfilename'],'bytes':f.get('size') or f.get('lfs',{}).get('size'),'sha256':f.get('lfs',{}).get('sha256')} for f in meta['siblings'] if f['rfilename'].endswith('.gguf') and f.get('lfs',{}).get('sha256') and 'mmproj' not in f['rfilename'].lower()]}
 def add_hf(self,repo,filename):
  meta=self.hf_files(repo);file=next((f for f in meta['files'] if f['name']==filename),None)
  if not file:raise ValueError('Файл не найден или у него нет SHA256 издателя.')
  if '-of-' in filename:raise ValueError('Для этой первой версии выберите единый GGUF. Разделённые GGUF требуют ручной подготовки.')
  existing=next((m for m in self.catalog if m['kind']=='chat' and any(f.get('sha256')==file['sha256'] for f in m['files'])),None)
  if existing:return existing
  ident='hf-'+uuid.uuid4().hex[:12];size=file['bytes'];item={'id':ident,'name':pathlib.PurePosixPath(filename).stem[:100],'kind':'chat','quantization':'GGUF · Hugging Face','context':65536,'recommended_ram_gb':max(8,math.ceil(size/GIB)+5),'recommended_vram_gb':math.ceil(size/GIB)+2,'source':'https://huggingface.co/'+meta['repo'],'license':meta['license'],'files':[{'name':'model.gguf','bytes':size,'sha256':file['sha256'],'url':'https://huggingface.co/'+meta['repo']+'/resolve/'+meta['revision']+'/'+urllib.parse.quote(filename)}]}
  self.catalog.append(item);self.save_custom();return item

library=Library()
def register(app):
 async def get(request):return web.json_response({**library.snapshot(),'model_ready':bool(request.app.get('runtime',{}).get('metrics',{}).get('model_ready'))})
 async def scan(request):
  value=await request.json();return web.json_response(await asyncio.to_thread(library.scan,value.get('task','code')))
 async def download(request):library.download((await request.json())['id']);return web.json_response({'ok':True})
 async def pause(request):
  event=library.cancel.get((await request.json())['id'])
  if event:event.set()
  return web.json_response({'ok':True})
 async def activate(request):
  from video import videos
  if videos.busy():raise ValueError('Дождитесь завершения видео перед переключением модели.')
  library.activate((await request.json())['id']);return web.json_response({'ok':True})
 async def imported(request):
  value=await request.json();return web.json_response(await asyncio.to_thread(library.import_local,value['path'],value.get('name')))
 async def hf(request):return web.json_response(await asyncio.to_thread(library.hf_files,(await request.json())['repo']))
 async def hf_add(request):
  value=await request.json();return web.json_response(await asyncio.to_thread(library.add_hf,value['repo'],value['filename']))
 async def connect(request):
  from video import videos
  if videos.busy():raise ValueError('Дождитесь завершения видео перед переключением модели.')
  value=await request.json();return web.json_response(await asyncio.to_thread(library.connect_local,value['url'],value['model'],value.get('context',65536)))
 app.router.add_get('/api/library',get)
 async def discovery_get(request):return web.json_response(library.discovery.snapshot())
 async def discovery_start(request):
  data=await request.json();return web.json_response(library.discovery.start(data.get('query',''),data.get('provider','all'),data.get('task','chat')))
 async def discovery_add(request):
  item=await asyncio.to_thread(library.discovery.add,(await request.json())['key']);return web.json_response({'id':item['id']})
 app.router.add_get('/api/library/search',discovery_get)
 app.router.add_post('/api/library/search',discovery_start)
 app.router.add_post('/api/library/search/add',discovery_add)
 for path,handler in [('scan',scan),('download',download),('pause',pause),('activate',activate),('import',imported),('hf',hf),('hf-add',hf_add),('connect',connect)]:app.router.add_post('/api/library/'+path,handler)
