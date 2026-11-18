"""A live plugin; no core patches, prompt rewrites or automatic task resubmission."""
import importlib.util,json,pathlib,threading,logging,sqlite3

spec=importlib.util.spec_from_file_location('_freedom_progress_policy_'+str(pathlib.Path(__file__).parent),pathlib.Path(__file__).with_name('policy.py'))
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
spec=importlib.util.spec_from_file_location('_freedom_background_'+str(pathlib.Path(__file__).parent),pathlib.Path(__file__).with_name('background.py'))
background=importlib.util.module_from_spec(spec);spec.loader.exec_module(background)
spec=importlib.util.spec_from_file_location('_freedom_web_scope_'+str(pathlib.Path(__file__).parent),pathlib.Path(__file__).with_name('web_scope.py'))
web_scope=importlib.util.module_from_spec(spec);spec.loader.exec_module(web_scope)
spec=importlib.util.spec_from_file_location('_freedom_arshi_'+str(pathlib.Path(__file__).parent),pathlib.Path(__file__).with_name('arshi.py'))
arshi=importlib.util.module_from_spec(spec);spec.loader.exec_module(arshi)
spec=importlib.util.spec_from_file_location('_freedom_reasoning_'+str(pathlib.Path(__file__).parent),pathlib.Path(__file__).with_name('reasoning.py'))
reasoning=importlib.util.module_from_spec(spec);spec.loader.exec_module(reasoning)
_ledgers={};_lock=threading.RLock()

def ledger():
 file=pathlib.Path(__file__).with_name('runtime.json');root=(file.parent/json.loads(file.read_text(encoding='utf-8'))['app_relative']).resolve()
 with _lock:
  if str(root) not in _ledgers:_ledgers[str(root)]=policy.Ledger(root/'data/progress-guard')
  return _ledgers[str(root)]

def middleware(tool_name,args,next_call,session_id='',turn_id='',session_cwd='',**kwargs):
 sid=session_id
 if not sid:
  from gateway.session_context import get_session_env
  sid=get_session_env('HERMES_SESSION_ID','')
 if not policy.SID.fullmatch(sid or ''):return next_call(args)
 # UI polling is a separate API; active process polling by the model remains legitimate.
 if tool_name in {'process','process_manage'} and args.get('action') in {'poll','log','list','status','wait'}:
  result=next_call(args);ledger().process_result(sid,args.get('session_id') or args.get('process_id'),result);return background.explain(result)
 if tool_name=='preview_browser' and args.get('action') in {'status','click','fill','type','press','scroll','viewport','close'}:return next_call(args)
 guard=ledger();turn=turn_id or sid;observed={**args,**({'_freedom_cwd':session_cwd} if session_cwd else {})}
 blocked=guard.before(sid,turn,tool_name,observed)
 if blocked:return json.dumps(blocked,ensure_ascii=False)
 before=policy.evidence(observed) if tool_name in {'patch','write_file'} else None
 result=background.explain(next_call(args)) if tool_name=='terminal' else next_call(args)
 if before is not None and not policy.failure(tool_name,policy.parsed_result(result))[0]:guard.note_file_change(sid,observed,before)
 notice=guard.after(sid,turn,tool_name,observed,result)
 if notice and isinstance(result,str):
  try:
   structured=json.loads(result)
   if isinstance(structured,dict):return json.dumps({**structured,'freedom_progress_notice':notice},ensure_ascii=False)
  except ValueError:pass
  return result+'\n\n[Freedom GPT: проверка продвижения]\n'+notice
 return result

