"""Bounded local recovery over the existing service owners. Never replays user work."""
import ast,asyncio,contextlib,hashlib,json,os,pathlib,shutil,sqlite3,time,urllib.request,uuid

ACTION_NAMES={'watchdog':'Восстановить наблюдение за панелью','gateway':'Восстановить соединение со службой агента','model':'Запустить отсутствующую службу модели','team-plugin':'Восстановить отсутствующие файлы инструментов команды'}


def plan(snapshot):
 """Only positive, verified evidence authorizes a repair; unknown state stays untouched."""
 if snapshot.get('stopping'):return []
 actions=[]
 if snapshot.get('ui_owned') is True and snapshot.get('watchdog') is False:actions.append('watchdog')
 if snapshot.get('gateway') is False and snapshot.get('gateway_recoverable') is True:actions.append('gateway')
 if snapshot.get('team_missing') is True and snapshot.get('team_source_valid') is True and snapshot.get('team_enabled') is True:actions.append('team-plugin')
 if (snapshot.get('model_applicable') is True and snapshot.get('model_ready') is False
     and snapshot.get('model_owner') is False and snapshot.get('model_listener') is False
     and snapshot.get('idle') is True and snapshot.get('model_files_ready') is True
     and snapshot.get('model_stopped') is False and not snapshot.get('busy_reason')):actions.append('model')
 return actions


def get_json(url,timeout=2):
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(url,timeout=timeout) as response:return json.load(response)


def pending_work(home):
 try:
  path=pathlib.Path(home)/'state.db'
  with contextlib.closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
   return conn.execute("SELECT COUNT(*) FROM session_admissions WHERE status IN ('queued','started','unknown')").fetchone()[0]
 except (OSError,sqlite3.Error):return None


