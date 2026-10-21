"""Freedom GPT: local-only presentation over the existing Hermes session authority."""
from __future__ import annotations
import asyncio, base64, contextlib, datetime, hashlib, io, json, logging, mimetypes, os, pathlib, re, secrets, shutil, sqlite3, subprocess, sys, time, uuid

ROOT=pathlib.Path(__file__).resolve().parent
import bootstrap as portable
from library import library, register as register_library
from video import videos, register as register_video
from system_check import system,register as register_system
STACK=portable.STACK
PROJECTS=portable.workspace_root() if portable.PRIVATE else ROOT.resolve()
CREATIVE=STACK/'creative-kit'
HERMES_SOURCE=portable.SOURCE
PORT=portable.config()['ui_port']
def model_origin():return portable.model_url().removesuffix("/v1")
for name in ('.tmp','.cache','logs','data','uploads','output','archive'):(ROOT/name).mkdir(exist_ok=True,parents=True)
os.environ.update(HERMES_HOME=str(portable.HOME),TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),
    PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',UV_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
os.environ['PATH']=str(pathlib.Path(sys.executable).parent)+os.pathsep+os.environ['PATH']
sys.path.insert(0,str(HERMES_SOURCE))
from aiohttp import web, ClientSession, ClientTimeout
from PIL import Image
from updater import updates,META
import psutil
from hermes_cli.gateway_client import connect_gateway

