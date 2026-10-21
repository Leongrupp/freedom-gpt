"""Exercise a running isolated installation. Uses a loopback OpenAI fixture only."""
import json,pathlib,sys,time,urllib.request,urllib.error,uuid

def check(base,target,token):
 target=pathlib.Path(target);checks={}
 def call(path,data=None):
  req=urllib.request.Request(base+'/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Freedom-Token':token})
  try:
   with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)
  except urllib.error.HTTPError as error:raise RuntimeError(path+': '+error.read(400).decode(errors='replace'))
 def wait(sid):
  for _ in range(120):
   state=call('sessions/'+sid)
   if not state.get('running') and not state.get('pending'):return state
   time.sleep(.5)
  raise RuntimeError('Test chat did not become idle')
 project=target/'workspaces/feature-qa';project.mkdir(parents=True,exist_ok=True)
 created=call('sessions',{'title':'Feature regression1.5','cwd':str(project),'access':'manual'});sid=created['id'];path='sessions/'+sid
 goal=call(path+'/goal');checks['goal_engine_current']=goal['engine']['ready'] is True
 fields={'objective':'Test local project checkpoint','verification':'One saved record','constraints':'No external writes'}
 saved=call(path+'/goal',{'action':'save','fields':fields,'draft_revision':(goal.get('draft') or {}).get('revision',0)});checks['goal_draft_saved']=call(path+'/goal')['draft']['fields']['objective']==fields['objective']
 checks['accounts_optional']=call('accounts')['optional'] is True
 checks['updates_manual_only']=call('updates')['manual_only'] is True
 call(path+'/messages',{'text':'QA_HOLD: Return one short acknowledgement, no tools.','input_id':'qa_'+uuid.uuid4().hex,'files':[],'mode':'code'})
 identifiers=[]
 for n in range(3):
  receipt=call(path+'/messages',{'text':'Queued test '+str(n),'input_id':'qa_'+uuid.uuid4().hex,'files':[],'mode':'code'});identifiers.append(receipt['admission_id'])
 snapshot=call(path);order=[p['admission_id'] for p in snapshot['pending'] if p.get('status')=='queued']
 checks['three_tasks_queued']=all(i in order for i in identifiers)
 edited=call(path+'/queue',{'action':'edit','admission_id':identifiers[-1],'text':'Edited queue task','expected_text':'Queued test 2','expected_order':order,'edit_id':'qa_edit_'+uuid.uuid4().hex})
 snapshot=call(path);queued=[p for p in snapshot['pending'] if p.get('status')=='queued'];checks['queue_text_edited']=any('Edited queue task' in p.get('text','') for p in queued)
 order=[p['admission_id'] for p in queued];chosen=order[-1]
 call(path+'/queue',{'action':'up','admission_id':chosen,'expected_order':order})
 changed=[p['admission_id'] for p in call(path)['pending'] if p.get('status')=='queued'];checks['queue_reordered']=changed!=order and set(changed)==set(order)
 for identifier in changed:call(path+'/queue',{'action':'cancel','admission_id':identifier})
 call(path+'/notes',{'text':'Continue with the original task. This is a local steering regression.','input_id':'qa_note_'+uuid.uuid4().hex})
 checks['steering_accepted']=True
 snapshot=wait(sid);checks['streamed_agent_answer']=any(m.get('role')=='assistant' and m.get('content') for m in snapshot['messages'])
 call(path+'/usage');checks['usage_available']=True
 branch=call(path+'/branch',{'request_id':'qa_branch_'+uuid.uuid4().hex,'title':'Feature QA branch'})
 child=call('sessions/'+branch['id']);checks['branch_history_and_parent']=bool(child['messages']) and child['branch']['parent_id']==sid
 checks['branch_empty_queue']=not child.get('pending') and not child.get('running')
 # Import the installed provider, then ask the actual HTTP memory panel to read it.
 import importlib.util,os
 os.environ['FREEDOM_ROOT']=str(target)
 spec=importlib.util.spec_from_file_location('installed_memory_qa',target/'stack/hermes-runtime/plugins/coding-continuity/project_store.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.ProjectStore(project).remember('Portable amber lighthouse project architecture','decision',sid,'isolated local QA')
 memory=call(path+'/memory?query=amber');checks['memory_panel_recalls_record']=bool(memory.get('items'))
 call('skills');checks['skills_list_available']=True
 checks['no_real_accounts']=not call('accounts')['github']['available'] and not call('accounts')['huggingface']['available']
 assert all(checks.values()),checks
 return checks