class LocalRuntime:
 def __init__(self,root,portable,bridge,app,busy):self.root,self.portable,self.bridge,self.app,self.busy=pathlib.Path(root),portable,bridge,app,busy
 async def inspect(self,deep=False):
  p=self.portable
  try:busy_reason=self.busy(self.app)
  except Exception:busy_reason='Не удалось подтвердить отсутствие другой работы'
  s={'gateway':False,'gateway_recoverable':False,'idle':None,'busy_reason':busy_reason}
  if self.bridge.ready.is_set():
   try:
    rows=await asyncio.wait_for(self.bridge.rpc('session.list',scope='live',limit=200),3)
    s['gateway']=True;s['idle']=not any(r.get('running') or r.get('pending') for r in rows.get('sessions',[])) and not self.app.get('prompt_admissions') and not any(v.get('active') for v in self.bridge.live.values())
   except Exception:pass
  if not s['gateway']:
   try:
    from hermes_cli.gateway_runtime import discover_gateway_endpoint,attachable
    discovery=await asyncio.to_thread(discover_gateway_endpoint,p.HOME,timeout=1)
    s['gateway_recoverable']=attachable(discovery) or discovery.state=='absent'
   except Exception:pass
  from ui_lifecycle import current_ui,owned_process,SCRIPT,stop_requested
  record=current_ui(p.config()['ui_port']);s['ui_owned']=bool(record)
  s['stopping']=bool(record and stop_requested(record['created']))
  s['watchdog']=bool(owned_process(p.read(self.root/'.tmp/ui-supervisor.json',{}),SCRIPT))
  s['model_applicable']=not bool(p.config().get('external_url'))
  if s['model_applicable']:
   try:s['model_ready']=(await asyncio.to_thread(get_json,f"http://127.0.0.1:{int(p.config()['model_port'])}/health")).get('status')=='ok'
   except Exception:s['model_ready']=False
   s.update(model_owner=None,model_listener=None,model_files_ready=False,model_stopped=True)
   if p.PRIVATE:
    try:
     import managed_models,psutil
     s['model_owner']=bool(managed_models.owned_supervisor())
     s['model_listener']=any(c.status==psutil.CONN_LISTEN and c.laddr and c.laddr.port==int(p.config()['model_port']) for c in psutil.net_connections(kind='inet'))
     cfg=p.read(p.STACK/'server-settings.json',{});model=pathlib.Path(cfg.get('model') or '')
     s['model_files_ready']=bool(cfg.get('model') and model.is_file() and (p.STACK/'server-supervisor.py').is_file())
     s['model_stopped']=(p.STACK/'.tmp/stop-server').exists()
    except Exception:pass
   if not s.get('model_ready') and s.get('model_owner') is False:
    pending=await asyncio.to_thread(pending_work,p.HOME)
    s['idle']=s['idle'] is True and pending==0
    if pending is None:s['busy_reason']='Не удалось подтвердить состояние очереди. Запуск службы модели отложен.'
    elif pending:s['busy_reason']='Есть незавершённые или неопределённые задания. Автоматический запуск службы модели отложен.'
  import psutil
  s['disk_free']=shutil.disk_usage(self.root).free;s['ram_available']=psutil.virtual_memory().available
  source=pathlib.Path(__file__).resolve().parent/'agent_plugins/freedom-team';target=p.HOME/'plugins/freedom-team'
  s.update(team_missing=False,team_source_valid=False,team_enabled=False)
  try:
   from hermes_cli.config import read_user_config_raw
   plugins=read_user_config_raw(p.HOME/'config.yaml').get('plugins',{})
   s['team_enabled']='freedom-team' in (plugins.get('enabled') or []) and 'freedom-team' not in (plugins.get('disabled') or [])
   s['team_missing']=any(not (target/name).is_file() for name in ('__init__.py','plugin.yaml','runtime.json'))
   ast.parse((source/'__init__.py').read_text('utf8'));s['team_source_valid']=(source/'plugin.yaml').is_file()
  except Exception:pass
  checks=[{'id':'gateway','name':'Служба агента','state':'ok' if s['gateway'] else 'error','detail':'Связь подтверждена' if s['gateway'] else 'Нет подтверждённого ответа; проверим штатный запуск службы'},
   {'id':'watchdog','name':'Восстановление панели после сбоя','state':'ok' if s['watchdog'] else 'warn','detail':'Наблюдатель работает' if s['watchdog'] else 'Проверим и восстановим наблюдатель этой установки'},
   {'id':'model','name':'Локальная модель','state':'ok' if not s['model_applicable'] or s.get('model_ready') else 'warn','detail':'Используется внешнее API' if not s['model_applicable'] else 'Модель отвечает' if s.get('model_ready') else 'Модель не готова; учитываем загрузку, задачи и остановку владельцем'},
   {'id':'disk','name':'Место на диске','state':'ok' if s['disk_free']>=1024**3 else 'warn','detail':str(round(s['disk_free']/1024**3,1))+' ГБ свободно; файлы автоматически не удаляются'},
   {'id':'memory','name':'Оперативная память','state':'ok' if s['ram_available']>=512*1024**2 else 'warn','detail':str(round(s['ram_available']/1024**3,1))+' ГБ доступно; контекст и процессы не меняются'},
   {'id':'team','name':'Инструменты ИИ-агентов','state':'warn' if s['team_enabled'] and s['team_missing'] else 'ok','detail':'Обнаружены отсутствующие файлы' if s['team_enabled'] and s['team_missing'] else 'Файлы на месте или плагин выключен владельцем'}]
  for filename,label in [('data/settings.json','Настройки приложения'),('data/team-agents.json','Каталог помощников')]:
   try:
    path=self.root/filename
    if path.exists() and not isinstance(json.loads(path.read_text('utf8')),dict):raise ValueError()
    checks.append({'id':filename,'name':label,'state':'ok','detail':'Формат читается'})
   except Exception:checks.append({'id':filename,'name':label,'state':'error','detail':'Не удалось прочитать настройки. Нужна проверка и резервная копия; файл не перезаписан'})
  if deep:
   def database_check():
    path=self.root/'data/interface.sqlite'
    with contextlib.closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:return conn.execute('PRAGMA quick_check(1)').fetchone()[0]=='ok'
   try:ok=await asyncio.to_thread(database_check);detail='Проверка целостности пройдена' if ok else 'Проверка нашла проблему; автоматического удаления или сброса базы нет'
   except Exception:ok=False;detail='Проверка сейчас недоступна; база может быть занята'
   checks.append({'id':'database','name':'База интерфейса','state':'ok' if ok else 'warn','detail':detail})
  s['checks']=checks;return s
 async def execute(self,action,snapshot):
  # Recheck immediately before every mutation; a running task or owner stop may have arrived.
  current=await self.inspect()
  if action not in plan(current):return {'state':'skipped','message':'Состояние изменилось или восстановление сейчас не требуется'}
  if action=='watchdog':
   def ensure():
    from ui_lifecycle import current_ui,ensure_supervisor
    record=current_ui(self.portable.config()['ui_port'])
    if not record:raise ValueError('UI ownership changed')
    ensure_supervisor(record,self.portable.config()['ui_port'])
   await asyncio.to_thread(ensure)
  elif action=='gateway':
   def ensure():
    from hermes_cli.gateway_runtime import ensure_gateway_runtime,attachable,discover_gateway_endpoint
    result=discover_gateway_endpoint(self.portable.HOME,timeout=1)
    if not attachable(result):
     if result.state!='absent':return False
     result=ensure_gateway_runtime(self.portable.HOME,idle_exit=True,timeout=15)
    if not attachable(result):raise ValueError('Native owner is not attachable')
    return True
   if not await asyncio.to_thread(ensure):return {'state':'skipped','message':'Существующая служба требует отдельной проверки. Принудительной замены не было.'}
   if not self.bridge.task or self.bridge.task.done():await self.bridge.start()
  elif action=='model':
   def ensure():
    from platform_support import file_lock
    import managed_models
    with file_lock(self.portable.STACK/'.tmp/private-model-switch.lock'):
     if not managed_models.owned_supervisor() and not (self.portable.STACK/'.tmp/stop-server').exists() and pending_work(self.portable.HOME)==0:managed_models.start();return True
     return False
   if not await asyncio.to_thread(ensure):return {'state':'skipped','message':'Появилась работа или остановка владельцем. Служба модели не запускалась.'}
  elif action=='team-plugin':
   source=pathlib.Path(__file__).resolve().parent/'agent_plugins/freedom-team';target=self.portable.HOME/'plugins/freedom-team';target.mkdir(parents=True,exist_ok=True)
   for name in ('__init__.py','plugin.yaml'):
    if not (target/name).exists():shutil.copy2(source/name,target/name)
   if not (target/'runtime.json').exists():self.portable.write(target/'runtime.json',{'app_relative':os.path.relpath(self.root,target)})
   from gateway.control_socket import reload_gateway_plugins
   await asyncio.to_thread(reload_gateway_plugins,self.portable.HOME)
  return {'state':'attempted','message':'Восстановление запущено штатным механизмом; результат проверяется отдельно'}


