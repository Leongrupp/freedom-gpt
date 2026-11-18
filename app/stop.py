"""Stop this installation's owned background services before unplugging its SSD."""
import bootstrap
import json,pathlib,time,psutil
from bootstrap import ROOT,STACK,read
from library import library
import urllib.request
def video_api(path,value=None,token=None):
 headers={'Content-Type':'application/json'}
 if token:headers['X-Freedom-Token']=token
 request=urllib.request.Request('http://127.0.0.1:'+str(bootstrap.config()['ui_port'])+'/api/'+path,data=json.dumps(value).encode() if value is not None else None,headers=headers)
 with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)
try:
 state=video_api('video');job=state.get('current') or {}
 if job.get('state') in {'queued','loading','generating','restoring'}:
  token=video_api('bootstrap')['token'];video_api('video/cancel',{},token)
  for _ in range(180):
   if (video_api('video').get('current') or {}).get('state') not in {'queued','loading','generating','restoring'}:break
   time.sleep(1)
  else:raise RuntimeError('Video is still releasing GPU resources. Keep the disk connected and retry Stop-FreedomGPT.cmd.')
except (urllib.error.URLError,TimeoutError):pass
from ui_lifecycle import request_stop
request_stop()
if not bootstrap.PRIVATE:library.stop_model()
record=read(ROOT/'.tmp/server-process.json',{})
def wait_stopped(process,timeout=15):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  try:
   if not process.is_running() or process.status()==psutil.STATUS_ZOMBIE:return
   process.wait(timeout=.2);return
  except psutil.NoSuchProcess:return
  except psutil.TimeoutExpired:pass
 raise RuntimeError('Freedom GPT server did not stop. Keep the disk connected and retry.')
try:
 process=psutil.Process(record['pid'])
 if abs(process.create_time()-record['created'])<1 and str(ROOT/'server.py').lower() in ' '.join(process.cmdline()).lower():process.terminate();wait_stopped(process)
except (KeyError,psutil.NoSuchProcess):pass
from hermes_cli.gateway import stop_profile_gateway
stop_profile_gateway()
print('Freedom GPT background services stopped. Close its browser window before safely ejecting the disk.')
