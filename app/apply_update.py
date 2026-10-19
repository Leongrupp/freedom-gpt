"""Independent transactional updater. User data is outside the managed allowlist."""
import argparse,base64,datetime,json,os,pathlib,shutil,stat,subprocess,sys,time,zipfile
from update_protocol import verify,sha256,safe_target

def start_app(root):
 env=os.environ.copy();env.pop('PYTHONPATH',None)
 python=root/('runtime/python/pythonw.exe' if os.name=='nt' else 'runtime/python/bin/python3')
 subprocess.Popen([str(python),'-B','-s',str(root/'launch.py'),'--no-browser'],cwd=root,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def apply(root,envelope,package,stop=True,restart=True):
 root=pathlib.Path(root).resolve();package=pathlib.Path(package).resolve()
 payload=verify(envelope,(root/'update-key.pub').read_text())
 if package.stat().st_size!=payload['package']['bytes'] or sha256(package)!=payload['package']['sha256']:raise ValueError('Package integrity mismatch')
 stage=root/'.cache/updates'/payload['version']/'stage';stage.mkdir(parents=True,exist_ok=True)
 expected={f['path']:f for f in payload['files']};seen=set();all_seen=set()
 with zipfile.ZipFile(package) as archive:
  for entry in archive.infolist():
   if entry.is_dir():continue
   name=entry.filename
   if name.casefold() in all_seen or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Unexpected archive path')
   all_seen.add(name.casefold())
   # First public release also serves as the clean portable installer.
   if name in {'update-key.pub','stack/hermes-runtime/SOUL.md'} and entry.file_size<65536:continue
   if name not in expected:raise ValueError('Unexpected archive path')
   safe_target(root,name);dest=stage.joinpath(*name.split('/'));dest.parent.mkdir(parents=True,exist_ok=True)
   if entry.file_size!=expected[name]['bytes']:raise ValueError('File size mismatch')
   with archive.open(entry) as source,dest.open('wb') as output:shutil.copyfileobj(source,output,1024**2)
   if sha256(dest)!=expected[name]['sha256']:raise ValueError('File digest mismatch')
   if os.name!='nt':os.chmod(dest,(entry.external_attr>>16)&0o755 or 0o644)
   seen.add(name.casefold())
 if seen!={n.casefold() for n in expected}:raise ValueError('Missing archive files')
 if stop:
  env=os.environ.copy();env.pop('PYTHONPATH',None)
  python=root/('runtime/python/python.exe' if os.name=='nt' else 'runtime/python/bin/python3')
  subprocess.run([str(python),'-B','-s',str(root/'stop.py')],cwd=root,env=env,timeout=120,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 backup=root/'archive'/('update-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+payload['version']);backup.mkdir(parents=True)
 changed=[]
 try:
  for name in expected:
   target=safe_target(root,name);source=stage.joinpath(*name.split('/'))
   if target.is_file() and sha256(target)==expected[name]['sha256']:continue
   existed=target.exists();old=backup.joinpath(*name.split('/'))
   if existed:old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,old)
   target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.update-new')
   shutil.copy2(source,temp);os.replace(temp,target);changed.append((name,existed))
  status={'state':'installed','version':payload['version'],'backup':str(backup),'changed':len(changed),'time':time.time()}
 except Exception as exc:
  for name,existed in reversed(changed):
   target=safe_target(root,name)
   if existed:shutil.copy2(backup.joinpath(*name.split('/')),target)
   elif target.is_file():target.unlink()  # Only files newly created by this failed transaction.
  (root/'data').mkdir(exist_ok=True)
  (root/'data/update-result.json').write_text(json.dumps({'state':'rolled_back','error':str(exc),'backup':str(backup)}),encoding='utf8')
  if restart:start_app(root)
  raise
 (root/'data').mkdir(exist_ok=True);(root/'data/update-result.json').write_text(json.dumps(status,indent=2),encoding='utf8')
 if restart:start_app(root)
 return status
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--manifest',required=True);parser.add_argument('--package',required=True);args=parser.parse_args()
 print(json.dumps(apply(args.root,json.loads(pathlib.Path(args.manifest).read_text(encoding='utf8')),args.package)),flush=True)
