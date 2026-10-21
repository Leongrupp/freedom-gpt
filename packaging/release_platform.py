"""Repackage already verified platform stages locally. Never fetch or publish."""
import argparse,json,pathlib,shutil
from platform_bundle import ROOT,APP,VERSION,ROOT_FILES,MODULES,manifest,package_mac,package_linux,sha,mode
from sign_update import build_platform

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--target',choices=['ubuntu-x64','macos-arm64'],required=True);args=parser.parse_args();target=args.target
 app=ROOT/'build/platforms'/VERSION/target/'App'
 if not (app/'freedom-bundle.json').is_file():raise ValueError('Prepare this platform with platform_bundle.py first')
 for name in ROOT_FILES:shutil.copy2(APP/name,app/name)
 for name in MODULES:shutil.copy2(APP/name,app/'runtime/freedom'/name)
 shutil.copy2(ROOT/'packaging/portable_install.py',app/'runtime/freedom/portable_install.py')
 for source,name in [('posix-launch.sh','Start-FreedomGPT.sh'),('posix-stop.sh','Stop-FreedomGPT.sh'),('posix-install.sh','Install-FreedomGPT.sh')]:shutil.copy2(ROOT/'packaging'/source,app/name)
 from feature_payload import apply as stage_features
 stage_features(app)
 manifest(app,target);out=ROOT/'release/platforms'/VERSION
 files=package_mac(app,out) if target=='macos-arm64' else package_linux(app,out)
 files+=build_platform(app,out,target,mode)
 verification=ROOT/'logs'/(('ubuntu-clean-pc-verification-' if target=='ubuntu-x64' else 'macos-all-native-audit-')+VERSION+'.json')
 report=json.loads(verification.read_text()) if verification.is_file() else {}
 result={'version':VERSION,'platform':target,'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in files],'published':False,'core_runtime_tested':target=='ubuntu-x64' and report.get('passed') is True,'native_mac_tested':False if target=='macos-arm64' else None,'static_audit_passed':report.get('static_checks_passed') if target=='macos-arm64' else None}
 (out/(target+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
