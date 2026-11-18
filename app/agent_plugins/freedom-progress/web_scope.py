"""Web-only tools for one admitted research turn; never change session defaults."""
import json
import re
import threading

MARKER = '[Freedom: режим веб-исследования]'
PERSONAL = '[Freedom: обычный Chrome]'
ALLOWED = frozenset({'web_search', 'web_extract', 'preview_browser'})
_turns = {}
_evidence = {}
_admissions = {}
_personal = {}
_lock = threading.RLock()

PERSONAL_APPS={'chrome-personal':'Chrome','yandex-personal':'Yandex','edge-personal':'MSEdge','tor-personal':'Tor Browser'}
def personal(session_id,turn_id):
    from gateway.session_cli_turn import _cli_turn
    bound=_cli_turn.get()
    if bound:
        text=str(bound[1].get('api_text',''))
        matches=re.findall(r'\[Freedom: обычный браузер\] ([a-z-]+)',text)
        match=matches[-1] if matches else None
        if match:return match if match in PERSONAL_APPS else None
        return 'chrome-personal' if PERSONAL in text else None
    return _personal.get((session_id,turn_id))


def state(session_id, turn_id):
    from gateway.session_cli_turn import _cli_turn
    bound = _cli_turn.get()
    with _lock:
        if bound and turn_id:_admissions[(session_id,turn_id)]=str(bound[0])
        key = (session_id, str(bound[0]) if bound else _admissions.get((session_id,turn_id),turn_id))
    if not key[1]:return None
    with _lock:
        if key not in _evidence:
            if len(_evidence)>2048:
                _evidence.clear();_admissions.clear()
            _evidence[key]={'urls':set(), 'stale':0, 'readable':False}
            if bound:
                text=str(bound[1].get('api_text',''))
                offset=text.rfind('\n{"checked_at":')
                if offset>=0:
                    try:
                        seed,_=json.JSONDecoder().raw_decode(text[offset+1:])
                        _evidence[key]['urls'].update(row['url'] for row in seed.get('results',[]) if row.get('url'))
                        _evidence[key]['readable']=bool(seed.get('first_page',{}).get('content'))
                    except (ValueError,TypeError,KeyError):pass
        return _evidence[key]

def observe(evidence, tool_name, args, result):
    if evidence is None:return
    if isinstance(result,str):
        if result.lstrip().startswith('<untrusted_tool_result'):
            start=result.find('\n{');end=result.rfind('}')
            if start>=0 and end>start:result=result[start+1:end+1]
        try:result=json.loads(result)
        except ValueError:return
    urls=set();readable=False
    def visit(value):
        nonlocal readable
        if isinstance(value,dict):
            url=value.get('url')
            if isinstance(url,str) and url.startswith(('http://','https://')):
                urls.add(url)
                if value.get('content') and not value.get('error') and not value.get('challenge'):readable=True
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(result)
    is_search=tool_name=='web_search' or tool_name=='preview_browser' and args.get('action')=='search'
    with _lock:
        new=urls-evidence['urls'];evidence['urls'].update(urls)
        evidence['readable']|=readable
        if is_search:evidence['stale']=0 if new else evidence['stale']+1

def active(session_id='', turn_id=''):
    from gateway.session_cli_turn import _cli_turn
    bound = _cli_turn.get()
    if bound is not None:
        return MARKER in str(bound[1].get('api_text', ''))
    with _lock:
        return bool(turn_id and _turns.get((session_id, turn_id), False))

def request_scope(request, session_id='', turn_id='', **kwargs):
    enabled = active(session_id, turn_id)
    if turn_id:
        with _lock:
            if len(_turns) > 2048:
                _turns.clear()
            _turns[(session_id, turn_id)] = enabled
    if not enabled:
        return
    if personal(session_id,turn_id):
        with _lock:
            if len(_personal)>2048:_personal.clear()
            _personal[(session_id,turn_id)]=personal(session_id,turn_id)
        # Use the existing native dispatcher, not a name absent from agent.valid_tool_names.
        from tools.computer_use.tool import get_computer_use_schema
        native=get_computer_use_schema();native=native.get('function',native)
        arguments={'type':'object','properties':{'action':{'type':'string','enum':['desktop']},'desktop':native['parameters']},'required':['action','desktop']}
        schema={'type':'function','function':{'name':'tool_call','description':'Read and operate only the owner-selected ordinary browser. Capture before every interaction. CAPTCHA/login require manual handoff.',
            'parameters':{'type':'object','properties':{'calls':{'type':'array','minItems':1,'maxItems':1,'items':{'type':'object','properties':{'name':{'type':'string','enum':['preview_browser']},'arguments':arguments},'required':['name','arguments']}}},'required':['calls']}}}
        return {'request':{**request,'tools':[schema]},'source':'freedom-web-scope','reason':'Selected ordinary browser via registered preview dispatcher'}
    evidence=state(session_id,turn_id)
    if evidence and evidence['readable'] and evidence['stale']>=3:
        final={k:v for k,v in request.items() if k not in {'tools','tool_choice','parallel_tool_calls'}}
        final['messages']=[*request.get('messages',[]),{'role':'user','content':
            '[Freedom: завершение повторного поиска] Три последовательных поиска не дали новых ссылок; '
            'текст источника уже прочитан. Дай итоговый ответ по проверенным страницам со ссылками. '
            'Неизвестные причины и неподтверждённые детали прямо назови неизвестными. '
            'Не утверждай, что прочитал страницы с ошибкой или капчей.'}]
        return {'request':final,'source':'freedom-web-scope','reason':'Repeated search adds no sources; answer from observed evidence'}
    # Copy the payload and schemas: the session's tools remain intact for its next turn.
    from tools.web_tools import WEB_SEARCH_SCHEMA, WEB_EXTRACT_SCHEMA
    tools = [t for t in request.get('tools', [])
             if (t.get('function', {}).get('name') or t.get('name')) in ALLOWED]
    names = {t.get('function', {}).get('name') or t.get('name') for t in tools}
    for schema in (WEB_SEARCH_SCHEMA, WEB_EXTRACT_SCHEMA):
        function = schema.get('function', schema)
        if function['name'] not in names:
            tools.append(schema if 'function' in schema else {'type':'function', 'function':schema})
    return {'request': {**request, 'tools': tools}, 'source':'freedom-web-scope',
            'reason':'Research admission exposes web tools only'}

