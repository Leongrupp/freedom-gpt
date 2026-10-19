"""Inspect private prerequisites and repair vendored Python without admin access."""
import concurrent.futures,json,os,pathlib,platform,shutil,subprocess,sys,time
from bootstrap import ROOT,read,write
from platform_support import hardware,native_binary,native_environment,PROCESS_FLAGS

class SystemCheck:
 def __init__(self):self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1);self.future=None;self.state={'state':'idle','components':[],'ready':False}
 def snapshot(self):return dict(self.state)
 def start(self,repair=False):
  if self.future and not self.future.done():return self.snapshot()
  self.state={**self.state,'state':'repairing' if repair else 'checking','error':None}
  self.future=self.pool.submit(self.inspect,repair);return self.snapshot()
 def inspect(self,repair=False):
  try:
   if repair:
    from preflight import ensure
    ensure(ROOT)
   device=hardware(ROOT);components=[{'id':'python','name':'Python','state':'ready','detail':platform.python_version(),'required':True},
    {'id':'agent','name':'Freedom Agent runtime','state':'ready' if (ROOT/'runtime/hermes/hermes_cli').is_dir() else 'missing','detail':'Включён в приложение','required':True}]
   preferred='metal' if device.get('metal') else 'cuda' if device.get('cuda') else 'vulkan' if device.get('vulkan') else 'cpu'
   choices={'llama':list(dict.fromkeys([preferred,*(['vulkan'] if device.get('cuda') else []),'cpu'])),'sd':list(dict.fromkeys(['metal' if device.get('metal') else ('cuda' if sys.platform=='win32' else 'vulkan') if device.get('cuda') else 'vulkan' if device.get('vulkan') else 'cpu','cpu']))}
   selected={}
   for kind,backends in choices.items():
    failures=[]
    for backend in backends:
     try:
      binary=native_binary(ROOT,kind,backend)
      result=subprocess.run([str(binary),'--help'],cwd=binary.parent,env=native_environment(ROOT,binary),capture_output=True,timeout=30,creationflags=PROCESS_FLAGS)
      if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace')[-240:])
      selected[kind]=backend;break
     except (OSError,RuntimeError,subprocess.SubprocessError) as exc:failures.append(backend+': '+str(exc)[-240:])
    components.append({'id':kind,'name':'Движок кода и чата' if kind=='llama' else 'Движок изображений и видео','required':kind=='llama','state':'ready' if kind in selected else 'missing','detail':selected.get(kind) or ' / '.join(failures),'fallback':kind in selected and selected[kind]!=backends[0]})
   for name,command in [('Git','git'),('Node.js','node')]:
    found=shutil.which(command)
    if command=='git' and sys.platform=='darwin' and found=='/usr/bin/git':
     tools=subprocess.run(['xcode-select','-p'],capture_output=True,timeout=10)
     if tools.returncode:found=None
    components.append({'id':command,'name':name,'state':'ready' if found else 'optional','required':False,'detail':found or 'Для соответствующих проектов; не нужен для запуска чата'})
   result={'state':'complete','checked_at':time.time(),'components':components,'ready':all(c['state']=='ready' for c in components if c.get('required')),
    'hardware':device,'text_backend':selected.get('llama'),'image_backend':selected.get('sd'),'private_installation':True,'system_changes':False,
    'driver_note':'Драйверы GPU управляются операционной системой. При недоступном ускорении приложение использует совместимый CPU-движок.'}
   write(ROOT/'data/system-check.json',result);self.state=result
  except Exception as exc:self.state={**self.state,'state':'error','ready':False,'error':str(exc)}

system=SystemCheck()
def register(app):
 from aiohttp import web
 async def status(request):
  if system.state['state']=='idle':system.start()
  return web.json_response(system.snapshot())
 async def check(request):return web.json_response(system.start())
 async def repair(request):return web.json_response(system.start(repair=True))
 app.router.add_get('/api/system',status);app.router.add_post('/api/system/check',check);app.router.add_post('/api/system/repair',repair)
