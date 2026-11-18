"""Shared browser UI and keyless search/extraction via the public provider API."""
import asyncio,json,pathlib,re,time,urllib.request
from urllib.parse import urlsplit
from agent.web_search_provider import WebSearchProvider

def binding():
    file=pathlib.Path(__file__).with_name('runtime.json')
    app=(file.parent/json.loads(file.read_text(encoding='utf-8'))['app_relative']).resolve()
    return app,json.loads((app/'data/preview-control.json').read_text(encoding='utf-8'))

def session_id(explicit=None):
    if not explicit:
        from gateway.session_context import get_session_env
        explicit=get_session_env('HERMES_SESSION_ID','')
    return explicit if isinstance(explicit,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,140}',explicit) else 'workspace'

def send_action(args,sid=None):
    _,route=binding()
    request=urllib.request.Request(route['url']+'/'+session_id(sid),data=json.dumps(args).encode(),headers={'Authorization':'Bearer '+route['key'],'Content-Type':'application/json'},method='POST')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request,timeout=50) as response:return json.load(response)

class FreedomBrowserWeb(WebSearchProvider):
    name='freedom-browser'
    display_name='Freedom GPT · встроенный браузер'

    def is_available(self):
        try:binding();return True
        except (OSError,ValueError,KeyError):return False

    def is_keyless_available(self):return self.is_available()
    def supports_extract(self):return True

    def search(self,query,limit=5):
        try:
            result=send_action({'action':'search','query':query,'limit':min(10,limit)})
            found=result['search']
            return {'success':found['success'],'data':{'web':found['results']},
                    'provider':self.name,'browser_url':result.get('url'),'attempts':found.get('attempts',[]),
                    **({'error':found['error']} if not found['success'] else {})}
        except Exception as exc:
            return {'success':False,'error':'Built-in browser search failed: '+str(exc)[:300],'provider':self.name}

    def extract(self,urls,**kwargs):
        results=[]
        for url in urls:
            try:
                # Navigate and read as one worker command: parallel tool calls
                # must never read a page opened by another extraction.
                result=send_action({'action':'open','url':url,'read':True,'max_chars':30000})
                # News feed URLs redirect through Google's optional-cookie screen.
                # Reject only the observed optional consent, never CAPTCHA or login.
                if urlsplit(url).hostname=='news.google.com':
                    page=result.get('reading') or {}
                    if urlsplit(page.get('url','')).hostname=='consent.google.com' and page.get('access_gate')=='consent':
                        observed=send_action({'action':'inspect'})
                        reject=next((e for e in (observed.get('snapshot') or {}).get('elements',[]) if e.get('tag')=='button' and str(e.get('label','')).strip().casefold() in {'отклонить все','reject all'}),None)
                        if reject:
                            send_action({'action':'click','ref':reject['ref']})
                            result=send_action({'action':'read','max_chars':30000})
                    for _ in range(4):
                        page=result.get('reading') or {};current=urlsplit(page.get('url',''))
                        if current.hostname!='news.google.com' or '/rss/articles/' not in current.path or str(page.get('content','')).strip():break
                        time.sleep(.5);result=send_action({'action':'read','max_chars':30000})
                page=result['reading'];error=None
                if page.get('challenge'):error='The page requires manual CAPTCHA/login confirmation in the visible browser.'
                elif result.get('http_status',200)>=400:error='Page returned HTTP '+str(result['http_status'])
                elif not page.get('content'):error='The page did not provide readable text.'
                results.append({'url':page.get('url') or url,'title':page.get('title',''),'content':page.get('content','') if not error else '',
                                'metadata':{'provider':self.name,'browser_url':page.get('url'),'truncated':page.get('truncated',False)},
                                **({'error':error} if error else {})})
            except Exception as exc:results.append({'url':url,'title':'','content':'','error':str(exc)[:350]})
        return results

