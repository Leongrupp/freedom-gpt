"""Prove that every public desktop payload contains the reviewed app sources."""
from pathlib import Path
import hashlib,json,sys,tarfile,zipfile
from feature_payload import MODULES

ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'app/version.json').read_text(encoding='utf8'))['version']
PLATFORMS=ROOT/'release/platforms'/VERSION

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    expected={}
    for name in ['bootstrap.py','launch.py','stop.py','server.py','library.py','engine_supervisor.py','gguf_info.py',
                 'generate-image-request.py','updater.py','apply_update.py','update_protocol.py','version.json','catalog.json']:
        expected[name]=sha((ROOT/'app'/name).read_bytes())
    for name in [*MODULES,'discovery.py','video.py','platform_support.py','preflight.py','system_check.py']:
        expected['runtime/freedom/'+name]=sha((ROOT/'app'/name).read_bytes())
    overrides=json.loads((ROOT/'app/native_overrides/manifest.json').read_text(encoding='utf8'))
    for item in overrides['files']:
        source=ROOT/'app/native_overrides'/item['path']
        assert sha(source.read_bytes())==item['sha256']
        expected['runtime/hermes/'+item['path']]=item['sha256']
    for source,prefix in [(ROOT/'app/dist','dist/'),(ROOT/'app/scripts','runtime/freedom/scripts/')]:
        for file in source.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix!='.pyc':
                expected[prefix+file.relative_to(source).as_posix()]=sha(file.read_bytes())
    errors={};checked={}
    for target,path,prefix in [
        ('windows-x64',ROOT/'release'/f'FreedomGPT-{VERSION}-Windows-x64.zip',''),
        ('macos-arm64',PLATFORMS/f'FreedomGPT-{VERSION}-macOS-AppleSilicon.zip','Freedom GPT.app/Contents/Resources/App/')]:
        bad=[]
        with zipfile.ZipFile(path) as archive:
            for name,digest in expected.items():
                try:actual=sha(archive.read(prefix+name))
                except KeyError:actual=None
                if actual!=digest:bad.append(name)
        errors[target]=bad;checked[target]=len(expected)
    seen=set();bad=[]
    with tarfile.open(PLATFORMS/f'FreedomGPT-{VERSION}-Ubuntu-x64.tar.gz','r|gz') as archive:
        for entry in archive:
            name=entry.name.removeprefix('FreedomGPT/')
            if entry.isfile() and name in expected:
                seen.add(name)
                if sha(archive.extractfile(entry).read())!=expected[name]:bad.append(name)
    bad.extend(sorted(set(expected)-seen));errors['ubuntu-x64']=bad;checked['ubuntu-x64']=len(seen)
    report={'version':VERSION,'checked_files':checked,'mismatches':errors,'passed':all(not v for v in errors.values())}
    (ROOT/'logs'/f'source-alignment-verification-{VERSION}.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
