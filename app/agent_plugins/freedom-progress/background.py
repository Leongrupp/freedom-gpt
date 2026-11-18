"""Explain quiet delivery in a running tool result, without starting another model turn."""
import json

WAIT_NOTE = (
    'Background completion is saved as a hidden context note; it does not start another answer. '
    'This command is still running, so launch success is not task completion. '
    'If its result is needed for the current task, keep working in this turn and use '
    'process(action="wait", session_id=..., timeout=60), or process(action="log", ...) '
    'to collect the real result. Do not rerun the command, spawn sleep/cat timer jobs, '
    'or return a final answer that claims unfinished work is done.'
)


def explain(result):
    if not isinstance(result, str):
        return result
    try:
        data = json.loads(result)
    except ValueError:
        return result
    if not isinstance(data, dict) or not str(data.get('session_id', '')).startswith('proc_'):
        return result
    running = data.get('status') == 'running' or data.get('exited') is False
    running = running or data.get('output') == 'Background process started'
    if not running or data.get('completed_inline'):
        return result
    from hermes_cli.config import load_config_readonly
    if (load_config_readonly().get('display') or {}).get('local_process_results') != 'notes':
        return result
    data['completion_delivery'] = 'hidden_context_note'
    data['continuation'] = WAIT_NOTE
    # The stock silent-background hint proposes a relaunch with notify=true.
    if isinstance(data.get('hint'), str) and 'notify' in data['hint']:
        data.pop('hint')
    return json.dumps(data, ensure_ascii=False)