log=logging.getLogger('freedom')
TOKEN=secrets.token_urlsafe(32)
ALLOWED_ORIGINS={f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'}

def db():
    conn=sqlite3.connect(ROOT/'data/interface.sqlite',timeout=10)
    conn.row_factory=sqlite3.Row
    return conn

with db() as conn:
    conn.executescript('''PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,title TEXT,archived INTEGER DEFAULT 0,pinned INTEGER DEFAULT 0,updated REAL);
    CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,name TEXT,path TEXT,mime TEXT,bytes INTEGER,sha256 TEXT,created REAL);
    CREATE TABLE IF NOT EXISTS turns(input_id TEXT PRIMARY KEY,session_id TEXT,text TEXT,file_ids TEXT,admission_id TEXT,created REAL);
    CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,session_id TEXT,path TEXT,name TEXT,mime TEXT,created REAL,UNIQUE(session_id,path));
    CREATE TABLE IF NOT EXISTS routes(session_id TEXT PRIMARY KEY,model TEXT,url TEXT);
    ''')

def dict_row(row):return dict(row) if row else None
def load_json(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return default
def timestamp():return datetime.datetime.now().astimezone().isoformat()
def body_json(request):return request.json(loads=json.loads)
def error(message,status=400,code=None):return web.json_response({'error':message,**({'code':code} if code else {})},status=status)
def local_project(value):
    path=pathlib.Path(value or ROOT/'workspaces').resolve()
    if not path.is_relative_to(PROJECTS) or not path.is_dir():raise ValueError('Выберите существующую рабочую папку Freedom GPT.')
    return str(path)
def public_file(row):
    return {k:row[k] for k in ('id','name','mime','bytes','sha256') if k in row}
def local_asset(path):
    resolved=pathlib.Path(path).resolve()
    return resolved if resolved.is_relative_to(PROJECTS) and resolved.is_file() else None

def register_artifact(session_id,path):
    file=local_asset(path)
    if file is None:return None
    if artifact_workspace.hidden(file):return None
    mime={'.mp4':'video/mp4','.m4v':'video/mp4','.webm':'video/webm','.mov':'video/quicktime'}.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
    identifier=uuid.uuid4().hex
    with db() as conn:
        conn.execute('INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?)',
            (identifier,session_id,str(file),file.name,mime,time.time()))
        row=conn.execute('SELECT * FROM artifacts WHERE session_id=? AND path=?',(session_id,str(file))).fetchone()
    return {'id':row['id'],'name':row['name'],'mime':row['mime'],'url':'/api/artifacts/'+row['id']}

def find_artifacts(session_id,value):
    found=[]
    def walk(item):
        if isinstance(item,dict):
            for key,val in item.items():
                if key in {'image','image_path','output','output_path','file_path','path'} and isinstance(val,str):
                    if pathlib.Path(val).is_absolute():
                        asset=register_artifact(session_id,val)
                        if asset:found.append(asset)
                if isinstance(val,(dict,list)):walk(val)
        elif isinstance(item,list):
            for part in item:walk(part)
        elif isinstance(item,str):
            if item.lstrip().startswith(('{','[')):
                with contextlib.suppress(ValueError):walk(json.loads(item))
            for candidate in re.findall(r'[A-Za-z]:[/\\][^\n\r<>"|]*?\.(?:png|jpe?g|webp|gif|mp4|webm|mov|m4v|pdf|zip|glb|blend|txt|py|html|exe)(?=[\s\)\]\}.,;]|$)',item,re.I):
                asset=register_artifact(session_id,candidate.strip())
                if asset:found.append(asset)
    walk(value)
    return found

class Bridge:
    def __init__(self):
        self.client=None;self.ready=asyncio.Event();self.sockets=set();self.task=None
        self.error=None;self.snapshots={};self.live={};self.reconnected=0;self.resume_locks={}
    async def start(self):self.task=asyncio.create_task(self.loop())
    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.task
    async def broadcast(self,frame):
        for socket in list(self.sockets):
            try:await asyncio.wait_for(socket.send_json(frame),1)
            except Exception:self.sockets.discard(socket)
    async def loop(self):
        while True:
            try:
                async with connect_gateway() as client:
                    self.client=client;self.error=None;self.ready.set();self.reconnected+=1
                    for sid in list(self.snapshots):
                        with contextlib.suppress(Exception):
                            self.snapshots[sid]=await client.rpc('session.resume',session_id=sid)
                    await self.broadcast({'type':'gateway.connected','reconnected':self.reconnected})
                    while True:
                        event=await client.events.get()
                        if isinstance(event,Exception):raise event
                        params=event.get('params') or {}
                        kind=params.get('type');sid=params.get('session_id');payload=params.get('payload') or {}
                        if sid:
                            workspace.event(sid,kind,params)
                            if kind=='session.control.update':
                                goals.archive_goal(sid,(payload.get('control') or {}).get('goal'))
                            state=self.live.setdefault(sid,{'text':'','active':False,'tool':None,'generation':0})
                            state['generation']=params.get('execution_generation',state['generation'])
                            if kind=='message.start':state.update(active=True,text='',tool=None,started_at=time.time())
                            elif kind=='message.delta':
                                state['active']=True;state['text']+=payload.get('text') or payload.get('delta') or payload.get('content') or ''
                            elif kind=='tool.start':state.update(active=True,tool=payload.get('tool_name') or 'tool',text='')
                            elif kind=='tool.complete':
                                state['tool']=None
                                assets=find_artifacts(sid,payload.get('result'))
                                if assets:await self.broadcast({'type':'artifacts.changed','session_id':sid,'artifacts':assets})
                            elif kind=='message.complete':
                                queue_completion=params.get('execution_generation') is None and payload.get('outcome') in {'cancelled','steered'}
                                if not queue_completion:state.update(active=False,text='',tool=None)
                                find_artifacts(sid,payload.get('text') or payload.get('content') or '')
                            elif kind=='session.info' and 'running' in payload:state['active']=bool(payload['running'])
                        await self.broadcast({**params,'type':'gateway.event','event_type':kind})
            except asyncio.CancelledError:raise
            except Exception as exc:
                self.error=str(exc);self.client=None;self.ready.clear()
                await self.broadcast({'type':'gateway.disconnected','error':'Связь с Freedom GPT прервана. Проверяем состояние; запросы автоматически не повторяются.'})
                log.warning('gateway reconnect: %s',type(exc).__name__)
                await asyncio.sleep(3)
    async def rpc(self,method,**params):
        try:await asyncio.wait_for(self.ready.wait(),40)
        except asyncio.TimeoutError:raise ValueError('Freedom GPT пока недоступен. Повторите проверку через несколько секунд.')
        return await self.client.rpc(method,**params)
    async def resume(self,sid):
        async with self.resume_locks.setdefault(sid,asyncio.Lock()):return await self._resume(sid)
    async def _resume(self,sid):
        snapshot=await self.rpc('session.resume',session_id=sid)
        info=snapshot.get('info') or {}
        if portable.PRIVATE or str(info.get('model') or '').startswith('freedom-api-'):
            self.snapshots[sid]=snapshot
            return snapshot
        with db() as conn:route=conn.execute('SELECT model,url FROM routes WHERE session_id=?',(sid,)).fetchone()
        target=(portable.model_id(),portable.model_url().rstrip('/'))
        if info.get('model') and (info.get('model')!=target[0] or not route or tuple(route)!=target):
            live=self.live.get(sid,{})
            if live.get('active'):raise ValueError('Сначала остановите текущий ответ перед сменой модели.')
            result=await self.rpc('session.mutate',session_id=sid,request_id=uuid.uuid4().hex,expected_revision=snapshot['revision'],expected_generation=snapshot['execution_generation'],operation='model',payload={'model':'freedom-active'})
            if result.get('status')=='confirmation_required':raise ValueError('Freedom GPT требует подтверждения смены модели. Создайте новый чат с выбранной моделью; прежняя история сохранена.')
            with db() as conn:conn.execute('INSERT OR REPLACE INTO routes VALUES(?,?,?)',(sid,*target))
            snapshot=await self.rpc('session.resume',session_id=sid)
        self.snapshots[sid]=snapshot
        return snapshot

bridge=Bridge()
from workspace_features import WorkspaceFeatures, LEARNING_NOTE, EXECUTION_NOTE
workspace=WorkspaceFeatures(ROOT,portable,db,bridge)
from goal_workspace import GoalWorkspace
goals=GoalWorkspace(db,bridge,workspace,videos.busy)
from artifact_workspace import ArtifactWorkspace
artifact_workspace=ArtifactWorkspace(ROOT,PROJECTS,STACK,db,bridge)
from cloud_api import CloudAPI
cloud=CloudAPI(ROOT,portable,db,bridge,register_artifact)
workspace.cloud=cloud
from chat_branches import ChatBranches
branches=ChatBranches(db,bridge,workspace,portable)
from rewards import FreedomRewards
rewards=FreedomRewards(ROOT,portable,db,bridge)
from preview_browser import PreviewBrowser
from model_advisor import ModelAdvisor
from account_connections import AccountConnections
accounts=AccountConnections(ROOT,portable)
advisor=ModelAdvisor(library)
preview=PreviewBrowser(ROOT,portable,bridge,register_artifact)

def image_status():
    item=next((m for m in library.snapshot()['models'] if m['kind']=='image'),None)
    if not item:return {'ready':False,'tested':False,'percent':0,'files':[]}
    return {'ready':item['installed'],'tested':False,'percent':item['percent'],'bytes':item['bytes'],'total':item['total'],
            'model':item['name'],'files':[dict(f,complete=(library.folder(item)/f['name']).is_file()) for f in item['files']],
            'phase':'ready' if item['installed'] else 'downloading','reference_editing':False}

def read_timings():
    result={'tokens_per_second':None,'speed_kind':'last','generated_tokens':None,'prompt_tokens_per_second':None}
    marker=STACK/'.tmp/current-server-log.txt'
    try:
        path=pathlib.Path(marker.read_text(encoding='utf-8-sig').strip()).resolve()
        if not path.is_relative_to(STACK/'logs'):return result
        with path.open('rb') as stream:
            stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-36000));text=stream.read().decode('utf-8','replace')
        for line in text.splitlines():
            if 'n_gen =' in line and 'tg_3s' in line:
                match=re.search(r'n_gen\s*=\s*(\d+).*?tg_3s\s*=\s*([\d.]+)',line)
                if match:result.update(generated_tokens=int(match[1]),tokens_per_second=float(match[2]),speed_kind='live')
            elif 'eval time =' in line:
                match=re.search(r'/\s*(\d+) tokens.*?([\d.]+) tokens per second',line)
                if match:
                    if 'prompt eval' in line:result['prompt_tokens_per_second']=float(match[2])
                    else:result.update(tokens_per_second=float(match[2]),generated_tokens=int(match[1]),speed_kind='last')
    except (OSError,ValueError):pass
    return result

