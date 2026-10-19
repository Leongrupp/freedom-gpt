"""Resolve no code: download exact binary wheels for each portable Python ABI."""
import argparse,concurrent.futures,hashlib,json,os,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parent.parent
PLATFORMS={'ubuntu-x64':['manylinux_2_28_x86_64','manylinux2014_x86_64','manylinux_2_17_x86_64'],
 'macos-arm64':['macosx_11_0_arm64','macosx_12_0_arm64','macosx_13_0_arm64','macosx_14_0_arm64','macosx_15_0_arm64','macosx_26_0_arm64'],'windows-x64':['win_amd64']}
def fetch(pair):
 target,platforms=pair;folder=ROOT/'.cache/platforms/wheels'/target;folder.mkdir(parents=True,exist_ok=True)
 args=[sys.executable,'-m','pip','download','--no-deps','--only-binary=:all:','--python-version','3.14','--implementation','cp','--abi','cp314','--abi','abi3','--abi','none','--dest',str(folder),'--cache-dir',str(ROOT/'.cache/pip-platforms'),'-r',str(ROOT/'packaging/requirements-portable.lock')]
 for platform in platforms:args+=['--platform',platform]
 temporary=ROOT/'.tmp/wheel-downloads'/target;temporary.mkdir(parents=True,exist_ok=True)
 env=os.environ.copy();env.update(TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary),PIP_CACHE_DIR=str(ROOT/'.cache/pip-platforms'))
 with (ROOT/'logs'/('wheels-'+target+'.log')).open('wb') as log:result=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=log)
 if result.returncode:raise RuntimeError('Wheel download failed: '+target+'; see logs/wheels-'+target+'.log')
 files=[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.glob('*.whl'))]
 (folder/'manifest.json').write_text(json.dumps(files,indent=2));print('WHEELS VERIFIED '+target+' '+str(len(files)),flush=True);return target
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--target',choices=PLATFORMS);args=parser.parse_args()
 targets={args.target:PLATFORMS[args.target]} if args.target else PLATFORMS
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,targets.items()))
if __name__=='__main__':main()