class SelfRepair:
 def __init__(self,root,runtime,clock=time.time):
  self.root,self.runtime,self.clock=pathlib.Path(root),runtime,clock;self.path=self.root/'data/self-repair.json';self.job=None;self.loop_task=None;self.misses={};self.check_lock=asyncio.Lock()
  try:
   self.state=json.loads(self.path.read_text('utf8'))
   if not isinstance(self.state,dict):raise ValueError()
  except FileNotFoundError:self.state={}
  except (OSError,ValueError):
   self.state={'automatic':False}
   with contextlib.suppress(OSError):
    backup=self.root/'archive/self-repair-invalid';backup.mkdir(parents=True,exist_ok=True);shutil.copy2(self.path,backup/(str(time.time_ns())+'.json'))
  self.state.setdefault('automatic',True);self.state.setdefault('attempts',{});self.state.setdefault('history',[]);self.state.setdefault('phase','idle')
  if not isinstance(self.state['attempts'],dict):self.state['attempts']={}
  self.state['attempts']={key:[v for v in values if type(v) in (int,float)] for key,values in self.state['attempts'].items() if key in ACTION_NAMES and isinstance(values,list)}
  if not isinstance(self.state['history'],list):self.state['history']=[]
  if type(self.state['automatic']) is not bool:self.state['automatic']=False
  # A UI restart does not resume any admitted task or assume an interrupted repair succeeded.
  if self.state['phase']=='repairing':self.state['phase']='idle'
  self.snapshot=None
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.'+uuid.uuid4().hex+'.new');tmp.write_text(json.dumps(self.state,ensure_ascii=False,indent=2),'utf8');os.replace(tmp,self.path)
 def status(self):return {k:v for k,v in self.state.items() if k!='attempts'}
 def event(self,action,state,message):
  self.state['history']=(self.state['history']+[{'at':self.clock(),'action':ACTION_NAMES.get(action,action),'state':state,'message':message}])[-30:];self.save()
 async def diagnose(self,deep=False):
  async with self.check_lock:
   snapshot=await self.runtime.inspect(deep);self.snapshot=snapshot
   self.state.update(checked_at=self.clock(),checks=snapshot.get('checks',[]),available_actions=[ACTION_NAMES[a] for a in plan(snapshot)],busy_reason=snapshot.get('busy_reason'))
   self.save();return self.status()
 def allowed(self,action):
  times=[t for t in self.state['attempts'].get(action,[]) if self.clock()-t<600]
  return len(times)<3 and (not times or self.clock()-times[-1]>=90)
 async def run(self,actions):
  self.state['phase']='repairing';self.save()
  try:
   for action in actions:
    if not self.allowed(action):self.event(action,'cooldown','Достигнут предел повторов. Сохраняем состояние и ждём следующей проверки.');continue
    attempts=[t for t in self.state['attempts'].get(action,[]) if self.clock()-t<600];self.state['attempts'][action]=attempts+[self.clock()];self.save()
    try:
     result=await self.runtime.execute(action,self.snapshot or {});self.event(action,result['state'],result['message'])
    except asyncio.CancelledError:raise
    except Exception:self.event(action,'failed','Штатное восстановление не завершилось. Настройки и задания сохранены; требуется проверка причины.')
   await self.diagnose()
   verified={'watchdog':self.snapshot.get('watchdog') is True,'gateway':self.snapshot.get('gateway') is True,'model':self.snapshot.get('model_ready') is True,'team-plugin':self.snapshot.get('team_missing') is False and self.snapshot.get('team_enabled') is True}
   for action in actions:
    if verified.get(action):self.event(action,'recovered','Повторная проверка подтвердила, что компонент работает.')
  finally:self.state['phase']='idle';self.save()
 async def request(self):
  if self.job and not self.job.done():return self.status()
  await self.diagnose()
  if self.job and not self.job.done():return self.status()
  actions=plan(self.snapshot)
  if not actions:self.event('diagnosis','checked','Безопасных действий восстановления сейчас нет. Смотрите результаты проверок.');return self.status()
  self.job=asyncio.create_task(self.run(actions));self.state['phase']='repairing';self.save();return self.status()
 async def tick(self):
  await self.diagnose()
  if not self.state['automatic'] or self.job and not self.job.done():return
  actions=plan(self.snapshot);self.misses={a:self.misses.get(a,0)+1 for a in actions}
  if any(n>=3 and self.allowed(a) for a,n in self.misses.items()):
   chosen=[a for a,n in self.misses.items() if n>=3];self.job=asyncio.create_task(self.run(chosen))
 async def loop(self):
  await asyncio.sleep(10)
  while True:
   try:await self.tick()
   except asyncio.CancelledError:raise
   except Exception:pass
   await asyncio.sleep(30)
 async def start(self,app):self.loop_task=asyncio.create_task(self.loop())
 async def close(self,app):
  if self.loop_task:
   self.loop_task.cancel()
   with contextlib.suppress(asyncio.CancelledError):await self.loop_task
  # Do not cancel a half-finished native recovery. It does not own user work.
  if self.job and not self.job.done():await asyncio.shield(self.job)
 def register(self,app):
  from aiohttp import web
  async def read(request):return web.json_response(self.status())
  async def check(request):return web.json_response(await self.diagnose(deep=True))
  async def repair(request):return web.json_response(await self.request())
  async def settings(request):
   data=await request.json()
   if type(data.get('automatic')) is not bool:raise ValueError('Укажите состояние автовосстановления.')
   self.state['automatic']=data['automatic'];self.save();return web.json_response(self.status())
  app.router.add_get('/api/self-repair',read);app.router.add_post('/api/self-repair/diagnose',check);app.router.add_post('/api/self-repair/repair',repair);app.router.add_post('/api/self-repair/settings',settings)
  app.on_startup.append(self.start);app.on_cleanup.append(self.close)


