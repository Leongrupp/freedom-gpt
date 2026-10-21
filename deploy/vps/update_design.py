"""Atomically overlay an allowlisted static design, retaining the old release."""
import hashlib,json,os,pathlib,re,shutil,subprocess,sys,tarfile,time,urllib.request
BASE=pathlib.Path('/var/www/freedom-gpt');WORK=pathlib.Path('/root/freedom-gpt-deploy')
ALLOWED={'public/index.html','public/en/index.html','public/premium.css','public/premium.js','public/app.js','public/freedom.svg','public/media/site/core-hero.webp','public/media/site/creative-world.webp','public/media/site/project-cover.png'}
ALLOWED|={'public/robots.txt','public/sitemap.xml','public/llms.txt','public/agent.css'}
ALLOWED|={'public/'+lang+path+'index.html' for lang in ['', 'en/'] for path in ['install/windows/','install/ubuntu/','install/macos/','guides/local-ai/','guides/choose-model/','guides/ai-agent/']}

def allowed_files(manifest):
 declared={item['path'] for item in manifest['files']}
 extra=declared-ALLOWED
 if len(declared)!=len(manifest['files']) or not ALLOWED.issubset(declared) or len(extra)>1 or any(not re.fullmatch(r'public/[a-f0-9]{32}\.txt',name) for name in extra):raise ValueError('Unexpected design manifest')
 return declared

def run(args):
 result=subprocess.run(args,capture_output=True,text=True,timeout=25)
 if result.returncode:raise RuntimeError(args[0]+': '+result.stderr[-300:])
 return result.stdout

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def state():
 files={}
 for name in ['/etc/nginx','/etc/freedom-gpt-tls','/etc/ipsec.conf','/etc/ipsec.secrets','/etc/strongswan.conf','/etc/strongswan.d','/etc/accel-ppp.conf','/etc/ppp','/etc/xl2tpd','/etc/openvpn']:
  path=pathlib.Path(name)
  for file in sorted(path.rglob('*')) if path.is_dir() else [path]:
   if file.is_file():files[str(file)]=digest(file)
 services={}
 for name in ['nginx','freedom-gpt-tls','accel-ppp','strongswan-starter']:
  result=subprocess.run(['systemctl','show',name,'--property=ActiveState,MainPID','--value'],capture_output=True,text=True,timeout=10)
  services[name]=sorted(result.stdout.splitlines())
 return {'configuration_hashes':files,'services':services,'release_version':json.loads((BASE/'shared/metadata/release.json').read_text()).get('version')}

def check_http(path,expected):
 request=urllib.request.Request('http://127.0.0.1/'+path,headers={'Host':'185.125.100.186'})
 with urllib.request.urlopen(request,timeout=15) as response:
  assert response.status==200
  if hashlib.sha256(response.read()).hexdigest()!=expected:raise RuntimeError('HTTP content mismatch: '+path)

def main():
 archive=pathlib.Path(sys.argv[1]).resolve();expected=sys.argv[2]
 if not archive.is_relative_to(WORK) or digest(archive)!=expected:raise ValueError('Untrusted archive or digest')
 current=BASE/'current';old=current.resolve(strict=True)
 if not current.is_symlink() or not old.is_relative_to(BASE/'releases'):raise ValueError('Unexpected active website mapping')
 run(['nginx','-t']);before=state();stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
 report_dir=WORK/('design-'+stamp);report_dir.mkdir(mode=0o700,exist_ok=False)
 (report_dir/'state-before.json').write_text(json.dumps(before,indent=2));(report_dir/'previous-release.txt').write_text(str(old))
 folder=BASE/'releases'/('design-'+stamp)
 shutil.copytree(old,folder,symlinks=True)
 with tarfile.open(archive,'r:gz') as tar:
  names=tar.getnames()
  data=tar.extractfile('design-manifest.json')
  if data is None:raise ValueError('Missing design manifest')
  declared=allowed_files(json.load(data))
  if len(names)!=len(set(names)) or set(names)!=declared|{'design-manifest.json'}:raise ValueError('Unexpected files in design archive')
  for member in tar.getmembers():
   if not member.isfile() or not (folder/member.name).resolve().is_relative_to(folder):raise ValueError('Unsafe archive member')
  tar.extractall(folder,filter='data')
 manifest=json.loads((folder/'design-manifest.json').read_text())
 allowed_files(manifest)
 for item in manifest['files']:
  file=folder/item['path']
  if file.stat().st_size!=item['bytes'] or digest(file)!=item['sha256']:raise ValueError('Extracted design mismatch')
  os.chmod(file,0o644)
 for path in folder.rglob('*'):
  if path.is_dir():os.chmod(path,0o755)
 os.chmod(folder,0o755)
 # Unmanaged application metadata and model/download directories are copied or
 # left in shared storage; neither their content nor service configuration changes.
 if digest(folder/'public/api/catalog.json')!=digest(old/'public/api/catalog.json'):raise ValueError('Catalog changed unexpectedly')
 next_link=BASE/('current-next-'+stamp);next_link.symlink_to(folder,target_is_directory=True)
 activated=False
 try:
  os.replace(next_link,current);activated=True
  for item in manifest['files']:
   path=item['path'].removeprefix('public/')
   if path=='index.html':path=''
   elif path=='en/index.html':path='en/'
   check_http(path,item['sha256'])
  after=state()
  if before!=after:raise RuntimeError('Protected configuration, services or published version changed')
  run(['nginx','-t'])
 except Exception:
  if activated:
   rollback=BASE/('current-rollback-'+stamp);rollback.symlink_to(old,target_is_directory=True);os.replace(rollback,current)
  raise
 report={'deployed':True,'design':manifest['version'],'previous_release':str(old),'current_release':str(folder),'protected_state_unchanged':before==after,'published_app_version':after['release_version'],'http_files_verified':len(manifest['files']),'backup_record':str(report_dir),'no_service_restart_or_reload':True}
 (report_dir/'state-after.json').write_text(json.dumps(after,indent=2));(report_dir/'result.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report))
if __name__=='__main__':main()
