"""Specialist instructions over the existing native delegate_task."""
import importlib.util,json,pathlib

def register(ctx):
 folder=pathlib.Path(__file__).parent;root=(folder/json.loads((folder/'runtime.json').read_text('utf8'))['app_relative']).resolve()
 spec=importlib.util.spec_from_file_location('_freedom_team_'+str(root),root/'team_agents.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 store=module.TeamStore(root)
 chat_spec=importlib.util.spec_from_file_location('_freedom_team_chats_'+str(root),root/'team_chats.py');chat_module=importlib.util.module_from_spec(chat_spec);chat_spec.loader.exec_module(chat_module)
 chats=chat_module.TeamChats(root)
 delegated_sessions=set()
 def context(**kwargs):
  if kwargs.get('parent_session_id') or str(kwargs.get('user_message','')).startswith('[specialist:'):
   delegated_sessions.add(kwargs.get('session_id'));return
  binding=chats.binding(kwargs.get('session_id'))
  if binding:
   try:
    note=store.role_prompt(binding['specialist_id'])+'\nЭто твой личный чат с владельцем. Ты помощник основного агента, а не координатор всей команды. Сохраняй контекст этой беседы. Основной чат: '+binding['parent_id']+'. Когда владелец просит передать информацию главному, вызови team_specialist(action=report,report="краткий проверенный отчёт"). Отчёт будет передан в очередь основного чата; не утверждай, что основной уже выполнил его. Без такого поручения обсуждай и работай здесь. Не запускай других подагентов.'
   except ValueError as exc:note=str(exc)+' Не выполняй новых действий, пока владелец не включит тебя.'
   return {'context':note}
  from gateway.session_cli_turn import _cli_turn
  bound=_cli_turn.get()
  if bound and '[Freedom: режим веб-исследования]' in str(bound[1].get('api_text','')):return
  if str(kwargs.get('user_message','')).startswith('[specialist:'):return
  return {'context':store.guidance()}
 def middleware(**kwargs):
  binding=chats.binding(kwargs.get('session_id'))
  if binding:
   try:
    store.role_prompt(binding['specialist_id'])
    if kwargs.get('tool_name')=='delegate_task' and kwargs.get('args',{}).get('action','spawn')=='spawn':raise ValueError('Ты помощник главного агента. Передай ему предложение через team_specialist action=report; не создавай подагентов.')
   except ValueError as exc:return json.dumps({'error':str(exc)},ensure_ascii=False)
  from gateway.session_cli_turn import _cli_turn
  bound=_cli_turn.get();text=str(bound[1].get('api_text','')) if bound else ''
  return module.delegate_scope(store,owner_text=text.split('\n\n[Настройки владельца:',1)[0],**kwargs)
 def handle(args,**kwargs):
  try:
   if args.get('action')=='create':
    sid=kwargs.get('session_id')
    if not sid or sid in delegated_sessions or chats.binding(sid):raise ValueError('Создание команды доступно в основном чате. Передай предложение главному агенту.')
    from gateway.session_cli_turn import _cli_turn
    bound=_cli_turn.get();owner_text=str(bound[1].get('api_text','')) if bound else ''
    if not module.creation_requested(owner_text):raise ValueError('Нужен прямой запрос владельца: «Создай агента-помощника…» и описание роли.')
    return json.dumps(store.create_profile(args.get('profile'),str(sid)+'\0'+str(bound[0])),ensure_ascii=False)
   if args.get('action')=='report':
    binding=chats.binding(kwargs.get('session_id'))
    if not binding:raise ValueError('Отчёты доступны из личного чата специалиста. Для обычного подагента верни результат штатным способом.')
    store.role_prompt(binding['specialist_id'])
    row=chats.report(binding['sid'],args.get('report'),str(kwargs.get('turn_id') or kwargs.get('task_id') or '')+'-tool')
    return json.dumps({'id':row['id'],'state':row['state'],'parent_id':row['parent_id'],'message':'Отчёт сохранён для передачи основному агенту. Состояние delivered означает принятие в его очередь, а не выполнение.'},ensure_ascii=False)
   if args.get('action')=='prepare':
    prepared=store.prepare(args.get('specialist'),args.get('goal'),args.get('context',''))
    prepared['context']=args.get('context','')
    return json.dumps({'delegate_task':{'tasks':[prepared]},'next':'Invoke native delegate_task. No child has started yet; current role instructions will be added on launch.'},ensure_ascii=False)
   return json.dumps(store.catalog(args.get('query',''),args.get('department','')),ensure_ascii=False)
  except (ValueError,TypeError) as e:return json.dumps({'error':str(e)},ensure_ascii=False)
 profile={'type':'object','description':'For create: write a complete role profile from the owner request. Permissions and models are inherited; do not add credentials.','properties':{'name':{'type':'string'},'description':{'type':'string'},'instructions':{'type':'string','description':'40–5000 characters: purpose, workflow, checks, deliverable to main agent.'},'department':{'type':'string','description':'Existing department key from catalog, or other.'},'training':{'type':'string'},'skills':{'type':'array','items':{'type':'string'}}},'required':['name','description','instructions','department'],'additionalProperties':False}
 schema={'name':'team_specialist','description':'Find team specialists, CREATE and persist an owner-requested helper with instructions, prepare native delegation, or report to the main agent. create saves a profile; it does not launch work or change access.','parameters':{'type':'object','properties':{'action':{'type':'string','enum':['catalog','create','prepare','report']},'profile':profile,'specialist':{'type':'string'},'goal':{'type':'string'},'context':{'type':'string'},'report':{'type':'string'},'department':{'type':'string','description':'Department key from the catalog or its Russian name.'},'query':{'type':'string','description':'Short profession, task or skill phrase for catalog search.'}},'required':['action']}}
 ctx.register_tool(name='team_specialist',toolset='delegation',schema=schema,handler=handle,description='Freedom specialist team',emoji='👥')
 repair_spec=importlib.util.spec_from_file_location('_freedom_self_repair_'+str(root),root/'self_repair.py');repair_module=importlib.util.module_from_spec(repair_spec);repair_spec.loader.exec_module(repair_module)
 def health(args,**kwargs):
  try:return json.dumps(repair_module.tool_action(root,args.get('action','diagnose')),ensure_ascii=False)
  except Exception:return json.dumps({'error':'Диагностика сейчас недоступна. Сохраните контекст; не повторяйте неопределённые действия. Проверьте запуск приложения штатным ярлыком.'},ensure_ascii=False)
 ctx.register_tool(name='freedom_health',toolset='terminal',schema={'name':'freedom_health','description':'Diagnose Freedom itself or request bounded safe recovery of missing local service owners. Does not kill chats, change models/context/keys, delete data or replay tasks. repair returns a job state; use status later and verify checks before claiming success.','parameters':{'type':'object','properties':{'action':{'type':'string','enum':['status','diagnose','repair']}},'required':['action']}},handler=health,description='Freedom self diagnostics and recovery',emoji='🛠')
 ctx.register_hook('pre_llm_call',context);ctx.register_middleware('tool_execution',middleware)
