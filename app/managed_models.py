"""Switch only the identified private local model supervisor; preserve agent settings."""
import json,os,pathlib,subprocess,sys,time
import psutil,requests
from bootstrap import ROOT,STACK,config,read,write
from platform_support import PROCESS_FLAGS,file_lock

PREFIX='freedom-local-gguf-'

def alias(ident):return PREFIX+ident
def catalog_id(value):return value[len(PREFIX):] if str(value or '').startswith(PREFIX) else None

def configured_id():
 cfg=read(STACK/'server-settings.json',{})
 return cfg.get('catalog_id') or config().get('active') or 'huihui-qwen38-coder'

def health():
 try:return requests.get(f"http://127.0.0.1:{config()['model_port']}/health",timeout=2).json().get('status')=='ok'
 except (requests.RequestException,ValueError):return False

def route_ready(ident):
 try:
  response=requests.get(f"http://127.0.0.1:{config()['model_port']}/v1/models",timeout=2)
  return response.status_code==200 and any(row.get('id')==alias(ident) for row in response.json().get('data',[])) and health()
 except (requests.RequestException,ValueError):return False

def owned_supervisor():
 try:
  pid=int((STACK/'.tmp/supervisor.pid').read_text().strip());process=psutil.Process(pid)
  expected=(STACK/'server-supervisor.py').resolve()
  if not any(pathlib.Path(arg).resolve()==expected for arg in process.cmdline()[1:] if not arg.startswith('-')):
   raise ValueError('Не подтверждён владелец процесса локальной модели.')
  return process
 except (FileNotFoundError,psutil.NoSuchProcess):return None

def idle():
 try:
  response=requests.get(f"http://127.0.0.1:{config()['model_port']}/slots",timeout=3)
  if response.status_code!=200:raise ValueError('Дождитесь готовности текущей локальной модели.')
  slots=response.json()
  if not isinstance(slots,list):raise ValueError('Не удалось проверить занятость локальной модели.')
  if any(slot.get('is_processing') for slot in slots):raise ValueError('Локальная модель выполняет задачу. Остановите ответ и очередь перед переключением.')
 except requests.ConnectionError:
  if owned_supervisor():raise ValueError('Текущая модель ещё загружается. Дождитесь её готовности.')

def stop():
 process=owned_supervisor();marker=STACK/'.tmp/stop-server'
 marker.touch()
 if not process:return
 # The confirmed supervisor terminates only its own llama child and releases its lock.
 try:process.wait(timeout=35)
 except psutil.TimeoutExpired:raise ValueError('Текущий сервер не завершился. Переключение отменено; проверьте журнал.')

def start(python=None):
 (STACK/'.tmp/stop-server').unlink(missing_ok=True)
 python=python or str(STACK/'hermes-runtime/tools/python-3.14.7+20260901-win32-x64/python.exe')
 if not pathlib.Path(python).is_file():python=sys.executable
 env=os.environ.copy();env.update(TEMP=str(STACK/'.tmp'),TMP=str(STACK/'.tmp'))
 with (ROOT/'logs/private-model-supervisor.log').open('ab') as log:
  return subprocess.Popen([python,'-B','-u',str(STACK/'server-supervisor.py')],cwd=STACK,env=env,stdout=log,stderr=log,creationflags=PROCESS_FLAGS)

def wait_ready(process,expected):
 deadline=time.monotonic()+240
 while time.monotonic()<deadline:
  if process.poll() is not None:raise ValueError('Сервер выбранной модели завершился при запуске.')
  try:
   response=requests.get(f"http://127.0.0.1:{config()['model_port']}/v1/models",timeout=2)
   if response.status_code==200 and any(row.get('id')==expected for row in response.json().get('data',[])) and health():return
  except (requests.RequestException,ValueError):pass
  time.sleep(.5)
 raise ValueError('Загрузка модели превысила время ожидания. Подробности в журнале локального движка.')

def switch(library,item,force=False):
 with file_lock(STACK/'.tmp/private-model-switch.lock'):
  if not force and configured_id()==item['id'] and route_ready(item['id']):return
  idle()
  old_settings=read(STACK/'server-settings.json',{})
  old_app=config();owner=owned_supervisor();python=owner.exe() if owner else None
  before=ROOT/'archive/private-model-settings';before.mkdir(parents=True,exist_ok=True)
  write(before/(str(time.time_ns())+'.json'),{'engine':old_settings,'application':old_app})
  stopped=False
  try:
   stop();stopped=True
   # Assess free memory after releasing the previous model, rather than treating
   # its own occupied VRAM as unavailable to every replacement.
   engine=library.engine_config(item)
   engine.update(alias=old_settings.get('alias','huihui-coder-local'),catalog_id=item['id'],
                 api_alias=alias(item['id']))
   engine.setdefault('draft_tokens',old_settings.get('draft_tokens',5))
   metadata=library.metadata(item)
   engine['mtp']=bool(any(key.endswith('.nextn_predict_layers') and value for key,value in metadata.items()) and engine['ngl']!='0')
   write(STACK/'server-settings.json',engine)
   process=start(python);wait_ready(process,alias(item['id']))
   library.record_context(item,engine)
   updated=config();updated.update(active=item['id'],external_context=engine['context'],onboarded=True)
   write(ROOT/'data/settings.json',updated)
  except Exception:
   if stopped:
    stop();write(STACK/'server-settings.json',old_settings);write(ROOT/'data/settings.json',old_app)
    process=start(python)
    wait_ready(process,old_settings.get('api_alias') or old_settings.get('alias','huihui-coder-local').split(',')[0])
   raise