async def monitor(app):
    async with ClientSession(timeout=ClientTimeout(total=2)) as http:
        while True:
            timings=read_timings() if not portable.config().get('external_url') else {'tokens_per_second':None,'speed_kind':'last','generated_tokens':None,'prompt_tokens_per_second':None}
            data={'type':'metrics','time':timestamp(),'gateway_ready':bridge.ready.is_set(),**timings,
                'cpu_percent':psutil.cpu_percent(),'ram_used':psutil.virtual_memory().used,
                'ram_total':psutil.virtual_memory().total,'context_max':portable.context_size(),'context_used':None,'model_ready':False}
            try:
                async with http.get(model_origin()+'/slots') as response:
                    slots=await response.json()
                    if response.status!=200 or not isinstance(slots,list) or not slots:raise ValueError('Slots unavailable')
                    slot=slots[0]
                    data.update(model_ready=True,processing=bool(slot.get('is_processing')),
                        context_used=slot.get('n_prompt_tokens'),context_max=slot.get('n_ctx',65536))
                    if not data['processing']:data['speed_kind']='last'
            except Exception:
                data.update(processing=False)
                try:
                    async with http.get(portable.model_url()+'/models') as response:
                        body=await response.json();data['model_ready']=response.status==200 and any(m.get('id')==portable.model_id() for m in body.get('data',[]))
                except Exception:pass
            try:
                command=['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw','--format=csv,noheader,nounits']
                proc=await asyncio.create_subprocess_exec(*command,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                raw,_=await asyncio.wait_for(proc.communicate(),3)
                row=raw.decode().splitlines()[0].split(',')
                data['gpu']={'name':row[0].strip(),'percent':float(row[1]),'used_mb':float(row[2]),'total_mb':float(row[3]),'temperature':float(row[4]),'watts':float(row[5])}
            except Exception:pass
            active=library.model(portable.config().get('active')) or {}
            data['active_model_name']=active.get('name',portable.config().get('external_model','Выберите модель'))
            data['images']=image_status();app['runtime']['metrics']=data
            await bridge.broadcast(data)
            await asyncio.sleep(2)

async def update_check(request):return web.json_response(updates.request_check())
async def update_settings(request):
    data=await request.json();return web.json_response(updates.enabled(data.get('enabled')))

@web.middleware
async def security(request,handler):
    host=request.host
    if host not in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}:return error('Недопустимый Host.',403)
    origin=request.headers.get('Origin')
    if origin and origin not in ALLOWED_ORIGINS:return error('Только локальный интерфейс.',403)
    if request.path.startswith('/api/') and request.method not in {'GET','HEAD'}:
        if request.headers.get('X-Freedom-Token')!=TOKEN:return error('Локальный сеанс обновлён. Восстанавливаем подключение.',403,'session_expired')
    if request.app.get('update_applying') and request.method not in {'GET','HEAD'}:return error('Обновление устанавливается. Соединение восстановится автоматически.',503,'updating')
    admission=request.method=='POST' and request.path.endswith('/messages')
    if admission:request.app['prompt_admissions']=request.app.get('prompt_admissions',0)+1
    try:response=await handler(request)
    except web.HTTPException:raise
    except Exception as exc:
        log.exception('request failed: %s %s',request.method,request.path)
        response=error(str(exc).replace('Hermes','Freedom GPT').replace('hermes','Freedom GPT')[:500],400)
    finally:
        if admission:request.app['prompt_admissions']-=1
    response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
        'Cache-Control':'no-store' if request.path.startswith('/api/') else 'no-cache'})
    if response.content_type=='text/html':response.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws://127.0.0.1:{PORT} ws://localhost:{PORT}; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    return response

