import json,os,pathlib,subprocess,time,traceback
root=pathlib.Path('/work');release=root/'release/platforms/1.7.0';checks={};details={};env=os.environ.copy();env.update(FREEDOM_INSTALL_DIR='/qa/RunInstaller',HOME='/qa/installer-user',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
pathlib.Path(env['HOME']).mkdir(parents=True,exist_ok=True)
def run(args,timeout=240):return subprocess.run(list(map(str,args)),capture_output=True,text=True,env=env,timeout=timeout)
try:
 before=set(pathlib.Path('/qa').glob('.freedom-setup-*'))
 r=run(['sh',release/'FreedomGPT-Setup-1.7.0-Ubuntu-x64.run','--install-only']);details['run_installer']=r.stdout[-500:]+r.stderr[-1500:];checks['run_installer_without_python_or_network']=r.returncode==0
 checks['temporary_extraction_cleaned']=set(pathlib.Path('/qa').glob('.freedom-setup-*'))==before
 py=pathlib.Path('/qa/RunInstaller/runtime/python/bin/python3');r=run([py,'-B','-s','-c','import psutil,requests,PIL.Image,cryptography,openai,mcp;print("private imports OK")']);checks['installed_run_python_imports']=r.returncode==0
 r=run(['dpkg-deb','--info',release/'FreedomGPT-1.7.0-Ubuntu-amd64.deb']);checks['deb_structure_valid']=r.returncode==0;details['deb_control']=r.stdout[-1400:]
 r=run(['dpkg','--install',release/'FreedomGPT-1.7.0-Ubuntu-amd64.deb']);checks['deb_installed_offline']=r.returncode==0;details['deb_install']=r.stdout[-500:]+r.stderr[-1000:]
 r=run(['/opt/freedom-gpt/Start-FreedomGPT.sh','--target','/qa/DebInstaller','--install-only']);checks['deb_first_run_install']=r.returncode==0;details['deb_first_run']=r.stdout[-500:]+r.stderr[-1000:]
 r=run(['/qa/DebInstaller/runtime/python/bin/python3','-B','-s','-c','import psutil,requests,PIL.Image,cryptography,openai,mcp;print("private imports OK")']);checks['deb_private_imports']=r.returncode==0
 checks['still_no_system_python']=not pathlib.Path('/usr/bin/python3').exists()
except Exception as exc:details['error']=str(exc);details['traceback']=traceback.format_exc()
report={'checks':checks,'details':details,'passed':bool(checks) and all(checks.values()) and 'error' not in details,'environment':'Ubuntu24.04 without network/system Python; real .run and dpkg installation'}
(root/'logs/ubuntu-installers-verification-1.7.0.json').write_text(json.dumps(report,indent=2));print(json.dumps({'checks':checks,'error':details.get('error'),'passed':report['passed']},indent=2),flush=True)
if not report['passed']:raise SystemExit(1)
