"""Refresh public download metadata. No account or GitHub credential is used."""
import hashlib,json,os,pathlib,re,time,urllib.error,urllib.request
BASE=pathlib.Path('/var/www/freedom-gpt')
META=BASE/'shared/metadata'
REPO='Leongrupp/freedom-gpt'

def write(name,value):
 target=META/name;temporary=META/(name+'.new')
 temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.chmod(temporary,0o644);temporary.replace(target)

def fetch(url,expected_sha=None):
 request=urllib.request.Request(url,headers={'User-Agent':'FreedomGPT-Website','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(request,timeout=12) as response:
  raw=response.read(2*1024**2+1)
 if len(raw)>2*1024**2:raise ValueError('Oversized public release response')
 if expected_sha is not None and hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('Public platform matrix digest mismatch')
 return json.loads(raw)

def main():
 META.mkdir(parents=True,exist_ok=True)
 try:
  value=fetch('https://api.github.com/repos/'+REPO+'/releases/latest')
  tag=value.get('tag_name','')
  if not re.fullmatch(r'v\d+\.\d+\.\d+',tag) or value.get('draft') or value.get('prerelease'):raise ValueError('Invalid stable release')
  names={f'FreedomGPT-Setup-{tag[1:]}.exe',f'FreedomGPT-{tag[1:]}-Windows-x64.zip'}
  files=[]
  for asset in value.get('assets',[]):
   if asset.get('name') not in names or asset.get('state')!='uploaded':continue
   name=asset['name'];size=asset.get('size',0)
   if not isinstance(size,int) or not 0<size<2*1024**3:continue
   digest=asset.get('digest','');sha=digest[7:] if re.fullmatch(r'sha256:[a-f0-9]{64}',digest or '') else None
   files.append({'name':name,'bytes':size,'sha256':sha,'url':f'https://github.com/{REPO}/releases/download/{tag}/{name}'})
  if len(files)!=2:raise ValueError('Windows release assets are incomplete')
  write('release.json',{'product':'Freedom GPT','version':tag[1:],'public':True,'status':'ready','files':files,'checked_at':time.time()})
  layouts=[('windows-x64','Windows 10/11 x64', ['FreedomGPT-Setup-{v}.exe','FreedomGPT-{v}-Windows-x64.zip'], 'Python, Node.js и движки внутри; модели отдельно.', 'Python, Node.js and engines included; models separate.'),
           ('ubuntu-x64','Ubuntu 24.04 x64',['FreedomGPT-Setup-{v}-Ubuntu-x64.run','FreedomGPT-{v}-Ubuntu-amd64.deb','FreedomGPT-{v}-Ubuntu-x64.tar.gz'],'Проверено в чистом контейнере без сети; GPU требует драйвера.','Tested in a clean offline container; GPU needs a driver.'),
           ('macos-arm64','macOS · Apple Silicon',['FreedomGPT-{v}-macOS-AppleSilicon.zip'],'macOS 26.2+, M1+. Кандидат без подписи, запуск на Mac ещё не проверен.','macOS 26.2+, M1+. Unsigned candidate; native Mac execution not yet tested.')]
  uploaded={a['name']:a for a in value.get('assets',[]) if a.get('state')=='uploaded'};platforms=[]
  for target,label,patterns,ru,en in layouts:
   downloads=[]
   for pattern in patterns:
    name=pattern.format(v=tag[1:]);asset=uploaded.get(name)
    if not asset:continue
    size=asset.get('size',0)
    if not isinstance(size,int) or not 0<size<2*1024**3:continue
    digest=asset.get('digest','');sha=digest[7:] if re.fullmatch(r'sha256:[a-f0-9]{64}',digest or '') else None
    fmt='EXE' if name.endswith('.exe') else 'DEB' if name.endswith('.deb') else '.run' if name.endswith('.run') else 'TAR.GZ' if name.endswith('.tar.gz') else '.app ZIP' if target=='macos-arm64' else 'ZIP'
    downloads.append({'name':name,'bytes':size,'sha256':sha,'format':fmt,'url':f'https://github.com/{REPO}/releases/download/{tag}/{name}'})
   if downloads:platforms.append({'id':target,'name':label,'files':downloads,'note_ru':ru,'note_en':en,'native_tested':target!='macos-arm64'})
  # The released matrix carries the exact current verification scope. Do not
  # overwrite successful native CI evidence with a permanent "unverified" label.
  matrix_asset=uploaded.get('platforms.json',{})
  matrix_digest=matrix_asset.get('digest','')
  if re.fullmatch(r'sha256:[a-f0-9]{64}',matrix_digest or ''):
   matrix=fetch(f'https://github.com/{REPO}/releases/download/{tag}/platforms.json',matrix_digest[7:])
   if matrix.get('version')!=tag[1:] or matrix.get('published') is not True:raise ValueError('Platform matrix version mismatch')
   declared={p['id']:p for p in matrix['platforms']}
   if set(declared)!={p['id'] for p in platforms}:raise ValueError('Platform matrix layout mismatch')
   for platform in platforms:
    entry=declared[platform['id']]
    actual={f['name']:(f['bytes'],f['sha256']) for f in platform['files']}
    if {f['name']:(f['bytes'],f['sha256']) for f in entry['files']}!=actual:raise ValueError('Platform matrix asset mismatch')
    for field in ['note_ru','note_en']:
     if not isinstance(entry.get(field),str) or len(entry[field])>2000:raise ValueError('Invalid platform note')
     platform[field]=entry[field]
    platform['native_tested']=entry.get('native_tested') is True
    if platform['id']=='macos-arm64' and platform['native_tested']:
     proof=entry.get('native_verification_url','')
     if not re.fullmatch(r'https://github.com/Leongrupp/freedom-gpt/actions/runs/\d+',proof):raise ValueError('Native verification link required')
     platform.update(native_verification_url=proof,model_generation_tested=False,media_generation_tested=False)
  write('platforms.json',{'product':'Freedom GPT','version':tag[1:],'published':True,'platforms':platforms,'checked_at':time.time()})
 except Exception as exc:
  old={}
  try:old=json.loads((META/'release.json').read_text())
  except (OSError,ValueError):pass
  if old.get('status')!='ready':write('release.json',{'product':'Freedom GPT','status':'pending','public':True,'files':[],'checked_at':time.time()})
  print('Release check:',type(exc).__name__)
 catalog=json.loads((BASE/'current/public/api/catalog.json').read_text())
 available=[]
 for model in catalog:
  item={'id':model['id'],'name':model['name'],'files':[]}
  for file in model.get('files',[]):
   path=BASE/'shared/models'/model['id']/file['name']
   if path.is_file() and path.stat().st_size==file['bytes']:
    item['files'].append({'name':file['name'],'bytes':file['bytes'],'sha256':file['sha256'],'url':'/models/'+model['id']+'/'+file['name'],'verification':'expected_size'})
  if item['files']:available.append(item)
 write('models.json',{'models':available,'checked_at':time.time()})
 print('Public metadata refreshed; model files available:',sum(len(m['files']) for m in available))

if __name__=='__main__':main()
