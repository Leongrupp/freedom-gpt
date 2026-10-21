"""Loop, background completion and active-tool steering regressions, offline only."""
import ast,importlib.util,json,os,pathlib,sys,threading,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(os.environ['FREEDOM_QA_ROOT']).resolve();sys.path[:0]=[str(ROOT/'runtime/hermes'),str(ROOT/'runtime/freedom'),str(ROOT)]
import bootstrap
from agent.tool_guardrails import ToolCallGuardrailController,ToolCallGuardrailConfig,classify_tool_failure,browser_execution_failed,_real_progress
from agent.display import _detect_tool_failure

class Loops(unittest.TestCase):
 def guard(self):return ToolCallGuardrailController(ToolCallGuardrailConfig(hard_stop_enabled=True,exact_failure_block_after=2,same_tool_failure_halt_after=4))
 def test_harness_traceback_after_large_stdout(self):
  result=json.dumps({'stdout':'x'*3000,'stderr':'Traceback (most recent call last):\nConnectionAbortedError: failure'})
  self.assertTrue(classify_tool_failure('browser_exec',result)[0]);self.assertTrue(_detect_tool_failure('browser_exec',result)[0])
 def test_successful_harness_not_failure(self):
  self.assertFalse(browser_execution_failed({'stdout':'fine','stderr':'','exit_code':0}));self.assertFalse(browser_execution_failed(None))
 def test_probe_does_not_clear_failed_cdp(self):
  g=self.guard();args={'code':'same broken CDP call'}
  for _ in range(2):
   g.after_call('browser_exec',args,json.dumps({'stderr':'ConnectionAbortedError: failure'}),failed=False)
   g.after_call('terminal',{'command':'sleep 10 && ps aux | grep -i browser | head -3'},json.dumps({'exit_code':0,'output':'123 browser'}),failed=False)
  self.assertFalse(g.before_call('browser_exec',args).allows_execution)
 def test_real_file_repair_allows_retry(self):
  g=self.guard();args={'code':'call'}
  for _ in range(2):g.after_call('browser_exec',args,'{"error":"failed"}',failed=True)
  g.after_call('patch',{'path':'test.py'},'{"success":true}',failed=False)
  self.assertTrue(g.before_call('browser_exec',args).allows_execution)
 def test_background_handle_is_not_progress(self):
  self.assertFalse(_real_progress('terminal',{'command':'start server'},'{"session_id":"proc_1","status":"running","exit_code":0}'))
 def test_mutating_terminal_is_progress(self):
  self.assertTrue(_real_progress('terminal',{'command':'python fix.py'},'{"exit_code":0}'))
  self.assertTrue(_real_progress('terminal',{'command':'echo change > project.txt'},'{"exit_code":0}'))
 def test_process_poll_is_not_progress(self):
  self.assertFalse(_real_progress('process',{'action':'poll'},'{"status":"running"}'))
 def test_changing_browser_code_still_halts(self):
  g=self.guard();decision=None
  for n in range(4):
   decision=g.after_call('browser_exec',{'code':'attempt'+str(n)},'{"stderr":"RuntimeError: nope"}',failed=False)
   g.after_call('terminal',{'command':'ps aux'},'{"exit_code":0}',failed=False)
  self.assertTrue(decision.should_halt)
 def test_ticketed_steer_wakes_active_tool(self):
  from gateway import session_queued_controls as controls
  calls=[]
  agent=types.SimpleNamespace(_executing_tools=True,_model_request_active=threading.Event(),withdraw_steer=lambda ticket:False,steer=lambda text,**kw:calls.append(('steer',text,kw)) or True,redirect=lambda text:calls.append(('redirect',text)) or True)
  authority=types.SimpleNamespace(steer_transfers={'sid':(7,{'note':False})})
  with patch.object(controls,'_receiving_agent',return_value=agent):
   self.assertTrue(controls._deliver(authority,'sid',7,agent,'note','Real user correction'))
   self.assertTrue(controls._deliver(authority,'sid',7,agent,'note','Real user correction'))
  self.assertEqual(len([c for c in calls if c[0]=='steer']),1);self.assertEqual(len([c for c in calls if c[0]=='redirect']),1)
  self.assertEqual(calls[0][2]['ticket'],'note')
 def test_model_steer_follows_current_request_not_historical_tool(self):
  from agent.turn_iteration_prep import _inject_steer_after_newest_tool_result
  history=[{'role':'assistant','content':'old tool','tool_calls':[]},{'role':'tool','content':'old result'},{'role':'assistant','content':'old answer'},{'role':'user','content':'current request'}]
  original=json.loads(json.dumps(history));_inject_steer_after_newest_tool_result(object(),history,'Newest correction')
  self.assertEqual(history[:len(original)],original);self.assertEqual(history[-1]['role'],'user');self.assertIn('Newest correction',history[-1]['content'])
 def test_model_steer_without_any_tool_is_delivered(self):
  from agent.turn_iteration_prep import _inject_steer_after_newest_tool_result
  history=[{'role':'user','content':'current question'}];_inject_steer_after_newest_tool_result(object(),history,'Text-only correction')
  self.assertEqual(len(history),3);self.assertIn('Text-only correction',history[-1]['content'])
 def test_steer_after_current_tool_needs_no_placeholder(self):
  from agent.turn_iteration_prep import _inject_steer_after_newest_tool_result
  history=[{'role':'tool','content':'current result'}];_inject_steer_after_newest_tool_result(object(),history,'Correction')
  self.assertEqual(len(history),2);self.assertIn('Correction',history[-1]['content'])
 def test_fast_background_failure_is_returned_inline(self):
  from tools import terminal_tool_background as background
  import tools.terminal_tool as terminal
  from tools import process_registry as registry_module
  event=threading.Event();event.set()
  session=types.SimpleNamespace(id='proc_fixture',pid=1,process=object(),_completion_event=event,exited=True,exit_code=127)
  registry=types.SimpleNamespace(wait=lambda sid,timeout:{'exit_code':127,'output':'Executable missing'})
  with patch.object(background,'_spawn',return_value=session),patch.object(terminal,'_resolve_command_cwd',return_value=str(ROOT)),patch.object(registry_module,'process_registry',registry):
   result=json.loads(background.spawn_background_process(command='bad executable',env=object(),env_type='local',effective_task_id='qa',task_id='qa',session_key='qa',workdir=str(ROOT),cwd=str(ROOT),effective_pty=False,notify_on_complete=True,watch_patterns=None,approval_note=None,pty_disabled_reason=None))
  self.assertEqual(result['exit_code'],127);self.assertTrue(result['completed_inline']);self.assertFalse(result['notify_on_complete'])

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Loops));out=ROOT/'output/loop-investigation-20261021';out.mkdir(parents=True,exist_ok=True)
 (out/'regressions.json').write_text(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful()},indent=2));sys.exit(not result.wasSuccessful())
