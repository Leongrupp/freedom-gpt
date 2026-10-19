"""Start this portable installation and its browser window without global settings."""
import bootstrap
import ctypes,hashlib,json,os,pathlib,socket,subprocess,sys,time,urllib.request
from bootstrap import ROOT,config,read,write,write_hermes,relocate
from platform_support import PROCESS_FLAGS,open_browser,show_error
def health(port):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:return json.load(response)
 except Exception:return None
def free_port(preferred):
 for port in range(preferred,preferred+40):
  try:
   with socket.socket() as sock:
    if os.name!='nt':sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind(('127.0.0.1',port));return port
  except OSError:pass
 raise RuntimeError('Не найден свободный локальный порт.')
def main():
 from preflight import ensure
 ensure(ROOT)
 bootstrap.ensure_private_model()
 cfg=config();ident=hashlib.sha256(str(ROOT).encode()).hexdigest()[:16];current=health(cfg['ui_port'])
 if not current or current.get('installation')!=ident:
  relocate();bootstrap.import_pending_history();cfg['ui_port']=free_port(cfg['ui_port'])
  # Stop this installation's supervisor before selecting a new model port.
  from library import library
  if not bootstrap.PRIVATE:library.stop_model();cfg['model_port']=free_port(cfg['model_port'])
  write(ROOT/'data/settings.json',cfg)
  write_hermes()
  with (ROOT/'logs/launcher.log').open('ab') as log:
   child=subprocess.Popen([sys.executable,'-s',str(ROOT/'server.py')],cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=log,creationflags=PROCESS_FLAGS)
  import psutil
  write(ROOT/'.tmp/server-process.json',{'pid':child.pid,'created':psutil.Process(child.pid).create_time()})
  for _ in range(90):
   if health(cfg['ui_port']):break
   if child.poll() is not None:raise RuntimeError('Не удалось запустить приложение. Подробности: '+str(ROOT/'logs/launcher.log'))
   time.sleep(.5)
  else:raise RuntimeError('Запуск занял слишком долго. Подробности в logs/launcher.log.')
 if '--no-browser' in sys.argv:return
 url=f"http://127.0.0.1:{cfg['ui_port']}/"
 open_browser(ROOT,url)
if __name__=='__main__':
 try:main()
 except Exception as exc:show_error(str(exc));raise SystemExit(1)