def tool_action(root,action):
 """Called by the live Hermes plugin. No external URL or arbitrary repair command is accepted."""
 if action not in {'status','diagnose','repair'}:raise ValueError('Выберите status, diagnose или repair.')
 import bootstrap
 root=pathlib.Path(root).resolve()
 if root!=bootstrap.ROOT.resolve():raise ValueError('Другая установка приложения.')
 origin=f"http://127.0.0.1:{int(bootstrap.config()['ui_port'])}"
 try:
  health=get_json(origin+'/api/health')
 except (OSError,ValueError):
  if action!='repair':return {'unavailable':True,'message':'Панель не отвечает. Можно запросить repair для проверки её штатного запуска.'}
  from ui_lifecycle import current_ui,spawn_ui,ensure_supervisor,stop_requested,owned_process
  record=bootstrap.read(root/'.tmp/server-process.json',{})
  if stop_requested(record.get('created',0)):return {'state':'stopped','message':'Приложение остановлено владельцем; автоматический запуск отменён.'}
  if owned_process(record,'server.py') or current_ui(bootstrap.config()['ui_port']):return {'state':'waiting','message':'Процесс панели существует. Его принудительная остановка не выполнялась.'}
  import psutil
  if any(c.status==psutil.CONN_LISTEN and c.laddr and c.laddr.port==int(bootstrap.config()['ui_port']) for c in psutil.net_connections(kind='inet')):return {'state':'blocked','message':'Локальный порт занят другим процессом. Он не остановлен и не заменён.'}
  from hermes_cli.active_sessions import _FileLock
  # The panel may be down, so this small ledger is independent of its in-memory state.
  ledger=root/'data/self-repair-panel-attempts.json'
  with _FileLock(ledger.with_suffix('.lock')):
   try:saved=json.loads(ledger.read_text('utf8'))
   except FileNotFoundError:saved={}
   except (OSError,ValueError):return {'state':'blocked','message':'Не удалось проверить журнал попыток запуска; повтор автоматически не выполнялся.'}
   attempts=saved.get('attempts',[]) if isinstance(saved,dict) else None
   if not isinstance(attempts,list) or any(type(t) not in (int,float) for t in attempts):return {'state':'blocked','message':'Журнал попыток запуска требует проверки.'}
   now=time.time();attempts=[t for t in attempts if now-t<600]
   if len(attempts)>=3 or attempts and now-attempts[-1]<90:return {'state':'cooldown','message':'Повторный запуск панели ограничен. Проверьте причину сбоя в журнале запуска.'}
   bootstrap.write(ledger,{'attempts':attempts+[now]})
   record=spawn_ui();ensure_supervisor(record,bootstrap.config()['ui_port'])
  return {'state':'starting','message':'Панель запускается штатным механизмом; затем повторите status.'}
 expected=hashlib.sha256(str(root).encode()).hexdigest()[:16]
 if health.get('installation')!=expected:raise ValueError('На порту другая установка. Восстановление отменено.')
 if action=='status':return get_json(origin+'/api/self-repair',timeout=5)
 token=get_json(origin+'/api/bootstrap')['token'];request=urllib.request.Request(origin+'/api/self-repair/'+action,data=b'{}',headers={'Content-Type':'application/json','X-Freedom-Token':token})
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(request,timeout=20) as response:return json.load(response)
