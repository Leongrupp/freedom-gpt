"""Repair private Python wheels offline before importing the application stack."""
import hashlib,importlib,json,pathlib,re,subprocess,sys,site,datetime
MODULES=('psutil','requests','aiohttp','PIL.Image','cryptography','pydantic','ruamel.yaml','openai','websockets','rich','httpx','mcp','croniter','dotenv')+ (('pywintypes','win32api','win32job') if sys.platform=='win32' else ())
DISTRIBUTIONS={'PIL.Image':'pillow','ruamel.yaml':'ruamel-yaml','dotenv':'python-dotenv','pywintypes':'pywin32','win32api':'pywin32','win32job':'pywin32'}
def failures():
 result={}
 for name in MODULES:
  try:importlib.import_module(name)
  except (ImportError,OSError) as exc:result[name]=type(exc).__name__+': '+str(exc)
 return result

def missing():
 return list(failures())
def ensure(root):
 root=pathlib.Path(root);errors=missing()
 if not errors:return {'ready':True,'repaired':False}
 if not pathlib.Path(sys.executable).resolve().is_relative_to((root/'runtime/python').resolve()):raise RuntimeError('Use the bundled Freedom GPT Python to repair this installation.')
 wheels=root/'runtime/wheels';manifest=wheels/'manifest.json';requirements=wheels/'requirements.lock'
 if not manifest.is_file() or not requirements.is_file():raise RuntimeError('В сборке отсутствуют Python-компоненты: '+', '.join(errors)+'. Восстановите runtime из установщика. / Restore runtime from the installer.')
 from platform_support import file_lock
 with file_lock(root/'.tmp/python-repair.lock'):
  errors=missing()
  if not errors:return {'ready':True,'repaired':False}
  for item in json.loads(manifest.read_text(encoding='utf-8')):
   file=wheels/item['file']
   if file.parent!=wheels or not file.is_file() or file.stat().st_size!=item['bytes'] or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Bundled wheel integrity verification failed: '+file.name)
  (root/'logs').mkdir(parents=True,exist_ok=True)
  normalize=lambda value:re.sub(r'[-_.]+','-',value).lower()
  wanted={normalize(DISTRIBUTIONS.get(name,name)) for name in errors}
  packages=[line.strip() for line in requirements.read_text(encoding='utf-8').splitlines() if '==' in line and normalize(line.split('==',1)[0]) in wanted]
  if len(packages)!=len(wanted):raise RuntimeError('Missing pinned repair requirements: '+', '.join(errors))
  with (root/'logs/python-repair.log').open('ab') as log:
   log.write(('\n'+datetime.datetime.now().isoformat()+' Import failures: '+json.dumps(failures(),ensure_ascii=False)+'\n').encode('utf-8'));log.flush()
   result=subprocess.run([sys.executable,'-B','-s','-m','pip','install','--no-index','--no-deps','--force-reinstall','--no-compile','--find-links',str(wheels),*packages],cwd=root,stdout=log,stderr=log,timeout=180)
   # pywin32 installs a .pth bootstrap for its DLL and module search paths.
   importlib.invalidate_caches();site.addsitedir(str(root/'runtime/python/Lib/site-packages'))
   remaining=failures()
   fresh=subprocess.run([sys.executable,'-B','-s','-c','import importlib; '+ '; '.join('importlib.import_module('+repr(name)+')' for name in MODULES)],cwd=root,stdout=log,stderr=log,timeout=60)
   log.write(('Post-repair failures: '+json.dumps(remaining,ensure_ascii=False)+'; fresh_process_exit='+str(fresh.returncode)+'\n').encode('utf-8'))
  if result.returncode or remaining or fresh.returncode:raise RuntimeError('Не удалось восстановить компоненты запуска. Причина записана в logs/python-repair.log.')
 return {'ready':True,'repaired':True}
