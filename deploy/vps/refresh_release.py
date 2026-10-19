"""Refresh public download metadata. No account or GitHub credential is used."""
import json,os,pathlib,re,time,urllib.error,urllib.request
BASE=pathlib.Path('/var/www/freedom-gpt')
META=BASE/'shared/metadata'
REPO='Leongrupp/freedom-gpt'

def write(name,value):
 target=META/name;temporary=META/(name+'.new')
 temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.chmod(temporary,0o644);temporary.replace(target)

def fetch(url):
 request=urllib.request.Request(url,headers={'User-Agent':'FreedomGPT-Website','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(request,timeout=12) as response:
  raw=response.read(2*1024**2+1)
 if len(raw)>2*1024**2:raise ValueError('Oversized public release response')
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
