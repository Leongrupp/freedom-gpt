"""Bound one local generation, not the goal or its number of steps."""
from urllib.parse import urlsplit

LIMIT = 8192


def request_budget(request,session_id='',base_url='',**kwargs):
    # Never change cloud billing/model settings or unrelated ordinary sessions.
    try:
        if urlsplit(base_url or '').hostname not in {'127.0.0.1','localhost','::1'} or not session_id:
            return None
        from hermes_cli.goals import load_goal
        goal=load_goal(session_id)
        if not goal or goal.status!='active' or '[Freedom arshi:v1]' not in goal.contract.boundaries:
            return None
        if not isinstance(request,dict) or 'messages' not in request:
            return None  # This private integration serves the local chat-completions route.
        result=dict(request)
        keys=[key for key in ('max_tokens','max_completion_tokens') if key in result] or ['max_tokens']
        for key in keys:
            value=result.get(key)
            result[key]=min(value,LIMIT) if type(value) is int and value>0 else LIMIT
        # A provider override must not silently restore an unlimited generation.
        extra=result.get('extra_body')
        if isinstance(extra,dict) and any(k in extra for k in keys):
            result['extra_body']={**extra}
            for key in keys:
                if key in extra:
                    value=extra[key]
                    result['extra_body'][key]=min(value,result[key]) if type(value) is int and value>0 else result[key]
        return {'request':result,'source':'freedom-arshi','reason':'Bound one local generation; native goal continuation remains enabled'}
    except (OSError,ValueError,AttributeError):
        return None
