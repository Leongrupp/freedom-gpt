"""Package only the website design; never publish an application or model."""
import hashlib,json,pathlib,shutil,subprocess,sys,tarfile,time
ROOT=pathlib.Path(__file__).resolve().parent.parent

def main():
 subprocess.run([sys.executable,str(ROOT/'site/build.py')],cwd=ROOT,check=True)
 stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());folder=ROOT/'build'/('site-design-'+stamp)
 files={
  'public/index.html':'site/index.html','public/en/index.html':'site/en.html',
  'public/premium.css':'site/premium.css','public/premium.js':'site/premium.js',
  'public/app.js':'site/app.js','public/freedom.svg':'site/freedom.svg',
  'public/media/site/core-hero.webp':'assets/site/core-hero.webp',
  'public/media/site/creative-world.webp':'assets/site/creative-world.webp',
 }
 manifest={'type':'website-design-only','version':'community-'+json.loads((ROOT/'app/version.json').read_text())['version'],'files':[]}
 for name,source in files.items():
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
  manifest['files'].append({'path':name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 (folder/'design-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 archive=ROOT/'.tmp'/('site-design-'+stamp+'.tar.gz')
 with tarfile.open(archive,'w:gz') as tar:
  for file in sorted(folder.rglob('*')):
   if file.is_file():tar.add(file,arcname=file.relative_to(folder).as_posix(),recursive=False)
 record={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'directory':str(folder)}
 (ROOT/'.tmp/site-design-package.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record))
if __name__=='__main__':main()
