"""Install-relative configuration. No account, model weights or personal history in the release."""
import json,os,pathlib,sys,sysconfig,threading,time,uuid
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parent
try:PRIVATE=json.loads((ROOT/'data/private-runtime.json').read_text(encoding='utf8'))
except (OSError,ValueError):PRIVATE={}
STACK=pathlib.Path(PRIVATE['stack']) if PRIVATE.get('stack') else ROOT/'stack'
HOME=pathlib.Path(PRIVATE['home']) if PRIVATE.get('home') else STACK/'hermes-runtime'
SOURCE=ROOT/'runtime/hermes'
SITE_PACKAGES=pathlib.Path(sysconfig.get_path('purelib'))
for item in ['data','logs','.tmp','.cache','workspaces','uploads','output','archive','stack/models','stack/logs','stack/.tmp','stack/.cache','stack/creative-kit/models','stack/creative-kit/.tmp','stack/creative-kit/logs']:(ROOT/item).mkdir(parents=True,exist_ok=True)
HOME.mkdir(parents=True,exist_ok=True)
os.environ.update(HERMES_HOME=str(HOME),PYTHONPATH=os.pathsep.join([str(SOURCE),str(SITE_PACKAGES),str(ROOT/'runtime/freedom'),str(ROOT)]),
    FREEDOM_ROOT=str(ROOT),FREEDOM_STACK=str(STACK),FREEDOM_HERMES_SOURCE=str(SOURCE),TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),TMPDIR=str(ROOT/'.tmp'),
    PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTHONIOENCODING='utf-8',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_TELEMETRY='1')
os.environ['PATH']=os.pathsep.join([str(ROOT/'runtime/node/bin'),str(ROOT/'runtime/node'),str(ROOT/'runtime/cuda'),os.environ.get('PATH','')])
os.environ.update(PIP_CACHE_DIR=str(ROOT/'.cache/pip'),UV_CACHE_DIR=str(ROOT/'.cache/uv'),npm_config_cache=str(ROOT/'.cache/npm'))
try:
 import certifi
 os.environ.setdefault('SSL_CERT_FILE',certifi.where())
except ImportError:pass
sys.path[:0]=[str(SOURCE),str(SITE_PACKAGES),str(ROOT/'runtime/freedom')]
from platform_support import PROCESS_FLAGS
_DLL_DIRECTORIES=[]
if os.name=='nt' and hasattr(os,'add_dll_directory'):
 for directory in [ROOT/'runtime/python',ROOT/'runtime/system/lib']:
  if directory.is_dir():_DLL_DIRECTORIES.append(os.add_dll_directory(str(directory)))
def read(path,default=None):
 for attempt in range(6):
  try:return json.loads(path.read_text(encoding='utf-8-sig'))
  except PermissionError:
   if attempt==5:return default
   time.sleep(min(.1,.01*2**attempt))
  except (OSError,ValueError):return default
_WRITE_LOCK=threading.RLock()
def write(path,data):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 # Readers and antivirus can briefly hold the destination open on Windows.
 # A unique sibling also prevents concurrent writers from sharing a .new file.
 with _WRITE_LOCK:
  tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.new')
  try:
   tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
   for attempt in range(10):
    try:os.replace(tmp,path);break
    except PermissionError:
     if attempt==9:raise
     time.sleep(min(.5,.02*2**attempt))
  finally:
   tmp.unlink(missing_ok=True)
def config():return {'active':None,'model_port':19135,'ui_port':19166,**read(ROOT/'data/settings.json',{})}
def workspace_root():return pathlib.Path(PRIVATE.get('workspace_root') or ROOT/'workspaces').resolve()
def ensure_private_model():
 if not PRIVATE.get('preserve_agent_config'):return
 import subprocess,urllib.request
 try:
  with urllib.request.urlopen(model_url().removesuffix('/v1')+'/health',timeout=2) as response:
   if json.load(response).get('status')=='ok':return
 except Exception:pass
 script=STACK/'ensure-model.ps1'
 if sys.platform=='win32' and script.is_file():subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],cwd=STACK,env=os.environ.copy(),creationflags=PROCESS_FLAGS)
def model_url():return config().get('external_url') or f"http://127.0.0.1:{config()['model_port']}/v1"
def model_id():return config().get('external_model') or 'freedom-local'
def local_history(sessions,previous=None):
 # Native Hermes resumes cli history; runtime turns may have changed source to local.
 # Imported data acquires this Windows user's local ownership on first native resume.
 for session in sessions:
  cwd=str(session.get('cwd') or '')
  session['cwd']=str(ROOT)+cwd[len(previous):] if previous and cwd.startswith(previous) else str(ROOT/'workspaces')
  session.update(source='cli',user_id=None,model=model_id(),model_config=json.dumps({'provider':'custom','base_url':model_url()}))
 return sessions
