"""First-run installer, executed by the bundled Python rather than system Python."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,time,uuid
sys.dont_write_bytecode=True
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
PROTECTED={'.tmp','.cache','data','logs','uploads','output','workspaces','archive'}
def sha(path):
 value=hashlib.sha256()
 with path.open('rb') as source:
  for block in iter(lambda:source.read(4*1024**2),b''):value.update(block)
 return value.hexdigest()
def version(text):return tuple(map(int,text.split('.')))
def install(source,target):
 source=pathlib.Path(source).resolve();target=pathlib.Path(target).expanduser().resolve()
 manifest=json.loads((source/'bundle-manifest.json').read_text(encoding='utf-8'))
 if target==source:return source
 if target.exists() and any(target.iterdir()) and not (target/'freedom-bundle.json').is_file():raise RuntimeError('Choose an empty directory or an existing Freedom GPT installation.')
 current=json.loads((target/'freedom-bundle.json').read_text()) if (target/'freedom-bundle.json').is_file() else {}
 if current and current.get('platform')!=manifest['platform']:raise RuntimeError('This directory belongs to a different platform. Choose a separate app folder.')
 if current and version(current['version'])>version(manifest['version']):return target
 if current and version(current['version'])==version(manifest['version']):
  try:prior=json.loads((target/'data/installer-report.json').read_text())
  except (OSError,ValueError):prior={}
  if prior.get('source_manifest')==sha(source/'bundle-manifest.json'):return target
 target.mkdir(parents=True,exist_ok=True)
 required=sum(item['bytes'] for item in manifest['files'])
 if shutil.disk_usage(target).free<required*2+1024**3:raise RuntimeError('Not enough free space for installation and backups.')
 for item in manifest['files']:
  name=pathlib.PurePosixPath(item['path'])
  if name.is_absolute() or '..' in name.parts or name.parts[0] in PROTECTED or not (source/name).resolve().is_relative_to(source):raise ValueError('Protected installer path')
  file=source/name
  if file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:raise ValueError('Installer integrity error: '+str(name))
 token=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8];stage=target/'.tmp'/('install-'+token);backup=target/'archive'/('installation-'+token)
 stage.mkdir(parents=True)
 changed=[]
 for item in manifest['files']:
  destination=target/item['path'];pending=stage/item['path']
  if destination.is_file() and sha(destination)==item['sha256']:continue
  if not destination.resolve().is_relative_to(target):raise ValueError('Installation path escapes app directory')
  pending.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/item['path'],pending);os.chmod(pending,item.get('mode',0o644)&0o755)
  changed.append(item['path'])
 old_python=target/'runtime/python/bin/python3'
 if (target/'.tmp/server-process.json').exists() and old_python.is_file():
  env=os.environ.copy();env.pop('PYTHONPATH',None)
  subprocess.run([str(old_python),'-B','-s',str(target/'stop.py')],cwd=target,env=env,check=True,timeout=180)
 committed=[]
 try:
  for name in changed:
   destination=target/name;had_file=destination.exists()
   if had_file:
    old=backup/name;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,old)
   destination.parent.mkdir(parents=True,exist_ok=True);os.replace(stage/name,destination);committed.append((name,had_file))
 except Exception:
  for name,had_file in reversed(committed):
   if had_file:shutil.copy2(backup/name,target/name)
  raise
 (target/'data').mkdir(exist_ok=True)
 (target/'data/installer-report.json').write_text(json.dumps({'version':manifest['version'],'platform':manifest['platform'],'changed':len(changed),'backup':str(backup),'source_manifest':sha(source/'bundle-manifest.json')},indent=2))
 return target
def shortcut(target):
 if sys.platform!='linux':return
 folder=pathlib.Path.home()/'.local/share/applications';folder.mkdir(parents=True,exist_ok=True)
 # Desktop Exec values use desktop-entry quoting, independently of shell quoting.
 script=str(target/'Start-FreedomGPT.sh').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
 icon=str(target/'public/freedom.svg')
 text=f'[Desktop Entry]\nType=Application\nName=Freedom GPT\nComment=Your local AI workspace\nExec="{script}"\nIcon={icon}\nTerminal=false\nCategories=Development;Utility;\nStartupNotify=true\n'
 (folder/'freedom-gpt.desktop').write_text(text,encoding='utf-8')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--target');parser.add_argument('--no-browser',action='store_true');parser.add_argument('--install-only',action='store_true');args=parser.parse_args()
 default=pathlib.Path.home()/('Library/Application Support/FreedomGPT' if sys.platform=='darwin' else '.local/share/FreedomGPT')
 target=install(args.source,args.target or os.environ.get('FREEDOM_INSTALL_DIR') or default);shortcut(target)
 if args.install_only:print(str(target));return
 env=os.environ.copy();env.pop('PYTHONPATH',None)
 command=[str(target/'runtime/python/bin/python3'),'-B','-s',str(target/'launch.py')]
 if args.no_browser:command.append('--no-browser')
 raise SystemExit(subprocess.call(command,cwd=target,env=env))
if __name__=='__main__':
 try:main()
 except Exception as exc:print('Freedom GPT installation: '+str(exc),file=sys.stderr);raise SystemExit(1)
