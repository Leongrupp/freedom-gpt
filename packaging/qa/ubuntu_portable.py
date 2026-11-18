import json,os,pathlib,shutil,subprocess,sys,time,urllib.request,urllib.error,traceback
ROOT=pathlib.Path('/work');SOURCE=pathlib.Path('/qa/source170/FreedomGPT');TARGET=pathlib.Path(os.environ.get('FREEDOM_QA_TARGET','/qa/App170'))
checks={};details={};env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1',UV_OFFLINE='1',HOME='/qa/user')
pathlib.Path(env['HOME']).mkdir(parents=True,exist_ok=True)
def run(args,timeout=180,**kw):return subprocess.run(list(map(str,args)),env=env,capture_output=True,text=True,timeout=timeout,**kw)
def call(path,value=None,token=None):
 req=urllib.request.Request('http://127.0.0.1:19166/api/'+path,data=json.dumps(value).encode() if value is not None else None,headers={'Content-Type':'application/json',**({'X-Freedom-Token':token} if token else {})})
 with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
def launch():
 result=run([TARGET/'runtime/python/bin/python3','-B','-s',TARGET/'launch.py','--no-browser'])
 (ROOT/'logs/ubuntu-launcher.log').write_text(result.stdout+'\n'+result.stderr)
 if result.returncode:raise RuntimeError('Launcher: '+result.stderr[-1600:])
 for _ in range(300):
  try:
   if call('health').get('gateway_ready'):return
  except (OSError,urllib.error.URLError):pass
  time.sleep(.5)
 raise RuntimeError('Agent gateway timed out')
def stop():
 result=run([TARGET/'runtime/python/bin/python3','-B','-s',TARGET/'stop.py'])
 (ROOT/'logs/ubuntu-stop.log').write_text(result.stdout+'\n'+result.stderr);return result.returncode==0
try:
 checks['no_system_python']=not pathlib.Path('/usr/bin/python3').exists()
 result=run([SOURCE/'runtime/python/bin/python3','-B','-s',SOURCE/'runtime/freedom/portable_install.py','--source',SOURCE,'--target',TARGET,'--install-only'],360)
 if result.returncode:raise RuntimeError('Install: '+result.stderr[-1600:])
 checks['self_contained_install']=True
 (TARGET/'data/settings.json').write_text(json.dumps({'auto_update':False,'ui_port':19166,'model_port':19135,'external_url':'http://127.0.0.1:19179/v1','external_model':'freedom-test','external_context':65536}))
 launch();checks['ui_and_agent_ready']=True
 checks['empty_chat_history']=not call('sessions')['sessions']
 checks['hardware_detected']=bool(call('library').get('hardware',{}).get('cpu'))
 boot=call('bootstrap');checks['public_support_links']=boot.get('support',{}).get('telegram')=='https://t.me/AI1rus';token=boot['token'];created=call('sessions',{'title':'Ubuntu offline QA'},token);sid=created['id'];checks['create_chat_rpc']=bool(sid)
 for _ in range(90):
  system=call('system')
  if system['state'] not in {'checking','repairing','idle'}:break
  time.sleep(.5)
 details['components']=system;checks['required_components_ready']=system.get('ready') is True
 node=run([TARGET/'runtime/node/bin/node','--version']);details['node_version']=node.stdout.strip();checks['bundled_node_works']=node.returncode==0
 pip=run([TARGET/'runtime/python/bin/pip','--version']);details['pip']=pip.stdout.strip();checks['relocatable_pip']=pip.returncode==0
 sys.path.insert(0,str(ROOT/'packaging'));from check_installed_features import check;details['features']=check('http://127.0.0.1:19166',TARGET,token);checks['new_features']=all(details['features'].values())
 checks['stop_app']=stop();launch();checks['restart_preserves_chat']=sid in {s['id'] for s in call('sessions')['sessions']};checks['stop_after_restart']=stop()
 # Remove one importable package while keeping dist-info, like a damaged installation.
 package=TARGET/'runtime/python/lib/python3.14/site-packages/dotenv';saved=TARGET/'archive/qa-dotenv';shutil.move(package,saved)
 code="import bootstrap;from preflight import ensure;print(ensure(bootstrap.ROOT))"
 repaired=run([TARGET/'runtime/python/bin/python3','-B','-s','-c',code],180,cwd=TARGET)
 details['repair_result']=repaired.stdout.strip()+' '+repaired.stderr[-700:];checks['offline_dependency_repair']=repaired.returncode==0 and package.is_dir()
 if not package.exists():shutil.move(saved,package)
 settings=TARGET/'data/settings.json';sentinel=TARGET/'workspaces/preserve.txt';sentinel.write_text('preserved')
 again=run([SOURCE/'runtime/python/bin/python3','-B','-s',SOURCE/'runtime/freedom/portable_install.py','--source',SOURCE,'--target',TARGET,'--install-only'],180)
 checks['reinstall_preserves_data']=again.returncode==0 and sentinel.read_text()=='preserved' and json.loads(settings.read_text())['auto_update'] is False
except Exception as exc:
 details['error']=str(exc);details['traceback']=traceback.format_exc()
finally:
 for name in ['logs/launcher.log','stack/hermes-runtime/logs/gateway.log','logs/python-repair.log']:
  path=TARGET/name
  if path.is_file():(ROOT/'logs'/('ubuntu-'+path.name)).write_text(path.read_text(errors='replace')[-18000:])
 if (TARGET/'stop.py').is_file():
  try:stop()
  except Exception:pass
 report={'version':'1.7.0','platform':'ubuntu-x64','checks':checks,'details':details,'passed':bool(checks) and all(checks.values()) and 'error' not in details,'environment':'Official Ubuntu 24.04, --network none, no system Python','desktop_or_gpu_tested':False}
 (ROOT/'logs/ubuntu-clean-pc-verification-1.7.0.json').write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed'],'checks':checks,'error':details.get('error')},indent=2),flush=True)
if not report['passed']:raise SystemExit(1)

