"""Build a complete private-runtime POSIX app from reviewed release assets."""
import argparse,configparser,hashlib,json,os,pathlib,plistlib,shutil,stat,struct,subprocess,sys,tarfile,time,zipfile
from archive_utils import unpack,safe_name
ROOT=pathlib.Path(__file__).resolve().parent.parent;APP=ROOT/'app';CACHE=ROOT/'.cache/platforms'
VERSION=json.loads((APP/'version.json').read_text())['version']
MODULES=['discovery.py','video.py','platform_support.py','preflight.py','system_check.py']
ROOT_FILES=['bootstrap.py','launch.py','stop.py','server.py','library.py','engine_supervisor.py','generate-image-request.py','init-project-memory.py','gguf_info.py','updater.py','apply_update.py','update_protocol.py','version.json','update-key.pub','catalog.json','README.txt','freedom.ico']
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','*.pdb','__editable__*','direct_url.json')

def sha(path):
 value=hashlib.sha256()
 with path.open('rb') as source:
  for block in iter(lambda:source.read(4*1024**2),b''):value.update(block)
 return value.hexdigest()
def copy(source,target):target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def cached_copy(source,target):
 try:
  a=os.stat(source);b=os.stat(target)
  if a.st_size==b.st_size and a.st_mtime_ns==b.st_mtime_ns:return target
 except FileNotFoundError:pass
 return shutil.copy2(source,target)

def tree(source,target):shutil.copytree(source,target,dirs_exist_ok=True,ignore=IGNORE,copy_function=cached_copy)

def unpack_component(target,kind,item):
 archive=CACHE/'downloads'/item['file']
 if not archive.is_file() or archive.stat().st_size!=item['bytes'] or sha(archive)!=item['sha256']:raise ValueError('Complete verified runtime required: '+item['file'])
 folder=CACHE/'unpacked'/target/kind;unpack(archive,folder);return folder

