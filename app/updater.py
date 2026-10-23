"""Signed updates requested by the owner; apply only after a manual check and while idle."""
import asyncio,contextlib,json,os,pathlib,shutil,subprocess,sys,time,urllib.parse,urllib.request
from bootstrap import ROOT,STACK,config,read,write
from update_protocol import verify,sha256,version,target_platform
from platform_support import python_binary,PROCESS_FLAGS
META=read(ROOT/'version.json',{'version':'1.2.0','repository':'Leongrupp/freedom-gpt'})
FEED='https://github.com/'+META['repository']+'/releases/latest/download/'+('update.json' if target_platform()=='windows-x64' else 'update-'+target_platform()+'.json')
ALLOWED={'github.com','api.github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}

class TrustedRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  url=urllib.parse.urlparse(newurl)
  if url.scheme!='https' or url.hostname not in ALLOWED:raise ValueError('Untrusted update redirect')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def remote(url,headers=None):
 parsed=urllib.parse.urlparse(url)
 if parsed.scheme!='https' or parsed.hostname not in ALLOWED or parsed.username or parsed.password:raise ValueError('Untrusted update URL')
 return urllib.request.build_opener(TrustedRedirect()).open(urllib.request.Request(url,headers={'User-Agent':'FreedomGPT/'+META['version'],**(headers or {})}),timeout=25)

class Updates:
 def __init__(self):
  self.state={'state':'idle','current_version':META['version'],'enabled':False,'manual_only':True,'percent':0}
  self.manual_requested=False
  self.task=None;self.check_task=None;self.lock=asyncio.Lock();self.payload=None;self.package=None;self.envelope=None
 def status(self):return dict(self.state,enabled=False,manual_only=True,local_build=META.get('local_build'))
 def enabled(self,value):
  if not isinstance(value,bool):raise ValueError('Expected a boolean')
  cfg=config();cfg['auto_update']=False;write(ROOT/'data/settings.json',cfg);return self.status()
 async def start(self,app,bridge):self.task=asyncio.create_task(self.loop(app,bridge))
 async def close(self):
  for task in [self.task,self.check_task]:
   if task:task.cancel()
  for task in [self.task,self.check_task]:
   if task:
    with contextlib.suppress(asyncio.CancelledError):await task
 def request_check(self):
  self.manual_requested=True
  if not self.check_task or self.check_task.done():self.check_task=asyncio.create_task(self.check())
  return self.status()
 async def check(self):
  if self.lock.locked():return
  async with self.lock:
   try:
    self.state.update(state='checking',error=None,last_check=time.time())
    def fetch_manifest():
     with remote(FEED) as response:raw=response.read(16*1024**2+1)
     if len(raw)>16*1024**2:raise ValueError('Update manifest too large')
     return json.loads(raw)
    envelope=await asyncio.to_thread(fetch_manifest)
    payload=verify(envelope,(ROOT/'update-key.pub').read_text(),META['version'])
    if payload is None:self.state.update(state='current');return
    self.envelope=envelope;self.payload=payload;self.state.update(available_version=payload['version'],state='downloading',percent=0)
    self.package=await asyncio.to_thread(self.download,payload)
    self.state.update(state='ready',percent=100)
   except asyncio.CancelledError:raise
   except Exception as exc:self.state.update(state='error',error=type(exc).__name__+': '+str(exc)[:180])
 def download(self,payload):
  package=payload['package'];folder=ROOT/'.cache/updates'/payload['version'];folder.mkdir(parents=True,exist_ok=True)
  write(folder/'update.json',self.envelope)
  final=folder/'package.zip';part=folder/'package.zip.part'
  if final.is_file() and final.stat().st_size==package['bytes'] and sha256(final)==package['sha256']:return final
  start=part.stat().st_size if part.exists() else 0
  if start>package['bytes']:raise ValueError('Partial update is larger than release')
  required=package['bytes']-start+sum(f['bytes'] for f in payload['files'])+1024**3
  if shutil.disk_usage(ROOT).free<required:raise ValueError('Not enough free disk space for a safe update')
  with remote(package['url'],{'Range':f'bytes={start}-'} if start else {}) as response:
   if start and response.status!=206:start=0
   if start and not response.headers.get('Content-Range','').startswith(f'bytes {start}-'):raise ValueError('Invalid resume response')
   with part.open('ab' if start else 'wb') as output:
    count=start
    while block:=response.read(1024**2):
     count+=len(block)
     if count>package['bytes']:raise ValueError('Oversized update package')
     output.write(block);self.state['percent']=round(count/package['bytes']*100,1)
  if part.stat().st_size!=package['bytes'] or sha256(part)!=package['sha256']:raise ValueError('Update SHA256 verification failed')
  os.replace(part,final);return final
 async def loop(self,app,bridge):
  await asyncio.sleep(12)
  while True:
   if self.manual_requested and self.state['state']=='ready':await self.try_apply(app,bridge)
   await asyncio.sleep(5)
 async def try_apply(self,app,bridge):
  if not self.package or not self.payload or app.get('prompt_admissions',0) or app.get('performance_busy'):return
  from library import library
  from video import videos
  if videos.busy():return
  if any(v.get('active') for v in bridge.live.values()):return
  if any(j.get('state') in {'downloading','verifying'} for j in library.jobs.values()):return
  if (library.activation or {}).get('state')=='loading':return
  app['update_applying']=True
  try:
   if app.get('prompt_admissions',0):return
   listed=await bridge.rpc('session.list',scope='live',limit=200)
   if any(s.get('running') for s in listed.get('sessions',[])):return
   sys.path.insert(0,str(STACK/'creative-kit'))
   from gpu_lease import active
   if active():return
   self.state.update(state='applying')
   await bridge.broadcast({'type':'application.restarting','version':self.payload['version']})
   await asyncio.to_thread(self.launch_helper)
  except Exception as exc:self.state.update(state='error',error=str(exc)[:180])
  finally:
   if self.state['state']!='applying':app['update_applying']=False
   elif any(v.get('active') for v in bridge.live.values()):app['update_applying']=False
 def launch_helper(self):
  # An independent Python copy avoids locking libraries that the update replaces.
  helper=ROOT/'.cache/update-helper'/META['version'];python=helper/'python'
  from update_protocol import safe_target
  need=sum(f['bytes']+(safe_target(ROOT,f['path']).stat().st_size if safe_target(ROOT,f['path']).is_file() else 0) for f in self.payload['files'])+256*1024**2
  if not (helper/'complete').exists():need+=sum(p.stat().st_size for p in (ROOT/'runtime/python').rglob('*') if p.is_file())
  if shutil.disk_usage(ROOT).free<need:raise ValueError('Not enough free space for staging and rollback backups')
  if not (helper/'complete').exists():
   shutil.copytree(ROOT/'runtime/python',python,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
   (helper/'complete').write_text('ok')
  for name in ['apply_update.py','update_protocol.py']:shutil.copy2(ROOT/name,helper/name)
  env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(PYTHONDONTWRITEBYTECODE='1',TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'))
  with (ROOT/'logs/update-apply.log').open('ab') as log:
   subprocess.Popen([str(python_binary(python)),'-s',str(helper/'apply_update.py'),'--root',str(ROOT),'--manifest',str(self.package.parent/'update.json'),'--package',str(self.package)],cwd=helper,env=env,stdout=log,stderr=log,creationflags=PROCESS_FLAGS)

updates=Updates()