async def health(request):return web.json_response({'application':'Freedom GPT','version':META['version'],'local_build':META.get('local_build'),'installation':hashlib.sha256(str(ROOT).encode()).hexdigest()[:16],'gateway_ready':bridge.ready.is_set()})
async def bootstrap(request):
    active=library.model(portable.config().get('active')) or {}
    return web.json_response({'token':TOKEN,'name':'Freedom GPT','model':active.get('name',portable.config().get('external_model','Выберите модель')),'model_short':active.get('name',portable.config().get('external_model','Модель')),'model_id':portable.model_id(),'first_run':not portable.config().get('onboarded'),
        'version':META['version'],'updates':updates.status(),'context':portable.context_size(),'skills':None,'default_project':str(portable.workspace_root()),'images':image_status(),
        'metrics':request.app['runtime'].get('metrics',{}),'root':str(ROOT),'history_home':str(portable.HOME),'language':portable.config().get('language'),
        'support':None if portable.PRIVATE else META.get('support')})

async def sessions(request):
    rows={}
    for scope in ('stored','live'):
        result=await bridge.rpc('session.list',scope=scope,limit=200)
        for row in result.get('sessions',[]):
            sid=row.get('session_id') or row['id'];rows[sid]=row
    with db() as conn:meta={row['id']:dict(row) for row in conn.execute('SELECT * FROM chats')}
    result=[];branch_rows=branches.rows()
    for sid,row in rows.items():
        settings=meta.get(sid,{})
        result.append({**row,'id':sid,'title':settings.get('title') or row.get('title') or 'Новый чат',
            'archived':bool(settings.get('archived')),'pinned':bool(settings.get('pinned')),
            'created':row.get('started_at'),'branch':branch_rows.get(sid),
            'updated':settings.get('updated') or row.get('started_at') or 0})
    return web.json_response({'sessions':sorted(result,key=lambda x:(x['pinned'],x['updated']),reverse=True)})

async def new_session(request):
    data=await body_json(request);cwd=local_project(data.get('cwd'))
    from hermes_cli.gateway_chat import shell_client_env
    target=cloud.target(data.get('model'))
    if data.get('model') and not target:raise ValueError('Выберите подключённую API-модель.')
    if target:await asyncio.to_thread(cloud.sync_aliases)
    selected=target['id'] if target else portable.model_id()
    endpoint=cloud.proxy_url() if target else portable.model_url()
    snapshot=await bridge.rpc('session.create',request_id=uuid.uuid4().hex,source='cli',cwd=cwd,
        provider='custom',base_url=endpoint,model=selected,**({'api_key':cloud.proxy_key} if target else {}),reasoning='none' if data.get('mode','code')=='code' else 'low',client_env=shell_client_env())
    sid=snapshot['stored_session_id'];bridge.snapshots[sid]=snapshot
    access=data.get('access') or portable.config().get('default_access','manual')
    if access=='full':
        await bridge.rpc('config.set',session_id=sid,key='yolo',value='1')
        snapshot=await bridge.resume(sid)
    # In this installed Hermes version a named create can continue an existing title.
    # Keep presentation titles in our own table so every New Chat is unconditionally fresh.
    with db() as conn:
        conn.execute('INSERT OR IGNORE INTO chats(id,title,updated) VALUES(?,?,?)',(sid,data.get('title'),time.time()))
        conn.execute('INSERT OR REPLACE INTO routes VALUES(?,?,?)',(sid,selected,endpoint.rstrip('/')))
        if target:conn.execute('INSERT INTO workspace_preferences(session_id,selected_model) VALUES(?,?) ON CONFLICT(session_id) DO UPDATE SET selected_model=excluded.selected_model',(sid,selected))
    if preview.process and preview.process.returncode is None:
        with contextlib.suppress(Exception):await preview.call(sid,{'action':'adopt','from':'workspace'})
    return web.json_response({'id':sid,'snapshot':filter_snapshot(snapshot)})