def wheels(target,app):
 folder=CACHE/'wheels'/target;manifest=json.loads((folder/'manifest.json').read_text());site=app/'runtime/python/lib/python3.14/site-packages';entrypoints={}
 for item in manifest:
  path=folder/item['file']
  if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('Wheel digest mismatch: '+path.name)
  copy(path,app/'runtime/wheels'/path.name)
  with zipfile.ZipFile(path) as archive:
   for entry in archive.infolist():
    if entry.is_dir():continue
    name=safe_name(entry.filename);parts=name.split('/')
    if '.data' in parts[0]:
     if len(parts)<3 or parts[1] not in {'purelib','platlib'}:continue
     name='/'.join(parts[2:])
    destination=site/name;destination.parent.mkdir(parents=True,exist_ok=True)
    with archive.open(entry) as source,destination.open('wb') as output:shutil.copyfileobj(source,output,1024**2)
    if name.endswith('.dist-info/entry_points.txt'):
     config=configparser.ConfigParser(interpolation=None);config.read_string(destination.read_text())
     if config.has_section('console_scripts'):entrypoints.update({k:v.split(' [',1)[0].strip() for k,v in config.items('console_scripts')})
 copy(folder/'manifest.json',app/'runtime/wheels/manifest.json');copy(ROOT/'packaging/requirements-portable.lock',app/'runtime/wheels/requirements.lock')
 entrypoints['hermes']='hermes_cli.main:main'
 entrypoints.update({name:'pip._internal.cli.main:main' for name in ['pip','pip3','pip3.14']})
 metadata=site/'hermes_agent-0.0.0.dist-info';metadata.mkdir(parents=True,exist_ok=True)
 (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: hermes-agent\nVersion: 0.0.0\nLicense: MIT\n',encoding='utf-8')
 (app/'runtime/python/lib/freedom-entrypoints.json').write_text(json.dumps(entrypoints,indent=2))
 copy(ROOT/'packaging/entrypoint.py',app/'runtime/python/lib/freedom-entrypoint.py')
 for name in entrypoints:
  if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.' for c in name):raise ValueError('Invalid console name')
  script=app/'runtime/python/bin'/name
  script.write_text('#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$HERE/python3" -B -s "$HERE/../lib/freedom-entrypoint.py" '+name+' "$@"\n',encoding='utf-8',newline='\n')

def mode(path,root):
 name=path.relative_to(root).as_posix()
 if name.endswith(('.sh','.command')) or name.startswith(('runtime/python/bin/','runtime/node/bin/')) or name.startswith(('runtime/llama/','runtime/sd/')) and path.suffix not in {'.txt','.md','.json'}:return 0o755
 return 0o644

def manifest(app,target):
 forbidden=[];files=[]
 for path in sorted(app.rglob('*')):
  if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
  relative=path.relative_to(app).as_posix()
  if relative=='bundle-manifest.json':continue
  if path.name in {'.env','auth.json','state.db','interface.sqlite','private-runtime.json','install_id'} or path.suffix in {'.gguf','.safetensors'}:forbidden.append(relative)
  files.append({'path':relative,'bytes':path.stat().st_size,'sha256':sha(path),'mode':mode(path,app)})
 if forbidden:raise ValueError('Personal/model files in public bundle: '+str(forbidden[:10]))
 result={'schema':1,'version':VERSION,'platform':target,'files':files,'personal_data_included':False,'model_weights_included':False}
 (app/'bundle-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result

def prepare(target,donor):
 folder=ROOT/'build/platforms'/VERSION/target;app=folder/'App';app.mkdir(parents=True,exist_ok=True)
 for name in ROOT_FILES:copy(APP/name,app/name)
 for name in MODULES:copy(APP/name,app/'runtime/freedom'/name)
 copy(ROOT/'packaging/portable_install.py',app/'runtime/freedom/portable_install.py')
 for name in ['dist','public']:tree(APP/name,app/name)
 for name in ['runtime/hermes','licenses','stack/hermes-runtime/plugins','stack/hermes-runtime/skills']:
  tree(donor/name,app/name)
 for name in ['gpu_lease.py','image-tool.py']:copy(APP/'creative'/name,app/'stack/creative-kit'/name)
 (app/'stack/hermes-runtime/SOUL.md').write_text('You are Freedom GPT, a local assistant. Use the installed tools honestly. Preserve project decisions and files. Local models do not need an internet connection after installation.\n',encoding='utf-8')
 lock=json.loads((ROOT/'packaging/native-lock.json').read_text());components=lock['targets'][target]
 py=unpack_component(target,'python',components['python']);tree(py/'python',app/'runtime/python')
 wheels(target,app)
 engines={'llama':{},'sd':{}}
 for kind,item in components.items():
  if kind=='python':continue
  source=unpack_component(target,kind,item)
  if kind=='node':
   parent=next(p for p in source.iterdir() if p.is_dir());tree(parent,app/'runtime/node');continue
  if kind=='cuda-runtime':
   for file in source.rglob('*'):
    if file.is_file() and '.so' in file.name:copy(file,app/'runtime/cuda'/file.name)
   continue
  family,backend=kind.split('-',1);destination=app/'runtime'/family/backend;tree(source,destination)
  binary=next(destination.rglob('llama-server' if family=='llama' else 'sd-cli'))
  engines[family][backend]=binary.relative_to(app).as_posix()
  # The Metal builds include their CPU backend; ngl=0 is a supported fallback.
  if backend=='metal':engines[family]['cpu']=engines[family][backend]
 if target=='ubuntu-x64':
  lib=CACHE/'system/ubuntu-x64';copy(lib/'libgomp.so.1',app/'runtime/system/lib/libgomp.so.1');copy(lib/'libgomp-COPYRIGHT.txt',app/'licenses/GCC-libgomp-copyright.txt')
 native={'platform':target,'engines':engines,'upstream':components};(app/'runtime/native.json').write_text(json.dumps(native,indent=2));copy(ROOT/'packaging/native-lock.json',app/'runtime/native-lock.json')
 for source,name in [('posix-launch.sh','Start-FreedomGPT.sh'),('posix-stop.sh','Stop-FreedomGPT.sh'),('posix-install.sh','Install-FreedomGPT.sh')]:copy(ROOT/'packaging'/source,app/name)
 skill=app/'stack/hermes-runtime/skills/coding-continuity/SKILL.md'
 if skill.is_file():
  text=skill.read_text(encoding='utf-8');start=text.find('```powershell');end=text.find('```',start+3)
  if start>=0 and end>=0:text=text[:start]+'```sh\n"$FREEDOM_ROOT/runtime/python/bin/python3" "$FREEDOM_ROOT/init-project-memory.py" --project ACTUAL_PROJECT_PATH --session ACTUAL_SESSION_ID\n```'+text[end+3:]
  skill.write_text(text,encoding='utf-8')
 marker={'product':'Freedom GPT','version':VERSION,'platform':target,'hermes_commit':json.loads((donor/'freedom-bundle.json').read_text())['hermes_commit'],'personal_data_included':False,'model_weights_included':False}
 (app/'freedom-bundle.json').write_text(json.dumps(marker,indent=2));(app/'licenses/Runtime-provenance.json').write_text(json.dumps(native,indent=2))
 result=manifest(app,target);print('STAGED '+target+' '+str(sum(f['bytes'] for f in result['files']))+' bytes',flush=True);return app,result

def add_tar_file(tar,path,name,file_mode):
 info=tar.gettarinfo(str(path),name);info.mode=file_mode;info.uid=info.gid=0;info.uname=info.gname='root'
 with path.open('rb') as source:tar.addfile(info,source)

def add_tar_dir(tar,name):
 info=tarfile.TarInfo(name);info.type=tarfile.DIRTYPE;info.mode=0o755;info.uid=info.gid=0;info.uname=info.gname='root';tar.addfile(info)

def tar_app(app,output,prefix='FreedomGPT'):
 with tarfile.open(output,'w:gz',compresslevel=3) as archive:
  for path in sorted(app.rglob('*')):
   if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':add_tar_file(archive,path,prefix+'/'+path.relative_to(app).as_posix(),mode(path,app))

def ar_member(file,name,data):
 header=f'{name}/'.ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'100644'.ljust(8)+str(len(data)).ljust(10)+'`\n'
 file.write(header.encode('ascii'));file.write(data)
 if len(data)%2:file.write(b'\n')

def package_linux(app,out,deb_only=False):
 out.mkdir(parents=True,exist_ok=True);portable=out/f'FreedomGPT-{VERSION}-Ubuntu-x64.tar.gz'
 if not deb_only:tar_app(app,portable)
 stage=app.parent/'deb';data=stage/'data.tar.gz';control=stage/'control.tar.gz';stage.mkdir(exist_ok=True)
 launcher='#!/bin/sh\nset -eu\nBASE=/opt/freedom-gpt/App\nexec "$BASE/runtime/python/bin/python3" -B -s "$BASE/runtime/freedom/portable_install.py" --source "$BASE" "$@"\n'
 entry='[Desktop Entry]\nType=Application\nName=Freedom GPT\nComment=Local AI workspace\nExec=/opt/freedom-gpt/Start-FreedomGPT.sh\nIcon=/opt/freedom-gpt/App/public/freedom.svg\nTerminal=false\nCategories=Development;Utility;\n'
 (stage/'launcher.sh').write_text(launcher,newline='\n');(stage/'freedom-gpt.desktop').write_text(entry,newline='\n')
 with tarfile.open(data,'w:gz',compresslevel=3,format=tarfile.GNU_FORMAT) as archive:
  for name in ['./opt','./opt/freedom-gpt','./opt/freedom-gpt/App','./usr','./usr/share','./usr/share/applications']:add_tar_dir(archive,name)
  for path in sorted(app.rglob('*')):
   if path.is_dir() and '__pycache__' not in path.parts:add_tar_dir(archive,'./opt/freedom-gpt/App/'+path.relative_to(app).as_posix())
  for path in sorted(app.rglob('*')):
   if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':add_tar_file(archive,path,'./opt/freedom-gpt/App/'+path.relative_to(app).as_posix(),mode(path,app))
  add_tar_file(archive,stage/'launcher.sh','./opt/freedom-gpt/Start-FreedomGPT.sh',0o755)
  add_tar_file(archive,stage/'freedom-gpt.desktop','./usr/share/applications/freedom-gpt.desktop',0o644)
 control_text=f'Package: freedom-gpt\nVersion: {VERSION}\nArchitecture: amd64\nMaintainer: Freedom GPT contributors\nSection: utils\nPriority: optional\nDepends: libc6 (>= 2.39), libstdc++6\nRecommends: ca-certificates, xdg-utils, git\nDescription: Freedom GPT local AI workspace\n Private Python, agent and inference engines; models download separately.\n'
 (stage/'control').write_text(control_text)
 with tarfile.open(control,'w:gz',format=tarfile.GNU_FORMAT) as archive:add_tar_file(archive,stage/'control','./control',0o644)
 deb=out/f'FreedomGPT-{VERSION}-Ubuntu-amd64.deb'
 with deb.open('wb') as file:
  file.write(b'!<arch>\n');ar_member(file,'debian-binary',b'2.0\n');ar_member(file,'control.tar.gz',control.read_bytes());ar_member(file,'data.tar.gz',data.read_bytes())
 if deb_only:return [deb]
 # A no-admin self-extracting installer also works without a system Python.
 header='''#!/bin/sh
set -eu
DEST=${FREEDOM_INSTALL_DIR:-"$HOME/.local/share/FreedomGPT"}
PARENT=$(dirname -- "$DEST")
mkdir -p -- "$PARENT"
STAGING=$(mktemp -d "$PARENT/.freedom-setup-XXXXXX")
cleanup() { case "$STAGING" in "$PARENT"/.freedom-setup-*) rm -rf -- "$STAGING" ;; esac; }
trap cleanup EXIT HUP INT TERM
LINE=$(awk '/^__FREEDOM_PAYLOAD__$/ {print NR+1; exit}' "$0")
tail -n+"$LINE" "$0" | tar -xz -C "$STAGING"
"$STAGING/FreedomGPT/runtime/python/bin/python3" -B -s "$STAGING/FreedomGPT/runtime/freedom/portable_install.py" --source "$STAGING/FreedomGPT" --target "$DEST" "$@"
exit $?
__FREEDOM_PAYLOAD__
'''
 run=out/f'FreedomGPT-Setup-{VERSION}-Ubuntu-x64.run'
 with run.open('wb') as destination,portable.open('rb') as source:destination.write(header.encode());shutil.copyfileobj(source,destination,4*1024**2)
 return [portable,deb,run]

def package_mac(app,out):
 folder=app.parent/'Freedom GPT.app';resources=folder/'Contents/Resources';macos=folder/'Contents/MacOS';macos.mkdir(parents=True,exist_ok=True);resources.mkdir(parents=True,exist_ok=True)
 # The actual payload stays under Resources/App in the distributed app bundle.
 payload=resources/'App';tree(app,payload)
 launcher='#!/bin/sh\nset -eu\ncase "$(uname -m)" in arm64|aarch64) ;; *) printf "%s\\n" "This build requires Apple Silicon (M1 or later)." >&2; exit 1;; esac\nBASE=$(CDPATH= cd -- "$(dirname -- "$0")/../Resources/App" && pwd)\nexec "$BASE/runtime/python/bin/python3" -B -s "$BASE/runtime/freedom/portable_install.py" --source "$BASE" "$@"\n'
 (macos/'FreedomGPT').write_text(launcher,newline='\n')
 info={'CFBundleName':'Freedom GPT','CFBundleDisplayName':'Freedom GPT','CFBundleIdentifier':'org.freedomgpt.desktop','CFBundleExecutable':'FreedomGPT','CFBundlePackageType':'APPL','CFBundleShortVersionString':VERSION,'CFBundleVersion':VERSION,'LSMinimumSystemVersion':'26.2','LSArchitecturePriority':['arm64'],'NSHighResolutionCapable':True,'CFBundleDevelopmentRegion':'en','CFBundleLocalizations':['en','ru']}
 (folder/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
 # ICO PNG entries can be embedded in ICNS without redrawing the artwork.
 ico=(APP/'freedom.ico').read_bytes();count=struct.unpack_from('<H',ico,4)[0]
 for index in range(count):
  width,height,_,_,_,_,size,offset=struct.unpack_from('<BBBBHHII',ico,6+index*16);png=ico[offset:offset+size]
  if width==0 and png.startswith(b'\x89PNG'):
   chunk=b'ic08'+struct.pack('>I',8+len(png))+png;(resources/'freedom.icns').write_bytes(b'icns'+struct.pack('>I',8+len(chunk))+chunk);info['CFBundleIconFile']='freedom.icns';(folder/'Contents/Info.plist').write_bytes(plistlib.dumps(info));break
 out.mkdir(parents=True,exist_ok=True);archive=out/f'FreedomGPT-{VERSION}-macOS-AppleSilicon.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as file:
  for path in sorted(folder.rglob('*')):
   if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
   name=path.relative_to(folder.parent).as_posix();entry=zipfile.ZipInfo(name);entry.create_system=3;entry.compress_type=zipfile.ZIP_DEFLATED
   file_mode=0o755 if path==macos/'FreedomGPT' else mode(path,payload) if path.is_relative_to(payload) else 0o644
   entry.external_attr=(stat.S_IFREG|file_mode)<<16
   with file.open(entry,'w') as destination,path.open('rb') as source:shutil.copyfileobj(source,destination,4*1024**2)
 return [archive]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--target',choices=['ubuntu-x64','macos-arm64'],required=True);parser.add_argument('--runtime-from',required=True,type=pathlib.Path);parser.add_argument('--stage-only',action='store_true');args=parser.parse_args()
 donor=args.runtime_from.resolve()
 if json.loads((donor/'freedom-bundle.json').read_text()).get('personal_data_included') is not False:raise ValueError('A clean public donor runtime is required')
 app,report=prepare(args.target,donor)
 if args.stage_only:return
 out=ROOT/'release/platforms'/VERSION;files=package_linux(app,out) if args.target=='ubuntu-x64' else package_mac(app,out)
 result={'version':VERSION,'platform':args.target,'source':str(app),'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p),'path':str(p)} for p in files],'published':False,'native_execution_verified':False}
 (out/(args.target+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
