"""Package only the website design; never publish an application or model."""
import hashlib,json,pathlib,secrets,shutil,subprocess,sys,tarfile,time
ROOT=pathlib.Path(__file__).resolve().parent.parent

def main():
 subprocess.run([sys.executable,str(ROOT/'site/build.py')],cwd=ROOT,check=True)
 stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());folder=ROOT/'build'/('site-design-'+stamp)
 files={
  'public/index.html':'site/index.html','public/en/index.html':'site/en.html',
  'public/premium.css':'site/premium.css','public/premium.js':'site/premium.js',
  'public/app.js':'site/app.js','public/freedom.svg':'site/freedom.svg',
  'public/agent.css':'site/agent.css',
  'bin/refresh_release.py':'deploy/vps/refresh_release.py',
  'public/media/site/core-hero.webp':'assets/site/core-hero.webp',
  'public/media/site/creative-world.webp':'assets/site/creative-world.webp',
  'public/media/site/project-cover.png':'assets/cover-platforms.png',
 }
 for name in ['overview-ru','overview-en','chat-ru','chat-en','goal-ru','goal-en','models-ru','models-en','agent-working-ru','phone-access','settings-160','rewards-160','phone-160','notifications-160','workspace-160-ru','workspace-160-en']:
  files['public/media/screenshots/'+name+'.png']='assets/screenshots/'+name+'.png'
 sys.path.insert(0,str(ROOT/'site'))
 from seo import generated_files
 files.update({'public/'+name:'site/generated/'+name for name in generated_files()})
 manifest={'type':'website-design-only','version':'seo-'+json.loads((ROOT/'app/version.json').read_text())['version'],'files':[]}
 for name,source in files.items():
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
  manifest['files'].append({'path':name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 # This public verification file grants only IndexNow URL submission for this
 # host. Keep its identifier out of the source repository and model catalogs.
 config=ROOT/'.private/seo-indexnow.json'
 if not config.exists():
  config.parent.mkdir(exist_ok=True)
  config.write_text(json.dumps({'host':'aionpc.ru','key':secrets.token_hex(16)},indent=2),encoding='utf-8')
 indexnow=json.loads(config.read_text(encoding='utf-8'));key=indexnow['key']
 import re
 if indexnow['host']!='aionpc.ru' or not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Unexpected IndexNow configuration')
 name='public/'+key+'.txt';target=folder/name;target.write_text(key,encoding='ascii')
 manifest['files'].append({'path':name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 (folder/'design-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 archive=ROOT/'.tmp'/('site-design-'+stamp+'.tar.gz')
 with tarfile.open(archive,'w:gz') as tar:
  for file in sorted(folder.rglob('*')):
   if file.is_file():tar.add(file,arcname=file.relative_to(folder).as_posix(),recursive=False)
 record={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'directory':str(folder)}
 (ROOT/'.tmp/site-design-package.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record))
if __name__=='__main__':main()
