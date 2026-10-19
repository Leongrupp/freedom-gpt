"""Open the local release site after the server is ready; reuse an existing instance."""
import ctypes,json,os,pathlib,subprocess,sys,time,urllib.request,webbrowser
ROOT=pathlib.Path(__file__).resolve().parent;PROJECT=ROOT.parent;URL='http://127.0.0.1:17900/'
def ready():
 try:
  with urllib.request.urlopen(URL+'api/release',timeout=2) as response:return json.load(response).get('product')=='Freedom GPT'
 except Exception:return False
def main():
 if not ready():
  (PROJECT/'logs').mkdir(exist_ok=True)
  env=os.environ.copy();env.update(TEMP=str(PROJECT/'.tmp'),TMP=str(PROJECT/'.tmp'),PYTHONDONTWRITEBYTECODE='1')
  with (PROJECT/'logs/website-server.log').open('ab') as log:
   child=subprocess.Popen([sys.executable,'-s',str(ROOT/'server.py')],cwd=PROJECT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
  for _ in range(90):
   if ready():break
   if child.poll() is not None:raise RuntimeError('Сайт не запустился. Подробности: '+str(PROJECT/'logs/website-server.log'))
   time.sleep(.25)
  else:raise RuntimeError('Не удалось дождаться локального сайта.')
 if '--no-browser' not in sys.argv:webbrowser.open(URL)
if __name__=='__main__':
 try:main()
 except Exception as error:ctypes.windll.user32.MessageBoxW(None,str(error),'Freedom GPT — сайт',0x10)
