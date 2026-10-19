"""Deploy only this static website into an existing nginx installation."""
import hashlib,json,os,pathlib,pwd,re,shutil,subprocess,sys,tarfile,time
WORK=pathlib.Path('/root/freedom-gpt-deploy');BASE=pathlib.Path('/var/www/freedom-gpt')
CONF=pathlib.Path('/etc/nginx/sites-available/freedom-gpt.conf');ENABLED=pathlib.Path('/etc/nginx/sites-enabled/freedom-gpt.conf')
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=40)
 if p.returncode:raise RuntimeError('Command failed: '+args[0]+' '+p.stderr[-600:])
 return p.stdout
def main():
 archive=pathlib.Path(sys.argv[1]).resolve();expected=sys.argv[2]
 if not archive.is_relative_to(WORK) or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise ValueError('Untrusted upload path or digest')
 run(['nginx','-t'])
 if CONF.exists() or ENABLED.exists() or ENABLED.is_symlink() or (BASE/'current').exists():raise RuntimeError('An existing Freedom GPT deployment requires a reviewed update, refusing overwrite')
 release=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());folder=BASE/'releases'/release
 folder.mkdir(parents=True,exist_ok=False)
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar.getmembers():
   if not member.isfile() or not (folder/member.name).resolve().is_relative_to(folder.resolve()):raise ValueError('Unsafe site archive member')
  tar.extractall(folder,filter='data')
 manifest=json.loads((folder/'site-manifest.json').read_text())
 for item in manifest['files']:
  file=folder/item['path']
  if file.stat().st_size!=item['bytes'] or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Extracted file mismatch')
 for path in folder.rglob('*'):os.chmod(path,0o755 if path.is_dir() else 0o644)
 backup=WORK/('nginx-backup-'+release+'.tar.gz')
 with tarfile.open(backup,'w:gz') as tar:tar.add('/etc/nginx',arcname='nginx')
 os.chmod(backup,0o600)
 for sub in ['shared/models','shared/downloads','shared/metadata']: (BASE/sub).mkdir(parents=True,exist_ok=True)
 metadata=BASE/'shared/metadata';account=pwd.getpwnam('www-data');os.chown(metadata,account.pw_uid,account.pw_gid);os.chmod(metadata,0o755)
 catalog=json.loads((folder/'public/api/catalog.json').read_text())
 for model in catalog:
  if not re.fullmatch('[a-z0-9][a-z0-9_-]*',model['id']):raise ValueError('Unsafe model ID')
  (BASE/'shared/models'/model['id']).mkdir(exist_ok=True)
 for name,data in [('release.json',{'product':'Freedom GPT','status':'pending','public':True,'files':[]}),('models.json',{'models':[]})]:
  file=metadata/name;file.write_text(json.dumps(data));os.chown(file,account.pw_uid,account.pw_gid);os.chmod(file,0o644)
 (BASE/'current').symlink_to(folder,target_is_directory=True)
 activated=False
 try:
  shutil.copy2(folder/'nginx/freedom-gpt.nginx.conf',CONF);os.chmod(CONF,0o644);ENABLED.symlink_to(CONF)
  run(['nginx','-t']);run(['systemctl','reload','nginx']);activated=True
  for name in ['freedom-gpt-release-refresh.service','freedom-gpt-release-refresh.timer']:
   target=pathlib.Path('/etc/systemd/system')/name
   if target.exists():raise RuntimeError('Existing service unit requires review')
   shutil.copy2(folder/'systemd'/name,target);os.chmod(target,0o644)
  run(['systemctl','daemon-reload']);run(['systemctl','enable','--now','freedom-gpt-release-refresh.timer'])
  run(['systemctl','start','--no-block','freedom-gpt-release-refresh.service'])
 except Exception:
  if ENABLED.is_symlink():ENABLED.unlink()
  if CONF.exists():CONF.unlink()
  if activated:run(['nginx','-t']);run(['systemctl','reload','nginx'])
  raise
 report={'deployed':True,'release':release,'root':str(BASE/'current/public'),'model_upload':str(BASE/'shared/models'),'nginx_backup':str(backup),'managed_files':len(manifest['files'])}
 (WORK/'deployment.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