def ordinary_capture_target(browser, runner, expected_title='', **kwargs):
    """Bind the observed window to the selected installed executable, including portable Tor.

    Browser labels are not reliable Windows process identities: Tor is firefox.exe,
    and Yandex is browser.exe. Never fall back to another similarly named browser.
    """
    import os,psutil
    from browser_launch import candidates
    exe=next((p for p in candidates(browser) if p.is_file()),None)
    allowed={os.path.normcase(str(exe.resolve()))} if exe else set()
    pids=set()
    for proc in psutil.process_iter(['pid','exe']):
        try:
            if proc.info.get('exe') and os.path.normcase(str(pathlib.Path(proc.info['exe']).resolve())) in allowed:
                pids.add(proc.info['pid'])
        except (OSError,psutil.Error):continue
    listing=runner({'action':'list_windows'},**kwargs)
    if isinstance(listing,str):listing=json.loads(listing)
    windows=listing.get('windows',[]) if isinstance(listing,dict) else []
    eligible=[w for w in windows if w.get('pid') in pids and w.get('window_id') and not w.get('off_screen')]
    if expected_title:
        eligible=[w for w in eligible if expected_title.casefold() in str(w.get('title','')).casefold()]
    selected=max(eligible,key=lambda w:w.get('z_index',0),default=None)
    if not selected:raise ValueError('Окно выбранного браузера не найдено. Откройте его и завершите начальную настройку вручную.')
    return {'pid':selected['pid'],'window_id':selected['window_id']}

_ordinary_targets={}

def ordinary_desktop_call(browser, admission, inner, runner, expected_title='', **kwargs):
    """Read the same observed window after input without invoking auxiliary vision.

    An input is dispatched exactly once. A failed read never retries the input,
    since navigation or typing may already have taken effect.
    """
    key=(str(kwargs.get('session_id','')),str(admission),browser)
    args=dict(inner);action=args.get('action')
    if action=='capture':
        target=_ordinary_targets.get(key)
        if target:
            # A refresh must stay on the window already observed in this admission.
            # If it closed, let the native capture fail; never silently choose another.
            args.pop('app',None);args.update(target);args.setdefault('mode','ax')
            result=runner(args,**kwargs)
            try:data=json.loads(result) if isinstance(result,str) else result
            except (ValueError,TypeError):data={}
            if isinstance(data,dict) and f"No window with window_id {target['window_id']} exists" in str(data.get('error','')):
                _ordinary_targets.pop(key,None)
            return result
        target=ordinary_capture_target(browser,runner,expected_title=expected_title,**kwargs)
        if len(_ordinary_targets)>2048:_ordinary_targets.clear()
        _ordinary_targets[key]=target
        args.pop('app',None);args.update(target)
        args.setdefault('mode','ax')
        return runner(args,**kwargs)
    target=_ordinary_targets.get(key)
    if not target:return json.dumps({'error':'capture_browser_first'})
    args['capture_after']=False
    result=runner(args,**kwargs)
    try:effect=json.loads(result) if isinstance(result,str) else result
    except (ValueError,TypeError):return result
    if isinstance(effect,dict) and effect.get('code')=='window_target_not_found':
        _ordinary_targets.pop(key,None)
        return json.dumps({**effect,'error':'browser_window_lost','retryable':True,
            'message':'Окно исчезло; ввод отклонён. Сначала capture mode=ax: привязка будет восстановлена только к своему окну поиска. Не повторяйте ввод в другом окне вслепую.'},ensure_ascii=False)
    if not isinstance(effect,dict) or effect.get('ok') is not True:return result
    captured=runner({'action':'capture','mode':'ax',**target},**kwargs)
    try:reading=json.loads(captured) if isinstance(captured,str) else captured
    except (ValueError,TypeError):reading={}
    if not isinstance(reading,dict) or reading.get('error') or 'elements' not in reading:
        return json.dumps({'ok':True,'action_result':effect,'read_error':reading,
                           'message':'Действие отправлено, но новое состояние не прочитано. Сначала capture; не повторяйте действие вслепую.'},ensure_ascii=False)
    return json.dumps({**reading,**effect,'action_result':effect},ensure_ascii=False)

