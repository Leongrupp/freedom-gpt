"""Own and supervise this installation's llama.cpp process only."""
import bootstrap
import datetime,json,os,pathlib,subprocess,sys,time
from bootstrap import ROOT,STACK,read,write
from platform_support import PROCESS_FLAGS,file_lock,native_binary,native_environment
sys.path.insert(0,str(STACK/'creative-kit'))
from gpu_lease import active as gpu_reserved
try:lock=file_lock(STACK/'.tmp/supervisor.lock')
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
  cfg=read(STACK/'server-settings.json',{});engine=native_binary(ROOT,'llama',cfg.get('backend'))
  args=[str(engine),'-m',cfg['model'],'--host','127.0.0.1','--port',str(cfg['port']),'--alias',cfg['alias'],'-c',str(cfg['context']),'-np','1','-ngl',str(cfg['ngl']),'-fa','on','-ctk','q8_0','-ctv','q8_0','-t',str(cfg['threads']),'-tb',str(cfg['threads']),'-b','512','-ub','256','--metrics','--slots','--no-webui','--cache-prompt','--log-verbosity','3']
  if cfg.get('context_mode')=='auto':
   # Size a new model once. Keep that allocated window on worker recovery so
   # an existing agent never outgrows a silently reduced server context.
   args[args.index('-c')+1]=str(cfg['context']) if cfg.get('context_verified') else '0'
   if cfg.get('ngl')=='auto':index=args.index('-ngl');del args[index:index+2]
   args+=['--fit','on','--fit-ctx',str(cfg.get('fit_min_context',65536)),'--fit-target',str(cfg.get('fit_margin_mb',1024))]
  if cfg.get('api_alias'):args[args.index('--alias')+1]=','.join(dict.fromkeys([cfg['alias'],cfg['api_alias']]))
  for flag,key in [('-tb','threads_batch'),('-b','batch_size'),('-ub','ubatch_size')]:
   if key in cfg:args[args.index(flag)+1]=str(cfg[key])
  if 'cpu_poll' in cfg:args+=['--poll',str(cfg['cpu_poll'])]
  if 'priority' in cfg:args+=['--prio',str(cfg['priority'])]
  if cfg.get('mmproj'):args+=['--mmproj',cfg['mmproj'],'--no-mmproj-offload']
  if cfg.get('mtp'):args+=['--spec-type','draft-mtp','--spec-draft-n-max',str(cfg.get('draft_tokens',5)),'--reasoning-effort','low','--reasoning-budget',str(cfg.get('reasoning_budget',-1)),'--no-reasoning-preserve']
  path=STACK/'logs'/('llama-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log');(STACK/'.tmp/current-server-log.txt').write_text(str(path),encoding='utf8')
  with path.open('ab') as log:
   child=subprocess.Popen(args,cwd=engine.parent,env=native_environment(ROOT,engine),stdout=log,stderr=log,creationflags=PROCESS_FLAGS)
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
