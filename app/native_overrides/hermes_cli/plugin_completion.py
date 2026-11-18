"""Shared continue-directive parser for opt-in turn completion hooks."""


def continue_message(hook_name,**payload):
    from hermes_cli.plugins import invoke_hook
    for result in invoke_hook(hook_name,**payload):
        if not isinstance(result,dict):continue
        action=str(result.get('action') or result.get('decision') or '').strip().lower()
        message=result.get('message') or result.get('reason')
        if action in {'continue','block'} and isinstance(message,str) and message.strip():
            return message.strip()
    return None