def register(ctx):
    ctx.register_web_search_provider(FreedomBrowserWeb())
    async def handle(args,**kwargs):
        if args.get('action')=='desktop':
            from gateway.session_cli_turn import _cli_turn
            bound=_cli_turn.get();text=str(bound[1].get('api_text','')) if bound else ''
            matches=re.findall(r'\[Freedom: обычный браузер\] ([a-z-]+)',text)
            match=matches[-1] if matches else None
            browser=match if match else ('chrome-personal' if '[Freedom: обычный Chrome]' in text else '')
            targets={'chrome-personal':'Chrome','yandex-personal':'Yandex','edge-personal':'MSEdge','tor-personal':'Tor Browser'}
            if browser not in targets or '[Freedom: режим веб-исследования]' not in text:
                return json.dumps({'error':'Ordinary browser control requires an admitted research turn.'})
            inner=dict(args.get('desktop') or {})
            if inner.get('action')=='capture':inner['app']=targets[browser]
            else:inner.pop('app',None)
            for key in ('pid','window_id','display'):inner.pop(key,None)
            from tools.computer_use.tool import handle_computer_use
            expected_title=''
            offset=text.rfind('\n{"personal_browser":')
            if offset>=0:
                try:expected_title=str(json.JSONDecoder().raw_decode(text[offset+1:])[0].get('query',''))[:100]
                except (ValueError,TypeError):pass
            try:return await asyncio.to_thread(ordinary_desktop_call,browser,bound[0],inner,handle_computer_use,expected_title=expected_title,**kwargs)
            except (ValueError,OSError) as exc:return json.dumps({'error':str(exc)},ensure_ascii=False)
        # The app is install-local; no external provider key is exposed to the agent.
        sid=session_id(args.get('session_id') or kwargs.get('session_id'))
        result=await asyncio.to_thread(send_action,args,sid)
        if args.get('action') in {'look','screenshot','inspect'} and result.get('screenshot_path'):
            try:vision=await asyncio.to_thread(ctx.dispatch_tool,'vision_analyze',{'image_url':result['screenshot_path'],'question':args.get('question') or 'Проверь внешний вид страницы, читаемость, компоновку и видимые ошибки.'},**kwargs)
            except Exception:
                return json.dumps({'preview':result,'visual_analysis':{'available':False,'note':'Text and accessible elements are available. Visual analysis requires a compatible vision model.'}},ensure_ascii=False)
            if isinstance(vision,dict):
                vision.setdefault('content',[]).insert(0,{'type':'text','text':'Shared preview state: '+json.dumps(result,ensure_ascii=False)})
                vision.setdefault('meta',{})['screenshot_path']=result['screenshot_path']
                return vision
            return json.dumps({'preview':result,'visual_analysis':vision},ensure_ascii=False)
        return json.dumps(result,ensure_ascii=False)
    schema={'name':'preview_browser','description':'Default shared browser for Freedom GPT web research and website tasks. The user sees this exact page beside the chat. Use search for web results, open with a URL, then read for actual page text without a vision model. Use look for visual inspection and click/fill/press/scroll for interactions. Prefer this visible browser unless the user specifically requests another installed browser. CAPTCHA and login require user intervention.','parameters':{'type':'object','properties':{
        'action':{'type':'string','enum':['desktop','open','search','read','look','screenshot','inspect','click','fill','press','scroll','viewport','reload','back','forward','status','close']},
        'desktop':{'type':'object','description':'Native desktop action in the selected ordinary browser: capture mode=som, then click/type/key/scroll; fresh capture after every action.'},'query':{'type':'string'},'limit':{'type':'integer'},'max_chars':{'type':'integer'},
        'url':{'type':'string'},'question':{'type':'string'},'ref':{'type':'string','description':'Element ref such as p3 from the latest look snapshot'},
        'text':{'type':'string'},'key':{'type':'string'},'x':{'type':'number'},'y':{'type':'number'},'dy':{'type':'integer'},'width':{'type':'integer'},'height':{'type':'integer'},'session_id':{'type':'string','description':'Normally omit; use the current chat id if supplied by the owner settings.'}},'required':['action']}}
    ctx.register_tool(name='preview_browser',toolset='browser',schema=schema,handler=handle,is_async=True,description='Shared visual site preview',emoji='🌐')
