"""Signed release protocol shared by the publisher and the desktop updater."""
import base64,hashlib,json,pathlib,re,stat,platform,sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT_FILES=frozenset({'bootstrap.py','launch.py','stop.py','server.py','library.py','engine_supervisor.py','gguf_info.py',
 'generate-image-request.py','init-project-memory.py','updater.py','apply_update.py','update_protocol.py','version.json',
 'catalog.json','freedom.ico','FreedomGPT.exe','Start-FreedomGPT.cmd','Stop-FreedomGPT.cmd','Start-FreedomGPT.sh','Stop-FreedomGPT.sh','README.txt','freedom-bundle.json'})
PREFIXES=('dist/','public/','licenses/','runtime/','stack/creative-kit/engine/',
 'stack/hermes-runtime/plugins/coding-continuity/','stack/hermes-runtime/plugins/image_gen/local-qwen-image/',
 'stack/hermes-runtime/skills/coding-continuity/')
STACK_FILES={'stack/creative-kit/image-tool.py','stack/creative-kit/gpu_lease.py'}
RESERVED={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')

def target_platform():
 arch='arm64' if platform.machine().lower() in {'aarch64','arm64'} else 'x64'
 return ('windows' if sys.platform=='win32' else 'macos' if sys.platform=='darwin' else 'ubuntu')+'-'+arch
def version(value):
 if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d+\.\d+',value):raise ValueError('Invalid version')
 return tuple(int(v) for v in value.split('.'))
def sha256(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as f:
  for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
 return h.hexdigest()
def managed(name):
 if not isinstance(name,str) or '\\' in name or ':' in name or name.startswith('/') or '\0' in name:return False
 parts=name.split('/')
 if any(not p or p in {'.','..'} or p.rstrip('. ')!=p or p.split('.')[0].upper() in RESERVED for p in parts):return False
 return name in ROOT_FILES or name in STACK_FILES or name.startswith(PREFIXES)
def verify(envelope,key,current=None,expected_platform=None):
 if not isinstance(envelope,dict) or set(envelope)!={'payload','signature'}:raise ValueError('Invalid update envelope')
 payload=envelope['payload'];signature=base64.b64decode(envelope['signature'],validate=True)
 Ed25519PublicKey.from_public_bytes(base64.b64decode(key.strip(),validate=True)).verify(signature,canonical(payload))
 if payload.get('platform','windows-x64')!=(expected_platform or target_platform()):raise ValueError('Update is for another operating system or architecture')
 version(payload['version'])
 if current and version(payload['version'])<=version(current):return None
 if current and version(current)<version(payload.get('base_version','1.2.0')):raise ValueError('Install the current full release before automatic updates')
 if payload.get('channel')!='stable' or payload.get('schema')!=1:raise ValueError('Unsupported update channel')
 package=payload['package']
 if not isinstance(package['bytes'],int) or not 0<package['bytes']<8*1024**3:raise ValueError('Invalid package size')
 if not re.fullmatch('[0-9a-f]{64}',package['sha256']):raise ValueError('Invalid package digest')
 files=payload['files'];seen=set()
 if not isinstance(files,list) or not 0<len(files)<100000:raise ValueError('Invalid file manifest')
 for item in files:
  name=item['path'];normalized=name.casefold()
  if not managed(name) or normalized in seen:raise ValueError('Unsafe or duplicate update path')
  if not isinstance(item['bytes'],int) or not 0<=item['bytes']<4*1024**3:raise ValueError('Invalid file size')
  if not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError('Invalid file digest')
  seen.add(normalized)
 return payload
def safe_target(root,name):
 if not managed(name):raise ValueError('Protected application path')
 root=pathlib.Path(root).resolve();target=root.joinpath(*name.split('/'))
 if not target.resolve().is_relative_to(root):raise ValueError('Path outside installation')
 for parent in [target,*target.parents]:
  if parent==root:break
  if parent.exists():
   info=parent.lstat()
   if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Reparse path refused')
 return target
