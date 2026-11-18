"""Resume opted-in local goals from the gateway's existing wakeup watcher.

Admission and clearing the timed barrier share one native FIFO transaction.
No command replay and no independent scheduler. A changed/paused goal wins.
"""
import hashlib
import json
import time
import logging
from hermes_state_runtime import RuntimeStoreError


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def consume_wait(sid,target,expected,after):
    def guard(conn):
        row=conn.execute('SELECT value FROM state_meta WHERE key=?',('goal:'+target,)).fetchone()
        if not row or row[0]!=expected:raise RuntimeStoreError('stale_generation')
        if conn.execute("SELECT 1 FROM session_admissions WHERE target_session_id=? AND status IN ('queued','started','unknown')",(sid,)).fetchone():
            raise RuntimeStoreError('admission_conflict')
        conn.execute('UPDATE state_meta SET value=? WHERE key=? AND value=?',(after,'goal:'+target,expected))
    return guard


def stale_goal_wake(authority,row):
    descriptor=row.get('payload',{}).get('local_automation_v1') or {}
    try:identity=json.loads(descriptor.get('identity','null'))
    except (ValueError,TypeError):return False
    if not isinstance(identity,list) or identity[:1]!=['goal-timed-wake']:return False
    if len(identity)!=4:return True
    raw=authority.db.get_meta('goal:'+identity[2])
    return not raw or digest(raw)!=identity[3]


def candidate(authority,sid):
    from hermes_cli.goals import GoalState
    from hermes_cli.goal_autonomy import continued_gate_repair
    from gateway.session_contract import SessionRef
    target=authority.physical_target(SessionRef(authority.profile_id,sid))
    raw=authority.db.get_meta('goal:'+target)
    if not raw:return None
    state=GoalState.from_json(raw)
    if state.status!='active' or not state.waiting_until or state.waiting_until>time.time() or not continued_gate_repair(state):return None
    # Timed cooldown only; process/session barriers keep their own owner semantics.
    if state.waiting_on_pid is not None or state.waiting_on_session is not None:return None
    from hermes_state_runtime import list_session_admissions
    if list_session_admissions(authority.db,session_id=sid,pending_only=True):return None
    state.clear_wait()
    from hermes_cli.goals import GoalManager
    manager=GoalManager(target);manager._state=state
    prompt=manager.next_continuation_prompt()
    if not prompt:return None
    prompt+='\n\nОжидание завершилось. Сначала проверь сохранённый результат и доступность ресурсов. Не повторяй действия с неизвестным исходом; продолжи незавершённые требования.'
    return target,raw,state.to_json(),prompt


async def wake_due_local_goals(runner):
    from agent.estop import check_paused
    from gateway.session_authorities import active_authority
    from gateway.session_viewer_automation import viewer_driven
    from gateway.config import Platform
    from gateway.platforms.event import MessageEvent,MessageType
    from gateway.session_automation import admit_automation
    from hermes_cli.config import load_config
    if not (load_config().get('goals') or {}).get('continue_failed_gates'):return
    authority=active_authority(runner)
    if authority is None or check_paused('goal',logging.getLogger('gateway.run')):return
    for sid,live in list(authority.sessions.items()):
        if live.source.platform!=Platform.LOCAL or viewer_driven(authority,sid):continue
        if live.route in runner._running_agents:continue
        adapter=runner._delivery_adapter_for(live.source)
        if adapter is None:continue
        found=await runner._run_in_executor_with_context(lambda:candidate(authority,sid))
        if not found:continue
        target,raw,after,prompt=found
        identity=json.dumps(['goal-timed-wake',live.route,target,digest(after)],separators=(',',':'))
        event=MessageEvent(text=prompt,message_type=MessageType.TEXT,source=live.source,internal=True,
                           message_id=identity,metadata={'gateway_session_key':live.route,'gateway_session_id':target})
        try:
            await admit_automation(authority,adapter,event,identity,write_guard=consume_wait(sid,target,raw,after))
        except RuntimeStoreError:
            continue  # Owner input/pause or another admission won; leave it alone.
        runner._publish_local_control(live.source)