def register(ctx):
 def execute(**kwargs):
  cwd=ctx.session_cwd();before={}
  try:
   from hermes_cli.task_evidence import capture_sources
   if kwargs.get('tool_name')=='terminal':
    before=capture_sources(kwargs.get('args',{}),cwd)
    before.update(reasoning.trial_sources(kwargs.get('session_id',''),cwd))
  except (OSError,ValueError,TypeError,sqlite3.Error):pass
  cached=None
  try:
   if kwargs.get('tool_name')=='project_memory':cached=reasoning.journal().memory_receipt(kwargs.get('session_id',''),kwargs.get('turn_id',''),cwd,kwargs['args'])
  except (OSError,ValueError,TypeError,sqlite3.Error):pass
  result=json.dumps(cached,ensure_ascii=False) if cached is not None else middleware(**kwargs,session_cwd=cwd)
  changed=False
  # Observing a successful action must never turn it into a failed tool call.
  try:
   from hermes_cli.task_evidence import observe
   changed=observe(kwargs.get('session_id',''),kwargs.get('turn_id',''),kwargs['tool_name'],kwargs['args'],result,cwd,before_sources=before)
   if changed and kwargs.get('tool_name') in {'terminal','process','process_manage'}:
    ledger().note_source_change(kwargs['session_id'])
  except (OSError,ValueError,TypeError,sqlite3.Error) as exc:
   logging.getLogger(__name__).warning('Execution checkpoint unavailable; tool result preserved: %s',type(exc).__name__)
  try:
   reasoning.trial_writes(kwargs.get('session_id',''),cwd,kwargs['tool_name'],kwargs['args'],before,changed)
   notice=reasoning.observe(kwargs.get('session_id',''),kwargs.get('turn_id',''),cwd,kwargs['tool_name'],kwargs['args'],result,policy,changed=bool(changed))
   result=reasoning.receipt(kwargs.get('session_id',''),kwargs.get('turn_id',''),cwd,kwargs['tool_name'],kwargs['args'],result,policy)
   if notice:
    if isinstance(result,dict):result={**result,'freedom_reasoning_notice':notice}
    elif isinstance(result,str):
     data=policy.parsed_result(result)
     if isinstance(data,dict):result=json.dumps({**data,'freedom_reasoning_notice':notice},ensure_ascii=False)
  except (OSError,ValueError,TypeError,sqlite3.Error) as exc:
   logging.getLogger(__name__).warning('Reasoning journal unavailable; tool result preserved: %s',type(exc).__name__)
  return result
 def recover(session_id='',**kwargs):
  if web_scope.active(session_id,kwargs.get('turn_id','')):return
  from hermes_cli.task_evidence import recovery_context,begin_turn
  cwd=ctx.session_cwd();context=recovery_context(session_id,cwd)
  begin_turn(session_id,kwargs.get('turn_id',''),cwd)
  try:
   notes=reasoning.begin(session_id,kwargs.get('turn_id',''),cwd,kwargs.get('user_message',''))
   context='\n\n'.join(part for part in (context,notes) if part)
  except (OSError,ValueError,TypeError,sqlite3.Error) as exc:
   logging.getLogger(__name__).warning('Reasoning recall unavailable: %s',type(exc).__name__)
  return {'context':context}
 def verify(session_id='',**kwargs):
  if web_scope.active(session_id,kwargs.get('turn_id','')):return
  from hermes_cli.task_evidence import enabled,quality_issue,turn_start
  if not enabled():return
  cwd=ctx.session_cwd()
  if not cwd:return
  issue=quality_issue(session_id,cwd,turn_start(session_id,cwd))
  if not issue:issue=reasoning.work_issue(session_id,cwd)
  if issue:return {'action':'continue','message':'[Freedom: проверка результата]\n'+issue}
  if not kwargs.get('footer_only'):
   issue=reasoning.review(session_id,cwd)
   if issue:return {'action':'continue','message':issue}
 def final_check(response_text='',session_id='',**kwargs):
  if verify(session_id=session_id,footer_only=True):
   return response_text+'\n\n⚠ Проверка результата ещё не завершена: нужны подтверждения тестами, браузером или итогом запущенного процесса. Результат пока не подтверждён.'
 ctx.register_middleware('llm_request',web_scope.request_scope)
 ctx.register_middleware('llm_request',arshi.request_budget)
 ctx.register_middleware('llm_request',reasoning.request_mode)
 ctx.register_middleware('tool_execution',web_scope.execute_scope)
 ctx.register_middleware('tool_execution',execute)
 ctx.register_hook('pre_llm_call',recover)
 ctx.register_hook('pre_completion',verify)
 ctx.register_hook('transform_llm_output',final_check)
