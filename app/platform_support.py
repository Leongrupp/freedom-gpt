"""OS boundaries for a private, relocatable installation; no global changes."""
import json,math,os,pathlib,platform,shutil,subprocess,sys

WINDOWS=sys.platform=='win32'
MAC=sys.platform=='darwin'
PROCESS_FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)
GIB=1024**3

def python_binary(folder,windowless=False):
 folder=pathlib.Path(folder)
 if WINDOWS:return folder/('pythonw.exe' if windowless and (folder/'pythonw.exe').exists() else 'python.exe')
 return folder/'bin/python3'

def file_lock(path):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 handle=path.open('a+b');handle.seek(0,2)
 if not handle.tell():handle.write(b'0');handle.flush()
 handle.seek(0)
 try:
  if WINDOWS:
   import msvcrt
   msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
  else:
   import fcntl
   fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 except OSError:handle.close();raise
 return handle

def command(args,timeout=10):
 return subprocess.check_output(args,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=PROCESS_FLAGS).strip()

def vulkan_gpus(memory):
 """Read Vulkan device-local heaps through the installed OS loader."""
 import ctypes as c
 try:
  lib=c.CDLL('vulkan-1.dll' if WINDOWS else 'libvulkan.so.1')
  class Create(c.Structure):_fields_=[('type',c.c_uint32),('next',c.c_void_p),('flags',c.c_uint32),('app',c.c_void_p),('layers',c.c_uint32),('layer_names',c.c_void_p),('extensions',c.c_uint32),('extension_names',c.c_void_p)]
  class MemoryType(c.Structure):_fields_=[('flags',c.c_uint32),('heap',c.c_uint32)]
  class Heap(c.Structure):_fields_=[('size',c.c_uint64),('flags',c.c_uint32)]
  class Memory(c.Structure):_fields_=[('type_count',c.c_uint32),('types',MemoryType*32),('heap_count',c.c_uint32),('heaps',Heap*16)]
  lib.vkCreateInstance.argtypes=[c.POINTER(Create),c.c_void_p,c.POINTER(c.c_void_p)];lib.vkCreateInstance.restype=c.c_int
  lib.vkEnumeratePhysicalDevices.argtypes=[c.c_void_p,c.POINTER(c.c_uint32),c.POINTER(c.c_void_p)];lib.vkEnumeratePhysicalDevices.restype=c.c_int
  lib.vkGetPhysicalDeviceProperties.argtypes=[c.c_void_p,c.c_void_p];lib.vkGetPhysicalDeviceMemoryProperties.argtypes=[c.c_void_p,c.POINTER(Memory)]
  lib.vkDestroyInstance.argtypes=[c.c_void_p,c.c_void_p]
  instance=c.c_void_p();info=Create(type=1)
  if lib.vkCreateInstance(c.byref(info),None,c.byref(instance)):return []
  try:
   count=c.c_uint32()
   if lib.vkEnumeratePhysicalDevices(instance,c.byref(count),None) or not 0<count.value<=32:return []
   devices=(c.c_void_p*count.value)();lib.vkEnumeratePhysicalDevices(instance,c.byref(count),devices);result=[]
   for device in devices:
    data=c.create_string_buffer(4096);lib.vkGetPhysicalDeviceProperties(device,data)
    kind=c.c_uint32.from_buffer(data,16).value
    if kind not in {1,2}:continue
    name=data.raw[20:276].split(b'\0',1)[0].decode('utf-8','replace');props=Memory();lib.vkGetPhysicalDeviceMemoryProperties(device,c.byref(props))
    total=sum(props.heaps[i].size for i in range(min(props.heap_count,16)) if props.heaps[i].flags&1)
    if kind==1:total=min(total,memory.total*.65)
    result.append({'name':name+' · Vulkan','vram_gb':round(total/GIB,1),'free_gb':round(min(total*.8,memory.available*.8 if kind==1 else total*.8)/GIB,1),'vulkan':True,'cuda':False,'unified':kind==1,'free_estimate':True,'backend':'vulkan'})
   return result
  finally:lib.vkDestroyInstance(instance,None)
 except (OSError,AttributeError,ValueError):return []

