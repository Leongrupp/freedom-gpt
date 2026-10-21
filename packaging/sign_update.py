"""Build a signed, allowlisted update package. The signing key stays on the publisher PC."""
import base64,datetime,json,pathlib,sys,zipfile
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'app'))
from update_protocol import canonical,managed,sha256,verify

def signing_key():
 folder=ROOT/'.private';folder.mkdir(exist_ok=True);file=folder/'release-signing-key.pem'
 if file.exists():key=serialization.load_pem_private_key(file.read_bytes(),password=None)
 else:
  key=Ed25519PrivateKey.generate();file.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
 target=ROOT/'app/update-key.pub'
 if target.exists() and target.read_text().strip()!=public:raise ValueError('Existing public key differs; explicit key rotation is required')
 target.write_text(public+'\n',encoding='ascii');return key

def build(bundle,release):
 meta=json.loads((ROOT/'app/version.json').read_text());version=meta['version'];key=signing_key();files=[]
 for file in sorted(bundle.rglob('*')):
  name=file.relative_to(bundle).as_posix()
  if file.is_file() and managed(name) and '__pycache__' not in file.parts and file.suffix!='.pyc':files.append({'path':name,'bytes':file.stat().st_size,'sha256':sha256(file)})
 baseline_file=ROOT/'.private/update-baseline.json'
 baseline=json.loads(baseline_file.read_text()) if baseline_file.exists() else None
 assets=[]
 if baseline and baseline['version']!=version:
  prior={f['path']:f['sha256'] for f in baseline['files']}
  files=[f for f in files if prior.get(f['path'])!=f['sha256']]
  archive=release/f'FreedomGPT-update-{version}.zip'
  with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as output:
   for item in files:output.write(bundle/item['path'],item['path'])
  assets.append(archive)
 else:
  baseline={'version':version,'files':files};baseline_file.write_text(json.dumps(baseline,indent=2))
  archive=release/f'FreedomGPT-{version}-Windows-x64.zip'
 payload={'schema':1,'version':version,'base_version':'1.5.0','channel':'stable','created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
   'package':{'name':archive.name,'bytes':archive.stat().st_size,'sha256':sha256(archive),
              'url':f'https://github.com/{meta["repository"]}/releases/download/v{version}/{archive.name}'},'files':files}
 envelope={'payload':payload,'signature':base64.b64encode(key.sign(canonical(payload))).decode()}
 (release/'update.json').write_text(json.dumps(envelope,ensure_ascii=False,separators=(',',':')),encoding='utf8')
 print('SIGNED_UPDATE',version,len(files),archive.stat().st_size,flush=True)
 return [*assets,release/'update.json']

def build_platform(bundle,release,target,file_mode):
 """Separate signed feeds prevent mixing native binaries across operating systems."""
 import stat
 meta=json.loads((ROOT/'app/version.json').read_text());version=meta['version'];key=signing_key();files=[]
 archive=release/f'FreedomGPT-update-{version}-{target}.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as output:
  for path in sorted(bundle.rglob('*')):
   name=path.relative_to(bundle).as_posix()
   if not path.is_file() or not managed(name) or '__pycache__' in path.parts or path.suffix=='.pyc':continue
   files.append({'path':name,'bytes':path.stat().st_size,'sha256':sha256(path)})
   entry=zipfile.ZipInfo(name);entry.create_system=3;entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=(stat.S_IFREG|file_mode(path,bundle))<<16
   with output.open(entry,'w') as destination,path.open('rb') as source:
    import shutil
    shutil.copyfileobj(source,destination,512*1024)
 payload={'schema':1,'version':version,'base_version':'1.5.0','platform':target,'channel':'stable','created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'package':{'name':archive.name,'bytes':archive.stat().st_size,'sha256':sha256(archive),'url':f'https://github.com/{meta["repository"]}/releases/download/v{version}/{archive.name}'},'files':files}
 envelope={'payload':payload,'signature':base64.b64encode(key.sign(canonical(payload))).decode()}
 public=(ROOT/'app/update-key.pub').read_text();verify(envelope,public,expected_platform=target)
 feed=release/f'update-{target}.json';feed.write_text(json.dumps(envelope,separators=(',',':')),encoding='utf-8')
 return [archive,feed]
if __name__=='__main__':signing_key();print('PUBLIC_KEY_READY')
