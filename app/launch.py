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
def ensure_agent():
 from hermes_cli.gateway_runtime import ensure_gateway_runtime,attachable
 result=ensure_gateway_runtime(bootstrap.HOME,idle_exit=True)
 if not attachable(result):
  raise RuntimeError('Не удалось запустить службу агента: '+str(result.reason_code or result.state)+'. Подробности: '+str(bootstrap.HOME/'logs/gateway-stdio.log'))
def main():
 from ui_lifecycle import spawn_ui,ensure_supervisor
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
  # Start the canonical owner before detaching the UI. Windows launchers may
  # allow this process to detach once but refuse a second nested breakaway.
  # Preserve Hermes ownership checks and report a bounded startup failure.
  ensure_agent()
  record=spawn_ui()
  import psutil
  for _ in range(90):
   if health(cfg['ui_port']):break
   if not psutil.pid_exists(record['pid']):raise RuntimeError('Не удалось запустить приложение. Подробности: '+str(ROOT/'logs/launcher.log'))
   time.sleep(.5)
  else:raise RuntimeError('Запуск занял слишком долго. Подробности в logs/launcher.log.')
 else:
  if not current.get('gateway_ready'):ensure_agent()
  # An earlier crash/restart may have left stale process metadata.
  record=spawn_ui()
 ensure_supervisor(read(ROOT/'.tmp/server-process.json',{}),cfg['ui_port'])
 if '--no-browser' in sys.argv:return
 url=f"http://127.0.0.1:{cfg['ui_port']}/"
 open_browser(ROOT,url)
if __name__=='__main__':
 try:main()
 except Exception as exc:
  if '--no-browser' in sys.argv:print(str(exc),file=sys.stderr)
  else:show_error(str(exc))
  raise SystemExit(1)