def filter_snapshot(snapshot):
    # The UI never needs credential hints, launch environment or provider secrets.
    info=snapshot.get('info') or {}
    return {**{k:v for k,v in snapshot.items() if k!='info'},'info':{k:info.get(k) for k in
        ('title','model','provider','cwd','tool_count','reasoning_effort','yolo','started_at','last_active_at')},
        'live':bridge.live.get(snapshot.get('stored_session_id'),{}),
        'route':{'provider':info.get('provider'),'model':info.get('model'),
                 'base_url':(info.get('launch_request') or {}).get('base_url')}}

async def session_detail(request):
    sid=request.match_info['sid'];snapshot=await bridge.resume(sid)
    files=[]
    with db() as conn:
        for turn in conn.execute("SELECT * FROM turns WHERE session_id=? AND admission_id<>'' ORDER BY created",(sid,)):
            attached=[]
            for identifier in json.loads(turn['file_ids']):
                row=conn.execute('SELECT * FROM files WHERE id=?',(identifier,)).fetchone()
                if row:attached.append(public_file(dict(row)))
            if attached:files.append({'input_id':turn['input_id'],'text':turn['text'],'created':turn['created'],'files':attached})
    # Discover media in saved replies too, including results produced before this UI update.
    for message in snapshot.get('messages',[])[-50:]:
        if message.get('role') in {'assistant','tool'}:find_artifacts(sid,message.get('content',''))
    artifacts,artifact_trash=await asyncio.to_thread(artifact_workspace.list,sid)
    result={**filter_snapshot(snapshot),'attachments':files,'artifacts':artifacts,'artifact_trash':artifact_trash,'branch':branches.rows().get(sid)}
    result=await workspace.decorate(result)
    try:result['goal_state']=await goals.snapshot(sid)
    except Exception:result['goal_state']={'unavailable':True}
    return web.json_response(result)

async def chat_meta(request):
    sid=request.match_info['sid'];data=await body_json(request)
    with db() as conn:
        conn.execute('INSERT OR IGNORE INTO chats(id,updated) VALUES(?,?)',(sid,time.time()))
        for key in ('title','archived','pinned'):
            if key in data:
                value=str(data[key]).strip()[:160] if key=='title' else int(bool(data[key]))
                conn.execute(f'UPDATE chats SET {key}=? WHERE id=?',(value,sid))
    return web.json_response({'ok':True})

