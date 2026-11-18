"""Upload exact native candidates to a draft for CI; never publish a release."""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

from publish import github_env

ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION='1.7.0'
REPO='Leongrupp/freedom-gpt'
OUT=ROOT/'release/platforms'/VERSION
STATUS=ROOT/'logs/release-1.7.0/native-upload.json'
GH=next((pathlib.Path(os.environ['LOCALAPPDATA'])/'Microsoft/WinGet/Packages').glob('GitHub.cli_*/bin/gh.exe'))
ENV=github_env()
STATUS_LOCK=threading.Lock()


def allowed():
    p=ROOT/'.private'/('publication-approval-'+VERSION+'.json')
    d=json.loads(p.read_text())
    if d.get('enabled') is not True or d.get('version')!=VERSION or (ROOT/'.private'/('release-stop-'+VERSION)).exists():
        raise RuntimeError('This release upload is not enabled')


def run(args,timeout=90,check=True):
    allowed()
    p=subprocess.run([str(GH),*map(str,args)],cwd=ROOT,env=ENV,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
    if check and p.returncode:raise RuntimeError(p.stderr[-800:])
    return p


def state(stage,**data):
    d={'stage':stage,'version':VERSION,'time':time.time(),**data}
    with STATUS_LOCK:
        STATUS.write_text(json.dumps(d,indent=2),encoding='utf8');print(json.dumps(d),flush=True)


def digest(file):
    h=hashlib.sha256()
    with file.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()


def main():
    allowed()
    # Platform manifests are written only after their archives and feeds finish.
    deadline=time.monotonic()+3600
    state('waiting_for_final_native_packages')
    source_stamp=max(p.stat().st_mtime for p in (ROOT/'app').glob('*.py'))
    source_stamp=max(source_stamp,(ROOT/'app/README.txt').stat().st_mtime,(ROOT/'packaging/build_current_release.py').stat().st_mtime)
    while not all((OUT/(t+'.json')).is_file() and (OUT/(t+'.json')).stat().st_mtime>=source_stamp for t in ['macos-arm64','ubuntu-x64']):
        allowed()
        if time.monotonic()>deadline:raise TimeoutError('Native package build did not complete')
        time.sleep(5)
    files=[]
    for target in ['macos-arm64','ubuntu-x64']:
        meta=json.loads((OUT/(target+'.json')).read_text());assert meta['version']==VERSION
        files.extend(f for f in meta['files'] if 'update' not in f['name'])
    for f in files:
        p=OUT/f['name']
        if p.stat().st_size!=f['bytes'] or digest(p)!=f['sha256']:raise ValueError('Candidate changed: '+p.name)
    tag='v'+VERSION
    p=run(['release','view',tag,'--repo',REPO,'--json','isDraft'],check=False)
    if p.returncode:
        if 'not found' not in p.stderr.lower():raise RuntimeError(p.stderr[-400:])
        run(['release','create',tag,'--repo',REPO,'--draft','--target','main','--title','Freedom GPT '+VERSION+' · Windows / Ubuntu / macOS','--notes-file',ROOT/'release'/('notes-v'+VERSION+'.md')])
    elif not json.loads(p.stdout)['isDraft']:
        raise ValueError('Candidate release is already public; refusing to replace it')
    release_id=json.loads(run(['release','view',tag,'--repo',REPO,'--json','databaseId']).stdout)['databaseId']
    def upload(f):
        for attempt in range(3):
            release=json.loads(run(['api','repos/'+REPO+'/releases/'+str(release_id)]).stdout)
            if not release['draft']:raise ValueError('Release stopped being a draft')
            asset=next((a for a in release['assets'] if a['name']==f['name']),None)
            if asset and asset.get('state')=='uploaded' and asset['size']==f['bytes'] and asset.get('digest')=='sha256:'+f['sha256']:
                state('candidate_verified',asset=f['name'],bytes=f['bytes']);break
            if asset:run(['api','--method','DELETE','repos/'+REPO+'/releases/assets/'+str(asset['id'])])
            state('uploading_native_candidate',asset=f['name'],bytes=f['bytes'],attempt=attempt+1)
            result=run(['release','upload',tag,OUT/f['name'],'--repo',REPO],timeout=10800,check=False)
            if result.returncode and attempt==2:raise RuntimeError(result.stderr[-700:])
        else:raise RuntimeError('Candidate upload did not verify')
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(upload,files))
    state('native_candidates_uploaded',assets=[f['name'] for f in files],published=False)


if __name__=='__main__':
    import msvcrt
    lock=(ROOT/'.tmp/native-upload-1.7.0.lock').open('a+b')
    lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise SystemExit('A native candidate uploader already owns this release')
    try:main()
    finally:lock.close()
