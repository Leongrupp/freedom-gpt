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


def clone_native(source,dest):
    def copy(a,b):
        rel=pathlib.Path(a).relative_to(source).as_posix()
        target_path=pathlib.Path(b)
        if target_path.is_file():
            sa,sb=os.stat(a),os.stat(b)
            if sa.st_size==sb.st_size and sa.st_mtime_ns==sb.st_mtime_ns:return b
            target_path.unlink()
        if rel.startswith(('runtime/python/','runtime/node/','runtime/llama/','runtime/sd/','runtime/wheels/')):
            os.link(a,b);return b
        return shutil.copy2(a,b)
    def ignore(parent,names):
        blocked={'__pycache__'}|{n for n in names if n.endswith('.pyc')}
        if pathlib.Path(parent)==source:blocked|={'data','.tmp','.cache','logs','output','uploads','workspaces','.hermes'}
        return [n for n in names if n in blocked]
    shutil.copytree(source,dest,dirs_exist_ok=True,copy_function=copy,ignore=ignore)
    # A directory can exist after an interrupted copy. Assert the complete
    # donor payload before overlaying the current application sources.
    missing=[p.relative_to(source).as_posix() for p in source.rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'
             and p.relative_to(source).parts[0] not in {'data','.tmp','.cache','logs','output','uploads','workspaces','.hermes'}
             and not (dest/p.relative_to(source)).is_file()]
    if missing:raise RuntimeError('Incomplete native runtime: '+str(missing[:10]))


def main():
    from platform_bundle import ROOT_FILES
    windows=ROOT/'build'/('FreedomGPT-'+VERSION)
    for name in ROOT_FILES:shutil.copy2(ROOT/'app'/name,windows/name)
    # Only immutable binary runtime files are hard-linked. All mutable app,
    # Hermes, manifest and generated files get separate physical copies.
    for target in ('ubuntu-x64','macos-arm64'):
        source=ROOT/'build/platforms/1.6.0'/target/'App'
        dest=ROOT/'build/platforms'/VERSION/target/'App'
        clone_native(source,dest)
        for folder in ('dist','public'):
            shutil.copytree(ROOT/'app'/folder,dest/folder,dirs_exist_ok=True)
        marker=dest/'freedom-bundle.json'
        data=json.loads(marker.read_text());data['version']=VERSION
        marker.write_text(json.dumps(data,indent=2),encoding='utf8')
        run(target+'-packages',['packaging/release_platform.py','--target',target])
    # Windows already has its independent clean-install proof; native repair
    # need not rewrite identical Windows archives.
    if '--posix-only' not in sys.argv:run('windows-packages',['packaging/release.py'])
    print('PACKAGES_BUILT',VERSION,flush=True)


if __name__=='__main__':main()