def execute_scope(tool_name, args, next_call, session_id='', turn_id='', **kwargs):
    if active(session_id,turn_id) and personal(session_id,turn_id):
        if tool_name!='preview_browser' or args.get('action')!='desktop' or not isinstance(args.get('desktop'),dict):
            return json.dumps({'error':'personal_browser_scope','message':'Используйте tool_call → preview_browser с action=desktop в выбранном браузере.'},ensure_ascii=False)
        inner=args['desktop'];action=inner.get('action');evidence=state(session_id,turn_id)
        if action not in {'capture','wait'} and not (evidence or {}).get('browser_captured'):
            return json.dumps({'error':'capture_browser_first','message':'Сначала обновите capture выбранного браузера.'},ensure_ascii=False)
        if action not in {'capture','wait','click','type','key','scroll','move','drag'}:
            return json.dumps({'error':'browser_action_not_allowed'},ensure_ascii=False)
        if action=='key':
            keys=str(inner.get('keys','')).lower().replace('control','ctrl').replace('command','cmd').replace(' ','')
            if keys not in {'ctrl+l','ctrl+t','ctrl+a','ctrl+c','ctrl+f','ctrl+w','ctrl+tab','ctrl+shift+tab','alt+left','alt+right','enter','return','escape','esc','tab','shift+tab','backspace','delete','up','down','left','right','home','end','pageup','pagedown'}:
                return json.dumps({'error':'browser_key_not_allowed','message':'Используйте навигационные клавиши браузера.'},ensure_ascii=False)
        new_tab=action=='key' and keys=='ctrl+t'
        if action not in {'capture','wait'} and not new_tab and not (evidence or {}).get('owned_tab'):
            return json.dumps({'error':'open_own_tab_first','message':'Создайте свою вкладку: key keys=ctrl+t, затем capture.'},ensure_ascii=False)
        safe={**inner,'app':PERSONAL_APPS[personal(session_id,turn_id)]}
        if action not in {'capture','wait'}:safe.update(delivery_mode='foreground',bring_to_front=True,capture_after=True)
        for name in ('pid','window_id','display'):safe.pop(name,None)
        result=next_call({'action':'desktop','desktop':safe})
        if evidence is not None:
            try:data=json.loads(result) if isinstance(result,str) else result
            except (TypeError,ValueError):data={}
            followed=isinstance(data,dict) and bool(data.get('_multimodal')) and (data.get('action_result') or {}).get('ok') is True
            if isinstance(data,dict) and data.get('_multimodal'):
                try:data=json.JSONDecoder().raw_decode(data.get('text_summary','').lstrip())[0]
                except (TypeError,ValueError):data={}
            if new_tab and isinstance(data,dict) and data.get('ok') is True:evidence['owned_tab']=True
            if action=='key' and keys=='ctrl+w':evidence['owned_tab']=False
            fresh=bool(data) and not data.get('error') and data.get('ok') is not False
            evidence['browser_captured']=fresh and (action=='capture' or followed or ('width' in data and 'elements' in data))
        return result
    if active(session_id, turn_id) and tool_name not in ALLOWED:
        return json.dumps({'error':'web_research_scope', 'message':
            'Сейчас выполняется веб-поиск. Используйте web_search, web_extract или preview_browser. '
            'Не ищите локальные файлы и не запускайте команды. Если текст источника уже получен, '
            'ответьте пользователю со ссылками; неподтверждённые подробности обозначьте явно.'}, ensure_ascii=False)
    result=next_call(args)
    if active(session_id,turn_id):observe(state(session_id,turn_id),tool_name,args,result)
    return result
