"""Repair private Python wheels offline before importing the application stack."""
import hashlib,importlib,json,pathlib,re,subprocess,sys
MODULES=('psutil','requests','aiohttp','PIL.Image','cryptography','pydantic','ruamel.yaml','openai','websockets','rich','httpx','mcp','croniter','dotenv')
DISTRIBUTIONS={'PIL.Image':'pillow','ruamel.yaml':'ruamel-yaml','dotenv':'python-dotenv'}
def missing():
 result=[]
 for name in MODULES:
  try:importlib.import_module(name)
  except (ImportError,OSError):result.append(name)
 return result
def ensure(root):
 root=pathlib.Path(root);errors=missing()
 if not errors:return {'ready':True,'repaired':False}
 if not pathlib.Path(sys.executable).resolve().is_relative_to((root/'runtime/python').resolve()):raise RuntimeError('Use the bundled Freedom GPT Python to repair this installation.')
 wheels=root/'runtime/wheels';manifest=wheels/'manifest.json';requirements=wheels/'requirements.lock'
 if not manifest.is_file() or not requirements.is_file():raise RuntimeError('В сборке отсутствуют Python-компоненты: '+', '.join(errors)+'. Восстановите runtime из установщика. / Restore runtime from the installer.')
 from platform_support import file_lock
 with file_lock(root/'.tmp/python-repair.lock'):
  for item in json.loads(manifest.read_text(encoding='utf-8')):
   file=wheels/item['file']
   if file.parent!=wheels or not file.is_file() or file.stat().st_size!=item['bytes'] or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Bundled wheel integrity verification failed: '+file.name)
  (root/'logs').mkdir(parents=True,exist_ok=True)
  normalize=lambda value:re.sub(r'[-_.]+','-',value).lower()
  wanted={normalize(DISTRIBUTIONS.get(name,name)) for name in errors}
  packages=[line.strip() for line in requirements.read_text(encoding='utf-8').splitlines() if '==' in line and normalize(line.split('==',1)[0]) in wanted]
  if len(packages)!=len(wanted):raise RuntimeError('Missing pinned repair requirements: '+', '.join(errors))
  with (root/'logs/python-repair.log').open('ab') as log:
   result=subprocess.run([sys.executable,'-B','-s','-m','pip','install','--no-index','--no-deps','--force-reinstall','--no-compile','--find-links',str(wheels),*packages],cwd=root,stdout=log,stderr=log)
  if result.returncode or missing():raise RuntimeError('Automatic offline repair failed. See logs/python-repair.log.')
 return {'ready':True,'repaired':True}
