"""Create the public source archive from an explicit allowlist."""
import hashlib,json,pathlib,zipfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
def main():
 version=json.loads((ROOT/'app/version.json').read_text())['version'];output=ROOT/'release'/('FreedomGPT-source-'+version+'.zip');files=[]
 for name in ['.gitignore','.gitattributes','README.md','README.ru.md','BUILD.md','VERIFICATION.md','LICENSE','NOTICE','SECURITY.md','CONTRIBUTING.md','Start-Website.cmd','Export-to-SSD.cmd','FILEZILLA-MODELS.txt']:
  files.append(ROOT/name)
 for name in ['src','public']:
  files.extend(p for p in (ROOT/'app'/name).rglob('*') if p.is_file())
 files.extend(p for p in (ROOT/'app').iterdir() if p.is_file() and p.suffix.lower() in {'.py','.json','.js','.html','.cmd','.ico','.txt','.pub'})
 for name in ['site','licenses','assets','.github','deploy']:
  files.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 for name in ['bundle.py','release.py','catalog.py','source_archive.py','sign_update.py','publish.py','export_ssd.py','Installer.cs','Launcher.cs']:
  files.append(ROOT/'packaging'/name)
 with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
  for file in sorted(set(files)):archive.write(file,file.relative_to(ROOT).as_posix())
 sha=hashlib.sha256(output.read_bytes()).hexdigest();manifest_file=ROOT/'release/release.json';manifest=json.loads(manifest_file.read_text())
 manifest['files']=[f for f in manifest['files'] if f['name']!=output.name]+[dict(name=output.name,bytes=output.stat().st_size,sha256=sha)]
 manifest_file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
 (ROOT/'release/SHA256SUMS.txt').write_text(''.join(f['sha256']+'  '+f['name']+'\n' for f in manifest['files']),encoding='ascii')
 print('SOURCE_ARCHIVE',output.stat().st_size,sha,flush=True)
if __name__=='__main__':main()
