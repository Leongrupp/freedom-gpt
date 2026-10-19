"""Install-relative configuration. No account, model weights or personal history in the release."""
import json,os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
try:PRIVATE=json.loads((ROOT/'data/private-runtime.json').read_text(encoding='utf8'))
except (OSError,ValueError):PRIVATE={}
STACK=pathlib.Path(PRIVATE['stack']) if PRIVATE.get('stack') else ROOT/'stack'
HOME=pathlib.Path(PRIVATE['home']) if PRIVATE.get('home') else STACK/'hermes-runtime'
SOURCE=ROOT/'runtime/hermes'
for item in ['data','logs','.tmp','.cache','workspaces','uploads','output','archive','stack/models','stack/logs','stack/.tmp','stack/.cache','stack/creative-kit/models','stack/creative-kit/.tmp','stack/creative-kit/logs']:(ROOT/item).mkdir(parents=True,exist_ok=True)
HOME.mkdir(parents=True,exist_ok=True)
os.environ.update(HERMES_HOME=str(HOME),PYTHONPATH=os.pathsep.join([str(SOURCE),str(ROOT/'runtime/python/Lib/site-packages'),str(ROOT/'runtime/freedom'),str(ROOT)]),
    FREEDOM_ROOT=str(ROOT),FREEDOM_STACK=str(STACK),FREEDOM_HERMES_SOURCE=str(SOURCE),TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),
    PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_TELEMETRY='1')
os.environ['PATH']=str(ROOT/'runtime/cuda')+os.pathsep+os.environ.get('PATH','')
sys.path[:0]=[str(SOURCE),str(ROOT/'runtime/python/Lib/site-packages'),str(ROOT/'runtime/freedom')]
def read(path,default=None):
 try:return json.loads(path.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return default
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.new');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');os.replace(tmp,path)
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
 if script.is_file():subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],cwd=STACK,env=os.environ.copy(),creationflags=subprocess.CREATE_NO_WINDOW)
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
       'compression':{'enabled':True,'threshold_tokens':min(32768,int(context*.75))},
       'auxiliary':{'vision':{'provider':'custom','model':ident,'base_url':url,'api_key':'local','timeout':240},
                    'compression':{'provider':'custom','model':ident,'base_url':url,'api_key':'local'}},
       'telemetry':{'enabled':False},'database':{'journal_mode':'delete','synchronous':'FULL'},'plugins':{'enabled':['coding-continuity','local-qwen-image']},
       'image_gen':{'provider':'local-qwen-image'},'memory':{'provider':'coding-continuity'}}
 (HOME/'config.yaml').write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf8')
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