async def submit(request):
    if videos.busy():return error('Сейчас создаётся видео. Дождитесь возврата модели кода или остановите видео.',409)
    sid=request.match_info['sid'];data=await body_json(request)
    text=str(data.get('text') or '').strip()
    if not text or len(text)>100000:return error('Сообщение должно содержать от 1 до 100 000 символов.')
    input_id=str(data.get('input_id') or uuid.uuid4().hex)
    if not re.fullmatch('[a-zA-Z0-9_-]{8,100}',input_id):return error('Некорректный идентификатор запроса.')
    identifiers=data.get('files') or []
    if not isinstance(identifiers,list) or len(identifiers)>8:return error('Не более восьми вложений.')
    with db() as conn:prior=conn.execute('SELECT * FROM turns WHERE input_id=?',(input_id,)).fetchone()
    if prior:
        if prior['session_id']!=sid or prior['text']!=text or json.loads(prior['file_ids'])!=identifiers:return error('Идентификатор уже использован.',409)
        if prior['admission_id']:return web.json_response({'admission_id':prior['admission_id'],'input_id':input_id,'duplicate':True})
    mode=data.get('mode','chat')
    if mode not in {'code','chat','image'}:return error('Неизвестный режим работы.')
    image_api_text=None
    if mode=='image':
        if not image_status()['ready']:return error('Модель изображений ещё скачивается. Прогресс доступен в разделе «Модели».',409)
        if identifiers:return error('Этот генератор работает по тексту. Сначала проанализируйте фото в обычном чате, затем используйте его описание для генерации.',409)
        job_folder=ROOT/'data/image-requests';job_folder.mkdir(exist_ok=True)
        job=job_folder/(input_id+'.json')
        if not job.exists():job.write_text(json.dumps({'prompt':text},ensure_ascii=False),encoding='utf-8')
        command=__import__('shlex').join([sys.executable,str(ROOT/'generate-image-request.py'),str(job)]) if os.name!='nt' else subprocess.list2cmdline([sys.executable,str(ROOT/'generate-image-request.py'),str(job)])
        image_api_text=('Пользователь нажал кнопку создания изображения. Создай реальный PNG локально по описанию ниже. '
            'Если доступен image_generate, используй его. Если такого инструмента нет в текущем списке, '
            'вызови terminal и выполни точно эту установленную локальную команду: '+command+
            '. Описание уже записано в JSON, не подставляй его в командную строку. '
            'Не подменяй результат SVG или текстовым описанием. После успеха сообщи путь к PNG. Описание: '+text)
    snapshot=await bridge.resume(sid)
    was_running=bool(snapshot.get('running'))
    if portable.PRIVATE:
        info=snapshot.get('info') or {}
        route_target=cloud.target(info.get('model'))
        expected_url=cloud.proxy_url() if route_target else portable.model_url()
        # Creation launch_request is immutable after a canonical model mutation.
        # The accepted UI route is updated only after the owner commits that mutation.
        with db() as conn:accepted=conn.execute('SELECT model,url FROM routes WHERE session_id=?',(sid,)).fetchone()
        if info.get('model')!=workspace.selected_model(sid) or info.get('provider') not in {'custom','direct-local'} or not accepted or accepted['model']!=info.get('model') or accepted['url'].rstrip('/')!=expected_url.rstrip('/'):
            return error('Этот сохранённый чат использует другой провайдер. Создайте новый чат для текущей локальной модели.',409)
    reasoning='none' if mode=='code' else 'low'
    if not was_running and (snapshot.get('info') or {}).get('reasoning_effort')!=reasoning:
        await bridge.rpc('config.set',session_id=sid,key='reasoning',value=reasoning,scope='session')
    attachments=[];file_refs=[];selected=[]
    with db() as conn:
        for identifier in identifiers:
            row=conn.execute('SELECT * FROM files WHERE id=?',(identifier,)).fetchone()
            if not row:return error('Вложение не найдено.')
            selected.append(dict(row))
        prior=conn.execute('SELECT * FROM turns WHERE input_id=?',(input_id,)).fetchone()
        if prior and (prior['session_id']!=sid or prior['text']!=text):return error('Идентификатор уже использован.',409)
        conn.execute('INSERT OR IGNORE INTO turns VALUES(?,?,?,?,?,?)',(input_id,sid,text,json.dumps(identifiers),'',time.time()))
    for item in selected:
        if item['mime'].startswith('image/'):
            active=library.model(portable.config().get('active'))
            if active and not any(f['name']=='mmproj.gguf' for f in active['files']):return error('У выбранной модели не установлен визуальный проектор. Выберите Huihui Coder из стандартного набора для анализа фото.',409)
            payload=pathlib.Path(item['path']).read_bytes()
            if item['mime']=='image/bmp':
                output=io.BytesIO()
                with Image.open(io.BytesIO(payload)) as image:image.save(output,format='PNG')
                payload=output.getvalue()
            staged=await bridge.rpc('image.attach_bytes',session_id=sid,content_base64=base64.b64encode(payload).decode(),filename=item['name'])
            attachments.append({'path':staged['path'],'mime':staged['mime']})
        else:
            staged=await bridge.rpc('file.attach',session_id=sid,path=item['path'],name=item['name'])
            file_refs.append(staged['ref_text'])
    turn_params={}
    if attachments:turn_params['attachments']=attachments
    if image_api_text:turn_params['api_text']=image_api_text
    # Keep image annotations and file refs together in the canonical prompt. An api_text
    # override would replace the vision annotation assembled by this Hermes version.
    wire_text=text+('\n\nПрикреплённые пользователем файлы:\n'+'\n'.join(file_refs) if file_refs else '')
    if not attachments and not image_api_text:
        owner_notes=EXECUTION_NOTE+'\nТекущий чат для встроенного просмотра: '+sid
        if workspace.preferences(sid).get('learning',True):owner_notes+='\n'+LEARNING_NOTE
        turn_params['api_text']=wire_text+'\n\n[Настройки владельца: выполнение и память]\n'+owner_notes
    receipt=await bridge.rpc('prompt.submit',session_id=sid,input_id=input_id,text=wire_text,**turn_params)
    workspace.admitted(sid,input_id,receipt,(snapshot.get('info') or {}).get('model'))
    with db() as conn:
        conn.execute('UPDATE turns SET admission_id=? WHERE input_id=?',(receipt.get('admission_id',''),input_id))
        conn.execute('INSERT OR IGNORE INTO chats(id,updated) VALUES(?,?)',(sid,time.time()))
        conn.execute('UPDATE chats SET updated=?,title=CASE WHEN title IS NULL OR title=\'\' THEN ? ELSE title END WHERE id=?',
            (time.time(),str(data.get('text'))[:70],sid))
    if not was_running:
        bridge.live.setdefault(sid,{'text':'','active':True,'tool':None,'generation':receipt.get('execution_generation',0)})
    return web.json_response(receipt)

