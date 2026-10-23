"""Optional phone access for every portable installation; no owner credentials.

The PC makes an outbound signed connection to its configured relay. Each relay
request is restricted to the existing loopback API. Phone authorization and
pairing controls themselves are never forwarded through that channel.
"""
from __future__ import annotations
import asyncio,contextlib,hashlib,io,json,os,pathlib,secrets,socket,sys,time,urllib.parse,uuid
import bootstrap
from bootstrap import ROOT,read,write
from aiohttp import ClientSession,ClientTimeout,ClientWSTimeout,WSMsgType,web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cloud_vault import CloudVault
from remote_protocol import *

DEFAULT_RELAY='https://aionpc.ru:8445'

class DeviceKeys:
    def __init__(self,root):self.root=pathlib.Path(root);self.path=self.root/'data/remote-device.key'
    def get(self):
        if self.path.exists():
            value=self.path.read_bytes();raw=CloudVault.crypt(value,True) if os.name=='nt' else value
            return Ed25519PrivateKey.from_private_bytes(raw)
        key=Ed25519PrivateKey.generate();raw=key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        raw=CloudVault.crypt(raw) if os.name=='nt' else raw
        # Atomic exclusive creation also prevents two controllers replacing identity.
        try:
            fd=os.open(str(self.path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(raw)
        except FileExistsError:return self.get()
        if os.name!='nt':self.path.chmod(0o600)
        return key

class RemoteClient:
    def __init__(self,root=ROOT,*,api_port=None,allow_http_test=False):
        self.root=pathlib.Path(root);self.settings=self.root/'data/remote-access.json';self.api_port=api_port
        self.allow_http_test=allow_http_test;self.state='disabled';self.error=None;self.task=None;self.socket=None;self.client=None
        self.pending={};self.requests={};self.control_lock=asyncio.Lock();self.send_lock=asyncio.Lock()
        self.pair=None;self.device=None;self.claims=[];self.cid=None;self.key=None;self.stopping=False

    def cfg(self):return {'enabled':False,'relay':DEFAULT_RELAY,'label':socket.gethostname()[:60],**read(self.settings,{})}
    def port(self):return self.api_port or bootstrap.config()['ui_port']
    def validate_relay(self,value):
        parsed=urllib.parse.urlsplit(str(value))
        if (parsed.scheme not in ({'https','http'} if self.allow_http_test else {'https'}) or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {'','/'} or parsed.query or parsed.fragment):raise ValueError('Адрес сервера должен начинаться с https:// и не содержать пароля или пути.')
        return str(value).rstrip('/')

    async def send(self,data):
        if not self.socket or self.socket.closed:raise ValueError('Соединение с сервером ещё не готово.')
        async with self.send_lock:await self.socket.send_json(data)

    async def control(self,action,**payload):
        rid=uuid.uuid4().hex;future=asyncio.get_running_loop().create_future();self.pending[rid]=future
        try:
            await self.send({'type':'control','id':rid,'action':action,**payload})
            result=await asyncio.wait_for(future,12)
            if result.get('error'):raise ValueError(result['error'])
            value=result.get('result',{})
            if 'device' in value:self.device=value['device']
            if 'pending' in value:self.claims=value['pending']
            return value
        finally:self.pending.pop(rid,None)

    async def polling(self):
        try:
            while True:
                await self.control('status');await asyncio.sleep(2)
        except (ValueError,asyncio.TimeoutError):
            if self.socket:await self.socket.close()

    async def request_body(self,queue):
        total=0
        while True:
            frame=await asyncio.wait_for(queue.get(),60)
            if frame['type']=='http.body.end':return
            raw=decode(frame.get('data'));total+=len(raw)
            if total>MAX_UPLOAD:raise ValueError('Загрузка слишком большая.')
            yield raw

    async def http(self,frame,queue):
        rid=frame['id'];path=api_path(frame.get('path'));method=frame.get('method')
        if method not in {'GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'}:raise ValueError('Invalid method')
        headers=request_headers(frame.get('headers',{}));headers.update({'Host':f'127.0.0.1:{self.port()}','Origin':f'http://127.0.0.1:{self.port()}'})
        async with self.client.request(method,f'http://127.0.0.1:{self.port()}'+path,headers=headers,
                data=self.request_body(queue),allow_redirects=False,timeout=ClientTimeout(total=None,sock_connect=5,sock_read=300)) as response:
            await self.send({'type':'http.head','id':rid,'status':response.status,'headers':response_headers(dict(response.headers),path)})
            total=0
            async for chunk in response.content.iter_chunked(CHUNK):
                total+=len(chunk)
                if total>MAX_DOWNLOAD:raise ValueError('Remote download limit reached')
                await self.send({'type':'http.data','id':rid,'data':encode(chunk)})
            await self.send({'type':'http.end','id':rid})

    async def websocket(self,frame,queue):
        rid=frame['id'];path=api_path(frame.get('path'))
        if urllib.parse.urlsplit(path).path!='/api/ws':raise ValueError('Unsupported websocket')
        headers=request_headers(frame.get('headers',{}));headers.update({'Host':f'127.0.0.1:{self.port()}','Origin':f'http://127.0.0.1:{self.port()}'})
        async with self.client.ws_connect(f'http://127.0.0.1:{self.port()}'+path,headers=headers,heartbeat=20,compress=0,max_msg_size=MAX_FRAME) as ws:
            await self.send({'type':'ws.open','id':rid})
            async def from_api():
                async for event in ws:
                    if event.type==WSMsgType.TEXT:await self.send({'type':'ws.data','id':rid,'data':event.data})
                    else:break
            async def to_api():
                while True:
                    message=await queue.get()
                    if message['type']=='ws.data':await ws.send_str(message['data'])
                    else:break
            tasks=[asyncio.create_task(from_api()),asyncio.create_task(to_api())]
            try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
        await self.send({'type':'ws.close','id':rid})

    async def worker(self,frame,queue):
        rid=frame['id']
        try:
            if frame['type']=='http.start':await self.http(frame,queue)
            else:await self.websocket(frame,queue)
        except asyncio.CancelledError:raise
        except Exception:
            with contextlib.suppress(Exception):await self.send({'type':'request.error','id':rid,'error':'Локальная панель пока недоступна.'})
        finally:
            if self.requests.get(rid,(None,None))[0] is queue:self.requests.pop(rid,None)

    async def connect(self):
        delay=2
        while not self.stopping and self.cfg()['enabled']:
            self.state='connecting'
            try:
                relay=self.validate_relay(self.cfg()['relay']);self.key=DeviceKeys(self.root).get()
                public=self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
                url=relay.replace('https:','wss:').replace('http:','ws:')+'/phone/agent'
                async with self.client.ws_connect(url,heartbeat=20,compress=0,max_msg_size=MAX_FRAME,timeout=ClientWSTimeout(ws_close=5)) as socket:
                    self.socket=socket;challenge=await socket.receive_json(timeout=12)
                    if challenge.get('type')!='challenge' or challenge.get('version')!=VERSION:raise ValueError('Несовместимый сервер подключения.')
                    nonce=challenge.get('nonce')
                    if not isinstance(nonce,str) or not 16<len(nonce)<100:raise ValueError('Некорректный запрос сервера.')
                    await self.send({'type':'auth','version':VERSION,'public':encode(public),
                        'signature':encode(self.key.sign(signed_challenge(nonce,relay))),'label':self.cfg()['label']})
                    ready=await socket.receive_json(timeout=12)
                    if ready.get('type')!='ready' or ready.get('client_id')!=client_id(public):raise ValueError(ready.get('error') or 'Не удалось подтвердить компьютер.')
                    self.cid=ready['client_id'];self.state='connected';self.error=None;delay=2
                    poll=asyncio.create_task(self.polling())
                    try:
                        async for event in socket:
                            if event.type!=WSMsgType.TEXT:break
                            message=json.loads(event.data);kind=message.get('type');rid=message.get('id')
                            if kind=='control.result':
                                future=self.pending.get(rid)
                                if future and not future.done():future.set_result(message)
                            elif kind in {'http.start','ws.open'}:
                                if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}',rid) or rid in self.requests or len(self.requests)>=16:raise ValueError('Invalid request admission')
                                queue=asyncio.Queue(maxsize=12);task=asyncio.create_task(self.worker(message,queue));self.requests[rid]=(queue,task)
                            elif kind in {'http.body','http.body.end','ws.data'}:
                                item=self.requests.get(rid)
                                if item:await asyncio.wait_for(item[0].put(message),10)
                            elif kind=='cancel':
                                item=self.requests.pop(rid,None)
                                if item:item[1].cancel()
                            else:raise ValueError('Unknown relay frame')
                    finally:
                        poll.cancel();await asyncio.gather(poll,return_exceptions=True)
            except asyncio.CancelledError:raise
            except Exception as exc:
                self.error=str(exc)[:180] if isinstance(exc,ValueError) else 'Переподключаемся. Проверьте интернет на компьютере.'
            finally:
                self.socket=None
                for future in self.pending.values():
                    if not future.done():future.set_exception(ValueError('Соединение с сервером изменилось. Повторите действие.'))
                tasks=[task for queue,task in self.requests.values()]
                self.requests.clear()
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
            self.state='connecting' if self.cfg()['enabled'] else 'disabled'
            if self.cfg()['enabled']:await asyncio.sleep(delay);delay=min(delay*2,30)

    def status(self):
        cfg=self.cfg();pair=self.pair if self.pair and self.pair['expires']>time.time() and self.state=='connected' else None
        return {'enabled':cfg['enabled'],'relay':cfg['relay'],'label':cfg['label'],'state':self.state,'error':self.error,
            'public_url':cfg['relay']+'/','pair':pair,'device':self.device,'pending':self.claims,'client_id':self.cid,
            'upload_limit_mb':MAX_UPLOAD//1024//1024,'requires_internet':True,'approval_on_pc_required':True}

    async def get_status(self,request):return web.json_response(self.status())
    async def action(self,request):
        data=await request.json();action=data.get('action')
        async with self.control_lock:
            if action=='settings':
                if not isinstance(data.get('enabled'),bool):raise web.HTTPBadRequest(text='Некорректное значение.')
                cfg=self.cfg();cfg['enabled']=data['enabled']
                if 'relay' in data:cfg['relay']=self.validate_relay(data['relay'])
                if 'label' in data:cfg['label']=str(data['label']).strip()[:80] or 'Мой компьютер'
                write(self.settings,cfg);await self.restart()
            elif action=='pair':
                if self.state!='connected':raise ValueError('Сначала включите доступ и дождитесь подключения.')
                self.pair=await self.control('pair')
            elif action in {'approve','reject'}:
                await self.control(action,claim_id=str(data.get('claim_id','')));self.pair=None
            elif action=='revoke':await self.control('revoke');self.pair=None
            else:raise ValueError('Неизвестное действие.')
        return web.json_response(self.status())

    async def qr(self,request):
        if not self.pair or self.pair['expires']<=time.time():raise web.HTTPGone()
        import qrcode,qrcode.image.svg
        output=io.BytesIO();qrcode.make(self.pair['pair_url'],image_factory=qrcode.image.svg.SvgPathImage,box_size=7,border=4).save(output)
        return web.Response(body=output.getvalue(),content_type='image/svg+xml',headers={'Cache-Control':'no-store'})

    async def restart(self):
        if self.task:
            self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None
        self.state='disabled';self.pair=None;self.claims=[];self.error=None
        if self.cfg()['enabled']:self.task=asyncio.create_task(self.connect())
    async def start(self,app):
        self.client=ClientSession(auto_decompress=True);await self.restart()
    async def stop(self,app):
        self.stopping=True
        if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        if self.client:await self.client.close()
    def register(self,app):
        app.router.add_get('/api/phone',self.get_status);app.router.add_post('/api/phone',self.action);app.router.add_get('/api/phone/qr.svg',self.qr)
        app.on_startup.append(self.start);app.on_cleanup.append(self.stop)
