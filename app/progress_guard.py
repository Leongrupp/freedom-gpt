"""UI-owned stop requests from the install-local replay limiter."""
import asyncio,contextlib,json,logging,os,pathlib,re,shutil,time

log=logging.getLogger('freedom.progress')
SID=re.compile(r'^[A-Za-z0-9_-]{1,140}$')

class ProgressGuard:
 def __init__(self,root,portable,bridge):
  self.root,self.portable,self.bridge=root,portable,bridge
  self.folder=root/'data/progress-guard';self.folder.mkdir(parents=True,exist_ok=True)
  self.requests=self.folder/'requests';self.requests.mkdir(exist_ok=True)
  self.task=None
  source=root/'agent_plugins/freedom-progress'
  if not source.is_dir():source=root/'runtime/freedom/agent_plugins/freedom-progress'
  if source.is_dir():
   target=portable.HOME/'plugins/freedom-progress';target.mkdir(parents=True,exist_ok=True)
   for name in ['__init__.py','policy.py','background.py','web_scope.py','arshi.py','reasoning.py','reasoning_store.py','work_state.py','work_trial.py','plugin.yaml']:
    if not (target/name).exists() or (target/name).read_bytes()!=(source/name).read_bytes():shutil.copy2(source/name,target/name)
   portable.write(target/'runtime.json',{'app_relative':os.path.relpath(root,target)})
 def notice(self,sid):
  return self.portable.read(self.folder/(sid+'.notice.json'),None) if SID.fullmatch(sid or '') else None
 def clear(self,sid,discard_request=False):
  if SID.fullmatch(sid or ''):
   (self.folder/(sid+'.notice.json')).unlink(missing_ok=True)
   if discard_request:(self.requests/(sid+'.json')).unlink(missing_ok=True)
 async def start(self):self.task=asyncio.create_task(self.watch())
 async def close(self):
  if self.task:
   self.task.cancel()
   with contextlib.suppress(asyncio.CancelledError):await self.task
 async def handle(self,file):
  data=json.loads(file.read_text(encoding='utf-8'));sid=data.get('sid','');created=float(data.get('created',0))
  if not SID.fullmatch(sid) or file.name!=sid+'.json':raise ValueError('Invalid progress-guard session')
  if not 0<=time.time()-created<60:file.unlink(missing_ok=True);return
  # A request belongs to the turn that produced it, never a newly admitted successor.
  live=self.bridge.live.get(sid,{})
  if live.get('started_at',0)>created:
   file.unlink(missing_ok=True);return
  snapshot=await self.bridge.resume(sid)
  live=self.bridge.live.get(sid,{})
  if live.get('started_at',0)>created or (live.get('generation') is not None and live['generation']!=snapshot.get('execution_generation')):
   file.unlink(missing_ok=True);return
  if snapshot.get('running'):
   if (snapshot.get('info') or {}).get('yolo') is True:
    # The tool middleware already refused the repeated call and returned a new-
    # approach hint. Full access keeps the turn/goal alive; never replay a task.
    recovery={**data,'mode':'replanning','generation':snapshot.get('execution_generation'),'handled_at':time.time()}
    self.portable.write(self.folder/(sid+'.recovery.json'),recovery)
    self.portable.write(file.with_suffix('.done'),recovery);file.unlink(missing_ok=True)
    (self.folder/(sid+'.notice.json')).unlink(missing_ok=True)
    await self.bridge.broadcast({'type':'progress.recovering','session_id':sid,'recovery':recovery})
    return
   control=await self.bridge.rpc('session.control.read',session_id=sid)
   if ((control.get('control') or {}).get('goal') or {}).get('status')=='active':
    await self.bridge.rpc('session.control',session_id=sid,action='goal.pause')
   await self.bridge.rpc('session.interrupt',session_id=sid,execution_generation=snapshot['execution_generation'])
  notice={'reason':data.get('reason'),'tool':str(data.get('tool',''))[:100],'count':data.get('count'),
   'created':created,'stopped_at':time.time(),'generation':snapshot.get('execution_generation')}
  self.portable.write(self.folder/(sid+'.notice.json'),notice)
  self.portable.write(file.with_suffix('.done'),{**data,'handled_at':time.time()});file.unlink(missing_ok=True)
  await self.bridge.broadcast({'type':'progress.stopped','session_id':sid,'notice':notice})
 async def watch(self):
  while True:
   await asyncio.sleep(1)
   if not self.bridge.ready.is_set():continue
   for file in list(self.requests.glob('*.json'))[:10]:
    try:await asyncio.wait_for(self.handle(file),15)
    except asyncio.CancelledError:raise
    except Exception as exc:log.warning('Progress stop request deferred: %s',type(exc).__name__)