async def stop(request):
    sid=request.match_info['sid'];snapshot=await bridge.resume(sid)
    # Completion receipts are stored by the native owner. Cancel only queued,
    # failed auto-notifications, preserving all human tasks and their payloads.
    # Otherwise Stop settles one turn and its failed subprocess notices wake it again.
    for pending in snapshot.get('pending',[]):
        text=str(pending.get('text') or '')
        if pending.get('status')=='queued' and str(pending.get('input_id','')).startswith('["completion",') and text.startswith('[IMPORTANT: Background process') and re.search(r'exited \(exit code (?!0\))',text):
            with contextlib.suppress(Exception):
                await bridge.rpc('prompt.cancel',session_id=sid,admission_id=pending['admission_id'])
    control=await goals.snapshot(sid)
    if (control.get('goal') or {}).get('status')=='active':
        await bridge.rpc('session.control',session_id=sid,action='goal.pause')
    return web.json_response(await bridge.rpc('session.interrupt',session_id=sid,execution_generation=snapshot['execution_generation']))

async def respond(request):
    sid=request.match_info['sid'];data=await body_json(request);snapshot=await bridge.resume(sid)
    prompt=next((p for p in snapshot.get('prompts',[]) if p['prompt_id']==data.get('prompt_id')),None)
    if not prompt:return error('Этот запрос уже завершён. Обновите чат.',409)
    kind=prompt['kind'];answer=str(data.get('answer') or '')[:10000]
    if kind=='approval' and answer not in prompt.get('choices',[]):return error('Выберите предложенный вариант.')
    return web.json_response(await bridge.rpc(kind+'.respond',session_id=sid,
        execution_generation=prompt['execution_generation'],prompt_id=prompt['prompt_id'],**({'choice':answer} if kind=='approval' else {'answer':answer})))

async def upload(request):
    reader=await request.multipart();part=await reader.next()
    if part is None or not part.filename:return error('Выберите файл.')
    name=pathlib.Path(part.filename.replace('\\','/')).name[:180]
    if not name or '\x00' in name:return error('Некорректное имя файла.')
    identifier=uuid.uuid4().hex;suffix=pathlib.Path(name).suffix.lower()[:12]
    folder=ROOT/'uploads'/identifier;folder.mkdir();path=folder/('attachment'+suffix)
    size=0;digest=hashlib.sha256()
    with path.open('xb') as stream:
        while chunk:=await part.read_chunk(256*1024):
            size+=len(chunk)
            if size>50*1024**2:raise ValueError('Максимальный размер файла — 50 МБ.')
            if shutil.disk_usage(ROOT).free<300*1024**2:raise ValueError('В папке приложения недостаточно свободного места.')
            stream.write(chunk);digest.update(chunk)
    mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
    if suffix in {'.png','.jpg','.jpeg','.webp','.gif','.bmp'}:
        if size>20*1024**2:raise ValueError('Изображение должно быть меньше 20 МБ.')
        with Image.open(path) as image:
            if image.width*image.height>40_000_000:raise ValueError('Слишком большое разрешение изображения.')
            image.verify()
        mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.gif':'image/gif','.bmp':'image/bmp'}[suffix]
    elif mime.startswith('image/'):
        # SVG/other active or unvalidated formats are documents, never same-origin pages.
        mime='application/octet-stream'
    record={'id':identifier,'name':name,'path':str(path),'mime':mime,'bytes':size,'sha256':digest.hexdigest(),'created':time.time()}
    with db() as conn:conn.execute('INSERT INTO files VALUES(:id,:name,:path,:mime,:bytes,:sha256,:created)',record)
    return web.json_response(public_file(record))

async def file_response(request):
    identifier=request.match_info['fid']
    with db() as conn:row=conn.execute('SELECT * FROM files WHERE id=?',(identifier,)).fetchone()
    if not row:return error('Файл не найден.',404)
    response=web.FileResponse(row['path']);response.content_type=row['mime']
    if row['mime'] not in {'image/png','image/jpeg','image/gif','image/webp','image/bmp','video/mp4','video/webm','video/quicktime'}:response.headers['Content-Disposition']="attachment; filename*=UTF-8''"+__import__('urllib.parse',fromlist=['quote']).quote(row['name'])
    return response

