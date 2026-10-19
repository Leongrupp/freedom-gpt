"""Start this portable installation and its browser window without global settings."""
import bootstrap
import ctypes,hashlib,json,os,pathlib,socket,subprocess,sys,time,urllib.request
from bootstrap import ROOT,config,read,write,write_hermes,relocate
def health(port):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:return json.load(response)
 except Exception:return None
def free_port(preferred):
 for port in range(preferred,preferred+40):
  try:
   with socket.socket() as sock:sock.bind(('127.0.0.1',port));return port
  except OSError:pass
 raise RuntimeError('Не найден свободный локальный порт.')
def main():
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
   child=subprocess.Popen([sys.executable,'-s',str(ROOT/'server.py')],cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
  import psutil
  write(ROOT/'.tmp/server-process.json',{'pid':child.pid,'created':psutil.Process(child.pid).create_time()})
  for _ in range(90):
   if health(cfg['ui_port']):break
   if child.poll() is not None:raise RuntimeError('Не удалось запустить приложение. Подробности: '+str(ROOT/'logs/launcher.log'))
   time.sleep(.5)
  else:raise RuntimeError('Запуск занял слишком долго. Подробности в logs/launcher.log.')
 if '--no-browser' in sys.argv:return
 url=f"http://127.0.0.1:{cfg['ui_port']}/"
 browsers=[pathlib.Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',pathlib.Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe',pathlib.Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe']
 browser=next((p for p in browsers if p.is_file()),None)
 if browser:subprocess.Popen([str(browser),'--app='+url,'--user-data-dir='+str(ROOT/'.cache/browser'),'--no-first-run','--no-default-browser-check','--disable-background-networking','--window-size=1480,960'],cwd=ROOT)
 else:__import__('webbrowser').open(url)
if __name__=='__main__':
 try:main()
 except Exception as exc:ctypes.windll.user32.MessageBoxW(None,str(exc),'Freedom GPT',0x10)
