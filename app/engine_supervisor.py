"""Own and supervise this installation's llama.cpp process only."""
import bootstrap
import datetime,json,msvcrt,os,pathlib,subprocess,sys,time
from bootstrap import ROOT,STACK,read,write
sys.path.insert(0,str(STACK/'creative-kit'))
from gpu_lease import active as gpu_reserved
lock=(STACK/'.tmp/supervisor.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
except OSError:raise SystemExit(0)
child=None
def idle():
 try:
  import urllib.request
  with urllib.request.urlopen(f"http://127.0.0.1:{cfg['port']}/slots",timeout=2) as response:slots=json.load(response)
  return bool(slots) and all(not item.get('is_processing',True) for item in slots)
 except Exception:return False
try:
 while not (STACK/'.tmp/stop-server').exists():
  if gpu_reserved():time.sleep(1);continue
  cfg=read(STACK/'server-settings.json',{});engine=ROOT/'runtime/llama/llama-server.exe'
  args=[str(engine),'-m',cfg['model'],'--host','127.0.0.1','--port',str(cfg['port']),'--alias',cfg['alias'],'-c',str(cfg['context']),'-np','1','-ngl',str(cfg['ngl']),'-fa','on','-ctk','q8_0','-ctv','q8_0','-t',str(cfg['threads']),'-tb',str(cfg['threads']),'-b','512','-ub','256','--metrics','--slots','--no-webui','--cache-prompt','--log-verbosity','3']
  if cfg.get('mmproj'):args+=['--mmproj',cfg['mmproj'],'--no-mmproj-offload']
  if cfg.get('mtp'):args+=['--spec-type','draft-mtp','--spec-draft-n-max','5','--reasoning-effort','low','--reasoning-budget','1024','--no-reasoning-preserve']
  path=STACK/'logs'/('llama-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log');(STACK/'.tmp/current-server-log.txt').write_text(str(path),encoding='utf8')
  with path.open('ab') as log:
   child=subprocess.Popen(args,cwd=ROOT/'runtime/llama',env=os.environ.copy(),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
   write(STACK/'.tmp/model-process.json',{'pid':child.pid,'started':time.time()})
   while child.poll() is None and not (STACK/'.tmp/stop-server').exists():
    if gpu_reserved() and idle():break
    time.sleep(1)
   if child.poll() is None:child.terminate();child.wait(timeout=20)
  if (STACK/'.tmp/stop-server').exists():break
  time.sleep(2)
finally:
 if child and child.poll() is None:child.terminate()
 lock.close()
