"""Compile launchers and create a single EXE with an embedded, verified ZIP payload."""
import hashlib,json,pathlib,shutil,struct,subprocess,time,zipfile
ROOT=pathlib.Path(__file__).resolve().parent.parent;VERSION=json.loads((ROOT/'app/version.json').read_text())['version'];BUNDLE=ROOT/'build'/('FreedomGPT-'+VERSION);OUT=ROOT/'release';OUT.mkdir(exist_ok=True)
CSC=pathlib.Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
def hashfile(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
 return h.hexdigest()
def compile(source,target):
 args=[str(CSC),'/nologo','/target:winexe','/platform:x64','/out:'+str(target),'/win32icon:'+str(ROOT/'app/freedom.ico')]
 for assembly in ['System.dll','System.Core.dll','System.Drawing.dll','System.Windows.Forms.dll','System.IO.Compression.dll','System.IO.Compression.FileSystem.dll','Microsoft.CSharp.dll']:args+=['/reference:'+assembly]
 subprocess.run(args+[str(ROOT/'packaging'/source)],check=True,cwd=ROOT)
def main():
 compile('Launcher.cs',BUNDLE/'FreedomGPT.exe');compile('Installer.cs',ROOT/'build/SetupStub.exe')
 archive=OUT/('FreedomGPT-'+VERSION+'-Windows-x64.zip')
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as zip:
  for path in sorted(BUNDLE.rglob('*')):
   if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
    try:zip.write(path,path.relative_to(BUNDLE).as_posix())
    except OSError as exc:raise RuntimeError('Cannot archive public bundle file: '+str(path.relative_to(BUNDLE))) from exc
 print('ZIP_BYTES',archive.stat().st_size,flush=True)
 installer=OUT/('FreedomGPT-Setup-'+VERSION+'.exe')
 with installer.open('wb') as dest:
  with (ROOT/'build/SetupStub.exe').open('rb') as source:shutil.copyfileobj(source,dest)
  offset=dest.tell()
  with archive.open('rb') as source:shutil.copyfileobj(source,dest,4*1024**2)
  dest.write(b'FREEDOMGPTPKG001'+struct.pack('<QQ',offset,archive.stat().st_size)+bytes.fromhex(hashfile(archive)))
 if installer.stat().st_size>=2*1024**3:raise ValueError('Installer exceeds the GitHub 2 GiB asset limit')
 from sign_update import build
 update_assets=build(BUNDLE,OUT)
 files=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashfile(p)) for p in [installer,archive,*update_assets]]
 manifest={'product':'Freedom GPT','version':VERSION,'date':time.strftime('%Y-%m-%d'),'platform':'Windows 10/11 x64','files':files,'default_models':['huihui-qwen38-coder','qwen-image21'],'models_included':False,'public':False,'signed':False}
 (OUT/'release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
 (OUT/'SHA256SUMS.txt').write_text('\n'.join(f["sha256"]+'  '+f["name"] for f in files)+'\n',encoding='ascii')
 print(json.dumps(manifest,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
