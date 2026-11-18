"""Same-origin desktop bridge. The public messenger session stays in a DPAPI vault."""
import asyncio,contextlib,html,json,os,pathlib,re,secrets,subprocess
from aiohttp import web,ClientSession,ClientTimeout,WSMsgType,CookieJar
from yarl import URL
from cloud_vault import CloudVault

class MessengerBridge:
    def __init__(self,root,token='',origin='https://aionpc.ru:8446',persist=None):
        self.root=pathlib.Path(root);self.folder=self.root/'runtime/messenger';self.data=self.root/'data/messenger-embedded'
        self.origin=origin;self.token=token;self.persist=os.name=='nt' if persist is None else persist
        self.cookie='';self.client=None;self.lock=asyncio.Lock();self.sockets=set();self.unread=0
        if self.persist and (self.data/'session.dpapi').exists():
            with contextlib.suppress(OSError,ValueError,KeyError):self.cookie=json.loads(CloudVault.crypt((self.data/'session.dpapi').read_bytes(),True))['cookie']
    async def session(self):
        async with self.lock:
            if self.client is None:
                jar=CookieJar(unsafe=self.origin.startswith('http://127.0.0.1'))
                if self.cookie:jar.update_cookies({'fm_session':self.cookie},response_url=URL(self.origin))
                self.client=ClientSession(cookie_jar=jar,timeout=ClientTimeout(total=40),headers={'Origin':self.origin})
            return self.client
    def save_cookie(self):
        item=self.client.cookie_jar.filter_cookies(URL(self.origin)).get('fm_session');self.cookie=item.value if item else ''
        if self.persist:
            self.data.mkdir(parents=True,exist_ok=True);tmp=self.data/'session.new';tmp.write_bytes(CloudVault.crypt(json.dumps({'cookie':self.cookie}).encode()));os.replace(tmp,self.data/'session.dpapi')
    def status(self):return {'available':True,'embedded':True,'signed_in':bool(self.cookie),'unread':self.unread,'server':self.origin}
    def open(self):
        exe=self.folder/'FreedomMessenger.exe'
        if not exe.is_file():raise ValueError('Клиент Messenger не собран.')
        subprocess.Popen([str(exe)],cwd=self.folder,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));return {'opened':True}
    async def frame(self,request):
        text=(self.root/'dist/messenger.html').read_text(encoding='utf-8')
        meta='<meta name="fm-embedded" content="1"><meta name="fm-api" content="/api/messenger/remote"><meta name="fm-ws" content="/api/messenger/ws"><meta name="fm-csrf" content="'+html.escape(self.token,quote=True)+'">'
        return web.Response(text=text.replace('<head>','<head>'+meta),content_type='text/html')
    async def proxy(self,request):
        path=request.match_info['path'];read=bool(re.fullmatch(r'(?:state|search|history/[0-9]{8,12}|files/[a-f0-9]{32})',path));write=path in {'auth/register','auth/login','contacts','profile','send','receipt','upload','logout','delete-account'}
        if not ((request.method=='GET' and read) or (request.method=='POST' and write)):raise web.HTTPNotFound()
        body=await request.read()
        if len(body)>11*1024**2:raise web.HTTPRequestEntityTooLarge(max_size=11*1024**2,actual_size=len(body))
        client=await self.session();headers={}
        if request.content_type:headers['Content-Type']=request.headers.get('Content-Type','application/json')
        async with client.request(request.method,self.origin+'/v1/'+path,params=request.query,data=body or None,headers=headers,allow_redirects=False) as remote:
            data=await remote.read()
            if remote.status==401 or (path in {'logout','delete-account'} and remote.status==200):client.cookie_jar.clear();self.unread=0
            if path.startswith('auth/') or path in {'logout','delete-account'} or remote.status==401:self.save_cookie()
            if path=='state' and remote.status==200:self.unread=sum(c.get('unread',0) for c in json.loads(data).get('contacts',[]))
            if path in {'logout','delete-account'} and remote.status==200:self.unread=0
            response=web.Response(body=data,status=remote.status)
            for name in ('Content-Type','Content-Disposition','X-Content-Type-Options'):
                if name in remote.headers:response.headers[name]=remote.headers[name]
            return response
    async def socket(self,request):
        if not secrets.compare_digest(request.query.get('token',''),self.token):raise web.HTTPForbidden()
        client=await self.session()
        try:remote=await client.ws_connect(self.origin.replace('https:','wss:').replace('http:','ws:')+'/v1/ws',heartbeat=20,max_msg_size=65536)
        except Exception:raise web.HTTPUnauthorized(text='Войдите в мессенджер.')
        local=web.WebSocketResponse(heartbeat=20,max_msg_size=8192);await local.prepare(request);self.sockets.add(local)
        async def relay(source,target):
            async for msg in source:
                if msg.type==WSMsgType.TEXT:await target.send_str(msg.data)
                elif msg.type in {WSMsgType.CLOSE,WSMsgType.ERROR}:break
        tasks=[asyncio.create_task(relay(local,remote)),asyncio.create_task(relay(remote,local))]
        try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True);await remote.close();await local.close();self.sockets.discard(local)
        return local
    def register(self,app):
        async def status(r):return web.json_response(self.status())
        async def nonce(r):return web.json_response({'token':self.token})
        async def launch(r):return web.json_response(await asyncio.to_thread(self.open))
        async def cleanup(a):
            for ws in list(self.sockets):await ws.close()
            if self.client:await self.client.close()
        app.router.add_get('/api/messenger',status);app.router.add_post('/api/messenger/open',launch)
        app.router.add_get('/api/messenger/token',nonce)
        app.router.add_get('/api/messenger/frame',self.frame);app.router.add_get('/api/messenger/ws',self.socket)
        app.router.add_route('GET','/api/messenger/remote/{path:.+}',self.proxy);app.router.add_route('POST','/api/messenger/remote/{path:.+}',self.proxy)
        app.on_cleanup.append(cleanup)