def context_size():return config().get('external_context') or read(STACK/'server-settings.json',{}).get('context',65536)
def write_hermes(context=None):
 if PRIVATE.get('preserve_agent_config'):return
 import hermes_yaml as yaml
 context=context or context_size()
 cfg=config();url=model_url();ident=model_id()
 data={'model':{'default':ident,'provider':'custom','base_url':url,'api_key':'local','context_length':context,'ollama_num_ctx':context},
       'model_aliases':{'freedom-active':{'model':ident,'provider':'custom','base_url':url,'api_key':'local'}},
       'custom_providers':[{'name':'direct-local','base_url':url,'api_key':'local'}],
       'toolsets':['hermes-cli','vision','image_gen'],'terminal':{'backend':'local','cwd':str(ROOT/'workspaces')},
       'compression':{'enabled':True,'threshold':.5},
         'tool_loop_guardrails':{'hard_stop_enabled':True,'warnings_enabled':True,
                                 'hard_stop_after':{'exact_failure':2,'idempotent_no_progress':3,'same_tool_failure':8},
                                 'warn_after':{'exact_failure':1,'idempotent_no_progress':2,'same_tool_failure':2}},
       'auxiliary':{'vision':{'provider':'custom','model':ident,'base_url':url,'api_key':'local','timeout':240},
                    'compression':{'provider':'custom','model':ident,'base_url':url,'api_key':'local'}},
       'telemetry':{'enabled':False},'database':{'journal_mode':'delete','synchronous':'FULL'},'plugins':{'enabled':['coding-continuity','local-qwen-image','freedom-accounts','freedom-preview']},
       'image_gen':{'provider':'local-qwen-image'},'memory':{'provider':'coding-continuity'}}
 path=HOME/'config.yaml'
 previous=path.read_text(encoding='utf-8-sig') if path.exists() else None
 existing=yaml.safe_load(previous) if previous is not None else {}
 if existing is None:existing={}
 if not isinstance(existing,dict):raise ValueError('Agent configuration must be a YAML mapping; the original file was preserved.')
 # Defaults fill gaps. Only the active model route is managed by the application.
 import copy,hashlib
 def defaults(target,source):
  for key,value in source.items():
   if key not in target:target[key]=copy.deepcopy(value)
   elif isinstance(value,dict) and isinstance(target[key],dict):defaults(target[key],value)
 merged=copy.deepcopy(existing);defaults(merged,data)
 for section in ('model','model_aliases','auxiliary','plugins'):
  if not isinstance(merged[section],dict):raise ValueError('Invalid agent configuration section: '+section+'; original preserved.')
 merged['model'].update(data['model'])
 merged['model_aliases']['freedom-active']=data['model_aliases']['freedom-active']
 for name,value in data['auxiliary'].items():
  if not isinstance(merged['auxiliary'].get(name),dict):raise ValueError('Invalid auxiliary configuration; original preserved.')
  merged['auxiliary'][name].update({k:v for k,v in value.items() if k!='timeout'})
 providers=merged.get('custom_providers')
 if not isinstance(providers,list):raise ValueError('Invalid custom providers; original preserved.')
 providers[:]=[item for item in providers if not isinstance(item,dict) or item.get('name')!='direct-local']+[data['custom_providers'][0]]
 enabled=merged['plugins'].get('enabled',[])
 if not isinstance(enabled,list):raise ValueError('Invalid enabled plugins; original preserved.')
 merged['plugins']['enabled']=list(dict.fromkeys(enabled+data['plugins']['enabled']))
 if merged==existing:return
 if previous is not None:
  backup=ROOT/'archive/agent-config';backup.mkdir(parents=True,exist_ok=True)
  target=backup/(hashlib.sha256(previous.encode('utf-8')).hexdigest()+'.yaml')
  if not target.exists():target.write_text(previous,encoding='utf-8')
 temp=path.with_name('config-'+uuid.uuid4().hex+'.new')
 try:
  with temp.open('w',encoding='utf-8') as stream:
   stream.write(yaml.safe_dump(merged,allow_unicode=True,sort_keys=False));stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path)
 finally:temp.unlink(missing_ok=True)
def relocate():
 previous=read(ROOT/'data/install-root.json',{}).get('root')
 if previous and previous!=str(ROOT):
  import sqlite3
  database=ROOT/'data/interface.sqlite'
  if database.exists():
   with sqlite3.connect(database) as conn:
    for table in ['files','artifacts']:
     conn.execute(f'UPDATE {table} SET path=replace(path,?,?) WHERE path LIKE ?',(previous,str(ROOT),previous+'%'))
  # Upstream export/import resets runtime ownership and preserves compacted history.
  # Rewriting frozen policy JSON directly would invalidate its identity fingerprints.
  database=HOME/'state.db'
  if database.exists():
   import time,uuid
   from hermes_state import SessionDB
   donor=SessionDB(database,read_only=True)
   try:sessions=donor.export_all(include_inactive=True)
   finally:donor.close()
   sessions=local_history(sessions,previous)
   token=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
   archive=ROOT/'archive'/('relocation-'+token);archive.mkdir(parents=True)
   source=sqlite3.connect(database);backup=sqlite3.connect(archive/'state.db')
   try:source.backup(backup)
   finally:backup.close();source.close()
   replacement=HOME/('relocated-'+token+'.db');target=SessionDB(replacement)
   try:report=target.import_sessions(sessions)
   finally:target.close()
   if not report.get('ok'):raise ValueError('Не удалось восстановить историю после переноса. Резервная копия: '+str(archive))
   os.replace(replacement,database);write(archive/'report.json',report)
  for binding in (HOME/'continuity').glob('*/project.json'):
   item=read(binding,{})
   if str(item.get('project','')).startswith(previous):item['project']=str(ROOT)+item['project'][len(previous):];write(binding,item)
 write(ROOT/'data/install-root.json',{'root':str(ROOT)})
def import_pending_history():
 pending=ROOT/'data/history-to-import.json'
 if not pending.is_file():return
 from hermes_state import SessionDB
 database=SessionDB(HOME/'state.db')
 try:result=database.import_sessions(local_history(read(pending,[])))
 finally:database.close()
 write(ROOT/'data/history-import-report.json',result)
 if not result.get('ok'):raise ValueError('Не удалось импортировать историю. Экспорт сохранён в data/history-to-import.json; подробности в data/history-import-report.json.')
 pending.replace(pending.with_suffix('.imported.json'))
