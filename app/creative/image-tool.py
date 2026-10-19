"""Local Qwen Image generation with automatic, crash-safe GPU handoff."""
import argparse,contextlib,json,os,pathlib,subprocess,sys,time,uuid,urllib.request
import bootstrap
from gpu_lease import acquire,add_child,release,active
from platform_support import PROCESS_FLAGS,file_lock,native_binary,native_environment,hardware
ROOT=pathlib.Path(__file__).resolve().parent;STACK=ROOT.parent
MODEL=ROOT/'models/qwen-image-2.1-turbo-Q5_K_M.gguf'
ENCODER=ROOT/'models/Qwen3-VL-8B-Instruct-UD-Q4_K_XL.gguf'
VAE=ROOT/'models/qwen_image_2.1_vae_bf16.safetensors'
def engine():
 app=ROOT.parents[1];device=hardware(app)
 backend='metal' if device.get('metal') else ('cuda' if sys.platform=='win32' else 'vulkan') if device.get('cuda') else 'vulkan' if device.get('vulkan') else 'cpu'
 return native_binary(app,'sd',backend)

def http(path):
 with urllib.request.urlopen('http://127.0.0.1:'+str(json.loads((STACK/'server-settings.json').read_text())['port'])+path,timeout=3) as r:return json.load(r)
def ready():
 try:return http('/health').get('status')=='ok'
 except Exception:return False
def wait_ready(timeout=240):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  if ready():return
  time.sleep(1)
 raise RuntimeError('Coder failed to return; inspect main logs')
def check_paths():return all(p.is_file() for p in [MODEL,ENCODER,VAE,engine()])
@contextlib.contextmanager
def gpu_handoff():
 try:lock=file_lock(ROOT/'.tmp/image-job.lock')
 except OSError:raise RuntimeError('Image job already running; wait for it to finish')
 lease=None
 try:
  had_coder=ready()
  if not had_coder:
   lease=acquire();yield lease;return
  deadline=time.monotonic()+120
  while True:
   slots=http('/slots')
   if slots and all(not s.get('is_processing',True) for s in slots):break
   if time.monotonic()>deadline:raise RuntimeError('Coder is busy; image job deferred')
   time.sleep(1)
  lease=acquire();deadline=time.monotonic()+45
  # The supervisor owns and stops only its own server process.
  while ready():
   if time.monotonic()>deadline:raise RuntimeError('Supervisor did not release GPU; image generation cancelled')
   time.sleep(.5)
  time.sleep(2)
  yield lease
 finally:
  if lease:
   release(lease)
   if had_coder:wait_ready()
  lock.close()
def generate(prompt,*,aspect_ratio='square',output=None,width=None,height=None,seed=42):
 if not check_paths():raise RuntimeError('Image weights/engine are not downloaded and verified yet')
 dimensions={'square':(1024,1024),'landscape':(1216,832),'portrait':(832,1216)}
 w,h=dimensions.get(aspect_ratio,dimensions['square']);w=width or w;h=height or h
 if any(n<256 or n>1536 or n%32 for n in [w,h]) or w*h>1536*1024:raise ValueError('Dimensions must be multiples of 32, 256..1536, at most 1.57 MP')
 job=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
 output=pathlib.Path(output).resolve() if output else ROOT/'output/images'/job/'image.png'
 if not output.is_relative_to(ROOT.parents[1].resolve()):raise ValueError('Output must stay inside Freedom GPT')
 if output.exists():raise FileExistsError('Refusing to overwrite '+str(output))
 output.parent.mkdir(parents=True,exist_ok=True);logpath=ROOT/'logs'/('image-'+job+'.log')
 env=native_environment(ROOT.parents[1],engine());env.update(TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),TMPDIR=str(ROOT/'.tmp'))
 # Keep text encoding and VAE on CPU. GPU is dedicated to denoising.
 args=[str(engine()),'--diffusion-model',str(MODEL),'--llm',str(ENCODER),'--vae',str(VAE),
       '-p',prompt,'-W',str(w),'-H',str(h),'--steps','8','--cfg-scale','1.0','--sampling-method','euler',
       '--sigmas','qwen-image-2.1-turbo','--diffusion-fa','--offload-to-cpu','--vae-tiling','-t','12','-s',str(seed),'-o',str(output)]
 started=time.monotonic();child=None
 with gpu_handoff() as lease:
  try:
   with logpath.open('wb') as log:
    child=subprocess.Popen(args,cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=PROCESS_FLAGS)
    add_child(lease,child.pid)
    code=child.wait(timeout=1800)
   if code:raise RuntimeError(f'Image engine exited {code}; log: {logpath}')
   if not output.is_file():
    variants=list(output.parent.glob(output.stem+'*.png'))
    if len(variants)==1:output=variants[0]
    else:raise RuntimeError('Engine produced no PNG; inspect '+str(logpath))
  finally:
   if child and child.poll() is None:child.terminate();child.wait(timeout=20)
 report=dict(success=True,image=str(output),model=MODEL.name,seconds=round(time.monotonic()-started,2),width=w,height=h,log=str(logpath),coder_restored=ready())
 (output.parent/'generation.json').write_text(json.dumps(report,indent=2),encoding='utf8');return report
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True);s.add_parser('status');g=s.add_parser('generate');g.add_argument('--prompt',required=True);g.add_argument('--aspect',choices=['square','landscape','portrait'],default='square');g.add_argument('--output');g.add_argument('--width',type=int);g.add_argument('--height',type=int);g.add_argument('--seed',type=int,default=42)
 a=p.parse_args()
 if a.action=='status':print(json.dumps(dict(installed=check_paths(),coder_ready=ready(),image_job_active=active(),models=[dict(path=str(f),bytes=f.stat().st_size if f.exists() else 0) for f in [MODEL,ENCODER,VAE]])))
 else:print(json.dumps(generate(a.prompt,aspect_ratio=a.aspect,output=a.output,width=a.width,height=a.height,seed=a.seed)))
if __name__=='__main__':main()
