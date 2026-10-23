"""A shared preview surface; no browser-provider or existing tool overrides."""
import asyncio,json,pathlib,urllib.request

def register(ctx):
    async def handle(args,**kwargs):
        # The app is install-local; no external provider key is exposed to the agent.
        binding=pathlib.Path(__file__).with_name('runtime.json')
        app=(binding.parent/json.loads(binding.read_text(encoding='utf-8'))['app_relative']).resolve()
        route=json.loads((app/'data/preview-control.json').read_text(encoding='utf-8'))
        sid=args.get('session_id') or kwargs.get('session_id') or kwargs.get('task_id') or 'workspace'
        def send():
            q=urllib.request.Request(route['url']+'/'+sid,data=json.dumps(args).encode(),headers={'Authorization':'Bearer '+route['key'],'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(q,timeout=50) as response:return json.load(response)
        result=await asyncio.to_thread(send)
        if args.get('action') in {'look','screenshot','inspect'} and result.get('screenshot_path'):
            vision=await asyncio.to_thread(ctx.dispatch_tool,'vision_analyze',{'image_url':result['screenshot_path'],'question':args.get('question') or 'Проверь внешний вид страницы, читаемость, компоновку и видимые ошибки.'},**kwargs)
            if isinstance(vision,dict):
                vision.setdefault('content',[]).insert(0,{'type':'text','text':'Shared preview state: '+json.dumps(result,ensure_ascii=False)})
                vision.setdefault('meta',{})['screenshot_path']=result['screenshot_path']
                return vision
            return json.dumps({'preview':result,'visual_analysis':vision},ensure_ascii=False)
        return json.dumps(result,ensure_ascii=False)
    schema={'name':'preview_browser','description':'Use the built-in browser panel the user sees in Freedom GPT. Open a local dev-server URL or website, inspect it with look (screenshot pixels plus accessible elements), then click/fill/press/scroll. After building a website, visually inspect desktop and mobile layouts. This does not replace browser_exec or regular Chrome/Yandex/Opera/Tor for their own tasks.','parameters':{'type':'object','properties':{
        'action':{'type':'string','enum':['open','look','screenshot','inspect','click','fill','press','scroll','viewport','reload','back','forward','status','close']},
        'url':{'type':'string'},'question':{'type':'string'},'ref':{'type':'string','description':'Element ref such as p3 from the latest look snapshot'},
        'text':{'type':'string'},'key':{'type':'string'},'x':{'type':'number'},'y':{'type':'number'},'dy':{'type':'integer'},'width':{'type':'integer'},'height':{'type':'integer'},'session_id':{'type':'string','description':'Normally omit; use the current chat id if supplied by the owner settings.'}},'required':['action']}}
    ctx.register_tool(name='preview_browser',toolset='browser',schema=schema,handler=handle,is_async=True,description='Shared visual site preview',emoji='🌐')
