"""Cross-process GPU ownership with kernel locks and PID reuse protection."""
import json,os,pathlib,time,uuid
import psutil
from platform_support import file_lock
ROOT=pathlib.Path(__file__).resolve().parent.parent;LEASE=ROOT/'.tmp/image-gpu-lease.json';HELD={}
def stamp(pid):
 try:return psutil.Process(int(pid)).create_time()
 except (ValueError,psutil.NoSuchProcess,psutil.AccessDenied):return None
def read():
 try:return json.loads(LEASE.read_text(encoding='utf-8'))
 except (OSError,ValueError):return None
def active():
 data=read()
 if not data or data.get('expires',0)<time.time():return False
 return any(p.get('stamp') is not None and stamp(p['pid'])==p['stamp'] for p in data.get('processes',[]))
def write(data):
 LEASE.parent.mkdir(parents=True,exist_ok=True);temp=LEASE.with_suffix('.new');temp.write_text(json.dumps(data),encoding='utf-8');os.replace(temp,LEASE)
def acquire():
 handle=file_lock(ROOT/'.tmp/image-gpu-lease.lock')
 try:
  if active():raise RuntimeError('Another generation already owns the GPU')
  data={'token':uuid.uuid4().hex,'expires':time.time()+3600,'processes':[{'pid':os.getpid(),'stamp':stamp(os.getpid())}]}
  write(data);HELD[data['token']]=handle;return data
 except Exception:handle.close();raise
def add_child(data,pid):data['processes'].append({'pid':pid,'stamp':stamp(pid)});write(data)
def release(data):
 current=read()
 if current and current.get('token')==data['token']:LEASE.unlink(missing_ok=True)
 handle=HELD.pop(data['token'],None)
 if handle:handle.close()
