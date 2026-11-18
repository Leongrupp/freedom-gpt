"""Build a new version using existing clean native runtimes; no publishing."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'app/version.json').read_text())['version']
OUT=ROOT/'logs'/('release-'+VERSION)
OUT.mkdir(parents=True,exist_ok=True)


def run(stage,args):
    (OUT/'build-status.json').write_text(json.dumps({'stage':stage,'time':time.time(),'version':VERSION}),encoding='utf8')
    print(stage,flush=True)
    env=os.environ.copy();env.update(TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),PYTHONDONTWRITEBYTECODE='1')
    with (OUT/(stage+'.log')).open('wb') as log:
        p=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=ROOT,env=env,stdout=log,stderr=log)
    if p.returncode:raise RuntimeError(stage+' failed; inspect '+str(OUT/(stage+'.log')))


def main():
    from platform_bundle import ROOT_FILES
    windows=ROOT/'build'/('FreedomGPT-'+VERSION)
    for name in ROOT_FILES:shutil.copy2(ROOT/'app'/name,windows/name)
    # Only immutable binary runtime files are hard-linked. All mutable app,
    # Hermes, manifest and generated files get separate physical copies.
    for target in ('ubuntu-x64','macos-arm64'):
        source=ROOT/'build/platforms/1.6.0'/target/'App'
        dest=ROOT/'build/platforms'/VERSION/target/'App'
        if not dest.exists():
            def copy(a,b):
                rel=pathlib.Path(a).relative_to(source).as_posix()
                if rel.startswith(('runtime/python/','runtime/node/','runtime/llama/','runtime/sd/','runtime/wheels/')):
                    os.link(a,b);return b
                return shutil.copy2(a,b)
            shutil.copytree(source,dest,copy_function=copy,ignore=shutil.ignore_patterns('data','.tmp','.cache','logs','output','uploads','workspaces','__pycache__','*.pyc'))
        for folder in ('dist','public'):
            shutil.copytree(ROOT/'app'/folder,dest/folder,dirs_exist_ok=True)
        marker=dest/'freedom-bundle.json'
        data=json.loads(marker.read_text());data['version']=VERSION
        marker.write_text(json.dumps(data,indent=2),encoding='utf8')
        run(target+'-packages',['packaging/release_platform.py','--target',target])
    run('windows-packages',['packaging/release.py'])
    print('PACKAGES_BUILT',VERSION,flush=True)


if __name__=='__main__':main()