async def artifact_response(request):
    with db() as conn:row=conn.execute('SELECT * FROM artifacts WHERE id=?',(request.match_info['fid'],)).fetchone()
    if not row or artifact_workspace.hidden(row['path']) or not local_asset(row['path']):return error('Артефакт не найден.',404)
    response=web.FileResponse(row['path']);response.content_type=row['mime']
    if row['mime'] not in {'image/png','image/jpeg','image/gif','image/webp','image/bmp','video/mp4','video/webm','video/quicktime'}:response.headers['Content-Disposition']="attachment; filename*=UTF-8''"+__import__('urllib.parse',fromlist=['quote']).quote(row['name'])
    return response

async def projects(request):
    rows=[{'name':p.name,'path':str(p)} for p in portable.workspace_root().iterdir() if p.is_dir() and not p.name.startswith('.')]
    return web.json_response({'projects':sorted(rows,key=lambda x:x['name'].lower())})

async def models(request):return web.json_response({'coder':{'name':(library.model(portable.config().get('active')) or {}).get('name',portable.model_id()),'context':portable.context_size(),'local':True},'images':image_status()})

async def ws(request):
    if request.query.get('token')!=TOKEN:return error('Обновите приложение.',403)
    socket=web.WebSocketResponse(heartbeat=20,max_msg_size=1024*1024)
    await socket.prepare(request);bridge.sockets.add(socket)
    await socket.send_json(request.app['runtime'].get('metrics',{'type':'metrics','gateway_ready':bridge.ready.is_set()}))
    try:
        async for _ in socket:pass
    finally:bridge.sockets.discard(socket)
    return socket

async def index(request):
    response=web.FileResponse(ROOT/'dist/index.html')
    # FileResponse infers MIME only during prepare; middleware must see HTML now.
    response.content_type='text/html'
    return response
async def startup(app):
    await asyncio.to_thread(library.scan)
    system.start()
    portable.write_hermes(portable.context_size())
    if cloud.models():await asyncio.to_thread(cloud.sync_aliases)
    await bridge.start();app['monitor_task']=asyncio.create_task(monitor(app))
    await updates.start(app,bridge)
    await rewards.start()
    active=library.model(portable.config().get('active'))
    if active and library.ready(active):library.activate(active['id'])
async def cleanup(app):
    await rewards.stop()
    advisor.pool.shutdown(wait=False,cancel_futures=True)
    await preview.stop()
    await cloud.close()
    await updates.close()
    app['monitor_task'].cancel()
    with contextlib.suppress(asyncio.CancelledError):await app['monitor_task']
    await bridge.close()

def create_app():
    app=web.Application(middlewares=[security],client_max_size=55*1024**2)
    app['runtime']={'metrics':{}}
    register_library(app)
    register_video(app,bridge,register_artifact)
    app.router.add_get('/api/updates',lambda r:web.json_response(updates.status()))
    app.router.add_post('/api/updates/check',update_check)
    app.router.add_post('/api/updates/settings',update_settings)
    register_system(app)
    workspace.register(app)
    cloud.register(app)
    branches.register(app)
    rewards.register(app)
    preview.register(app)
    advisor.register(app)
    accounts.register(app)
    goals.register(app)
    artifact_workspace.register(app)
    app.router.add_get('/api/health',health);app.router.add_get('/api/bootstrap',bootstrap)
    app.router.add_get('/api/sessions',sessions);app.router.add_post('/api/sessions',new_session)
    app.router.add_get('/api/sessions/{sid}',session_detail);app.router.add_patch('/api/sessions/{sid}',chat_meta)
    app.router.add_post('/api/sessions/{sid}/messages',submit);app.router.add_post('/api/sessions/{sid}/stop',stop)
    app.router.add_post('/api/sessions/{sid}/respond',respond);app.router.add_post('/api/uploads',upload)
    app.router.add_get('/api/files/{fid}',file_response);app.router.add_get('/api/artifacts/{fid}',artifact_response)
    app.router.add_get('/api/projects',projects);app.router.add_get('/api/models',models);app.router.add_get('/api/ws',ws)
    app.router.add_static('/assets/',ROOT/'dist/assets');app.router.add_get('/freedom.svg',lambda r:web.FileResponse(ROOT/'public/freedom.svg'))
    app.router.add_get('/',index);app.on_startup.append(startup);app.on_cleanup.append(cleanup)
    return app

if __name__=='__main__':
    logging.basicConfig(filename=ROOT/'logs/server.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s',encoding='utf-8')
    # Disable request URLs in logs: websocket URLs carry a process-lifetime local CSRF token.
    web.run_app(create_app(),host='127.0.0.1',port=PORT,access_log=None,print=None)