def hardware(root):
 import psutil
 root=pathlib.Path(root);memory=psutil.virtual_memory();gpus=[];notes=[];cpu=platform.processor() or platform.machine()
 try:
  for line in command(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'],8).splitlines():
   name,total,free,driver=[part.strip() for part in line.split(',')]
   gpus.append({'name':name,'vram_gb':round(float(total)/1024,1),'free_gb':round(float(free)/1024,1),'driver':driver,'cuda':True,'backend':'cuda'})
 except (OSError,subprocess.SubprocessError,ValueError):pass
 if WINDOWS:
  try:
   script="[pscustomobject]@{cpu=(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name);gpu=@(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)} | ConvertTo-Json -Compress"
   info=json.loads(command(['powershell.exe','-NoProfile','-Command',script],15));cpu=info['cpu']
   if not gpus:gpus=[{'name':name,'vram_gb':None,'cuda':False,'backend':'cpu'} for name in info.get('gpu',[])]
  except (OSError,ValueError,subprocess.SubprocessError):pass
 elif MAC:
  try:cpu=command(['sysctl','-n','machdep.cpu.brand_string'])
  except (OSError,subprocess.SubprocessError):pass
  if platform.machine() in {'arm64','aarch64'}:
   budget=round(min(memory.total*.65,memory.available*.8)/GIB,1)
   gpus=[{'name':cpu+' · Apple Metal','vram_gb':round(memory.total*.65/GIB,1),'free_gb':max(0,budget),'cuda':False,'metal':True,'unified':True,'backend':'metal'}]
 else:
  try:
   for line in pathlib.Path('/proc/cpuinfo').read_text().splitlines():
    if line.startswith('model name'):cpu=line.split(':',1)[1].strip();break
  except OSError:pass
  if not gpus:
   try:
    text=command(['lspci'])
    gpus=[{'name':line.split(': ',1)[-1],'vram_gb':None,'cuda':False,'backend':'cpu'} for line in text.splitlines() if any(s in line for s in ['VGA compatible','3D controller','Display controller'])]
   except (OSError,subprocess.SubprocessError):pass
 if not MAC and not any(g.get('cuda') for g in gpus):gpus=vulkan_gpus(memory) or gpus
 accelerated=any(g.get('cuda') or g.get('metal') or g.get('vulkan') for g in gpus)
 if not accelerated:notes.append('GPU-ускорение не обнаружено. Доступен CPU; скорость будет ниже.')
 return {'cpu':cpu,'physical_cores':psutil.cpu_count(logical=False),'threads':psutil.cpu_count(),
  'ram_gb':math.ceil(memory.total/GIB),'ram_available_gb':round(memory.available/GIB,1),'gpus':gpus,
  'vram_gb':max((g.get('vram_gb') or 0 for g in gpus),default=0),'cuda':any(g.get('cuda') for g in gpus),
  'metal':any(g.get('metal') for g in gpus),'vulkan':any(g.get('vulkan') for g in gpus),'gpu_accelerated':accelerated,'unified_memory':any(g.get('unified') for g in gpus),
  'free_disk_gb':round(shutil.disk_usage(root).free/GIB,1),'notes':notes,'storage':str(root),'estimate_only':True,
  'os':platform.system(),'os_version':platform.release(),'architecture':platform.machine()}

def native_binary(root,kind,backend=None):
 root=pathlib.Path(root);name=('llama-server' if kind=='llama' else 'sd-cli')+('.exe' if WINDOWS else '')
 base=root/'runtime'/kind
 backend=backend or ('metal' if MAC and platform.machine() in {'arm64','aarch64'} else 'cpu')
 manifest=root/'runtime/native.json'
 if manifest.is_file():
  engines=json.loads(manifest.read_text(encoding='utf-8')).get('engines',{})
  relative=engines.get(kind,{}).get(backend)
  if not relative:raise FileNotFoundError('Backend not bundled: '+kind+' / '+backend)
  candidate=(root/relative).resolve()
  if not candidate.is_relative_to((root/'runtime').resolve()) or not candidate.is_file():raise FileNotFoundError('Missing bundled engine: '+kind+' / '+backend)
  return candidate
 for directory in [base/backend,base]:
  direct=directory/name
  if direct.is_file():return direct
  matches=sorted(directory.rglob(name)) if directory.exists() else []
  if matches:return matches[0]
 raise FileNotFoundError('Не найден локальный движок: '+kind+' / '+backend)

def native_environment(root,engine):
 root=pathlib.Path(root);env=os.environ.copy();engine=pathlib.Path(engine)
 paths=[str(engine.parent),str(engine.parent/'lib'),str(engine.parent.parent/'lib'),str(root/'runtime/system/lib'),str(root/'runtime/cuda')]
 env['PATH']=os.pathsep.join([*paths,env.get('PATH','')])
 if not WINDOWS:
  key='DYLD_LIBRARY_PATH' if MAC else 'LD_LIBRARY_PATH'
  env[key]=os.pathsep.join([*paths,env.get(key,'')])
 return env

def open_browser(root,url):
 if WINDOWS:
  paths=[pathlib.Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',pathlib.Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe',pathlib.Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe']
  browser=next((p for p in paths if p.is_file()),None)
  if browser:
   subprocess.Popen([str(browser),'--app='+url,'--user-data-dir='+str(pathlib.Path(root)/'.cache/browser'),'--no-first-run','--no-default-browser-check','--disable-background-networking','--window-size=1480,960']);return
 import webbrowser
 if not webbrowser.open(url):print('Freedom GPT: '+url,flush=True)

def show_error(message):
 if WINDOWS:
  import ctypes
  ctypes.windll.user32.MessageBoxW(None,str(message),'Freedom GPT',0x10)
 else:
  print('Freedom GPT: '+str(message),file=sys.stderr,flush=True)
  if MAC:
   # A fixed script receives the error as argv, never as executable AppleScript.
   script='on run argv\ndisplay alert "Freedom GPT" message (item 1 of argv) as critical\nend run'
   subprocess.run(['osascript','-e',script,str(message)],check=False)
