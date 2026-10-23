"""Opt-in Freedom GPT relay. Stores device authorization, never chats or files.

PCs prove possession of independent Ed25519 keys. A phone receives a session
only after explicit approval on its PC. The shared origin serves trusted app
assets: arbitrary HTML/JS from customer machines is never published here.
"""
from __future__ import annotations
import asyncio,contextlib,hashlib,html,json,os,pathlib,secrets,sqlite3,time,uuid
from collections import defaultdict,deque
from aiohttp import web,WSMsgType
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from protocol import *

ROOT=pathlib.Path(__file__).resolve().parent
COOKIE='__Host-FreedomPhone';CLAIM='__Host-FreedomClaim'

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

class Relay:
    def __init__(self,root=ROOT,origin='https://aionpc.ru:8445',*,secure=True,max_online=25,state=None):
        self.root=pathlib.Path(root);self.origin=origin;self.secure=secure;self.max_online=max_online
        self.root.mkdir(parents=True,exist_ok=True)
        self.state_dir=pathlib.Path(state) if state else self.root;self.state_dir.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.state_dir/'devices.sqlite');self.db.row_factory=sqlite3.Row
        self.db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,public_key TEXT NOT NULL,label TEXT NOT NULL,created REAL NOT NULL,last_seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS phones(token_hash TEXT PRIMARY KEY,client_id TEXT NOT NULL UNIQUE,label TEXT NOT NULL,expires REAL NOT NULL,created REAL NOT NULL);''')
        self.db.commit()
        if os.name!='nt':(self.state_dir/'devices.sqlite').chmod(0o600)
        self.agents={};self.pairs={};self.claims={};self.rates=defaultdict(deque);self.browser_sockets=defaultdict(set);self.authenticating=0

    def rate(self,key,limit,window=60):
        now=time.time();q=self.rates[key]
        while q and q[0]<now-window:q.popleft()
        if len(q)>=limit:raise web.HTTPTooManyRequests(text='Слишком много запросов. Попробуйте позже.')
        q.append(now)
        if len(self.rates)>10000:
            for k in list(self.rates):
                if not self.rates[k] or self.rates[k][-1]<now-3600:self.rates.pop(k,None)

    def expire(self):
        now=time.time()
        for table in [self.pairs,self.claims]:
            for k in list(table):
                if table[k]['expires']<now:table.pop(k,None)

    def session(self,request):
        raw=request.cookies.get(COOKIE,'')
        if not raw or len(raw)>100:return None
        row=self.db.execute('SELECT * FROM phones WHERE token_hash=? AND expires>?',(digest(raw),time.time())).fetchone()
        return dict(row) if row else None

    def check_origin(self,request,required=False):
        value=request.headers.get('Origin')
        if (value and value!=self.origin) or (required and value!=self.origin):raise web.HTTPForbidden(text='Недопустимый источник запроса.')

    @web.middleware
    async def security(self,request,handler):
        self.expire()
        # The deployment binds only to loopback and has a single HTTPS proxy.
        if self.secure and request.host!=self.origin.split('://',1)[1]:raise web.HTTPForbidden(text='Invalid host')
        try:response=await handler(request)
        except web.HTTPException as exc:response=exc
        except (ValueError,TypeError,KeyError):response=web.Response(status=400,text='Некорректный запрос.')
        if not response.prepared:
            response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
                'X-Robots-Tag':'noindex, nofollow, noarchive','Cache-Control':'private, max-age=31536000, immutable' if request.path.startswith('/assets/') else 'no-store',
                'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' "+self.origin.replace('https:','wss:').replace('http:','ws:')+"; font-src 'self'; worker-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"})
        return response

    async def send(self,agent,data):
        async with agent['lock']:await agent['ws'].send_json(data)

    def phone_info(self,cid):
        row=self.db.execute('SELECT label,created,expires FROM phones WHERE client_id=? AND expires>?',(cid,time.time())).fetchone()
        return dict(row) if row else None

    async def control(self,agent,message):
        rid=message.get('id');op=message.get('action');cid=agent['id'];result={}
        if op=='pair':
            self.rate('pair:'+cid,10,3600)
            for k in list(self.pairs):
                if self.pairs[k]['client_id']==cid:self.pairs.pop(k,None)
            raw=secrets.token_urlsafe(32);expires=time.time()+300
            self.pairs[digest(raw)]={'client_id':cid,'expires':expires,'used':False}
            result={'pair_url':self.origin+'/pair/'+raw,'expires':expires}
        elif op in {'approve','reject'}:
            claim=self.claims.get(message.get('claim_id',''))
            if not claim or claim['client_id']!=cid or claim.get('state')!='waiting':raise ValueError('Запрос телефона истёк.')
            if op=='reject':claim['state']='rejected'
            else:
                raw=secrets.token_urlsafe(32);now=time.time()
                self.db.execute('DELETE FROM phones WHERE client_id=?',(cid,))
                self.db.execute('INSERT INTO phones VALUES(?,?,?,?,?)',(digest(raw),cid,claim['label'],now+90*86400,now));self.db.commit()
                claim.update(state='approved',session_raw=raw)
                await self.close_phones(cid)
            result={'ok':True}
        elif op=='revoke':
            self.db.execute('DELETE FROM phones WHERE client_id=?',(cid,));self.db.commit();await self.close_phones(cid)
            for claim in self.claims.values():
                if claim['client_id']==cid:claim.update(state='rejected');claim.pop('session_raw',None)
            result={'ok':True}
        elif op!='status':raise ValueError('Unknown control operation')
        result.update(device=self.phone_info(cid),pending=[{'id':k,'label':v['label'],'code':v['code'],'expires':v['expires']}
            for k,v in self.claims.items() if v['client_id']==cid and v['state']=='waiting'])
        await self.send(agent,{'type':'control.result','id':rid,'result':result})

    async def close_phones(self,cid):
        for ws in list(self.browser_sockets[cid]):
            with contextlib.suppress(Exception):await ws.close(code=1008,message=b'Phone authorization changed')

    async def agent(self,request):
        self.rate('auth:'+request.headers.get('X-Real-IP',request.remote or '?'),40)
        if self.authenticating>=50:raise web.HTTPServiceUnavailable(text='Сервер связи занят.')
        ws=web.WebSocketResponse(heartbeat=20,compress=False,max_msg_size=MAX_FRAME);await ws.prepare(request)
        self.authenticating+=1
        agent=None
        try:
            nonce=secrets.token_urlsafe(32);await ws.send_json({'type':'challenge','nonce':nonce,'version':VERSION})
            message=await ws.receive_json(timeout=10)
            if message.get('type')!='auth' or message.get('version')!=VERSION:raise ValueError('Protocol mismatch')
            public=decode(message.get('public',''),32);cid=client_id(public)
            Ed25519PublicKey.from_public_bytes(public).verify(decode(message.get('signature',''),64),signed_challenge(nonce,self.origin))
            if cid not in self.agents and len(self.agents)>=self.max_online:raise ValueError('Сервер связи занят. Попробуйте позже.')
            existing=self.db.execute('SELECT id FROM clients WHERE id=?',(cid,)).fetchone()
            if not existing:
                self.rate('register:'+request.headers.get('X-Real-IP',request.remote or '?'),10,3600)
                if self.db.execute('SELECT COUNT(*) FROM clients').fetchone()[0]>=5000:raise ValueError('Registration capacity reached')
            label=str(message.get('label') or 'Мой компьютер')[:80]
            now=time.time();self.db.execute('INSERT INTO clients VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET label=excluded.label,last_seen=excluded.last_seen',
                (cid,encode(public),label,now,now));self.db.commit()
            previous=self.agents.get(cid)
            if previous:await previous['ws'].close(code=1001,message=b'PC reconnected')
            agent={'id':cid,'ws':ws,'label':label,'lock':asyncio.Lock(),'requests':{},'active_http':0}
            self.agents[cid]=agent;await ws.send_json({'type':'ready','client_id':cid,'version':VERSION})
            self.authenticating-=1;agent['authenticated']=True
            async for event in ws:
                if event.type!=WSMsgType.TEXT:break
                message=json.loads(event.data);kind=message.get('type');rid=message.get('id')
                if kind=='control':
                    try:await self.control(agent,message)
                    except (ValueError,web.HTTPException) as exc:await self.send(agent,{'type':'control.result','id':rid,'error':str(exc)[:160]})
                elif kind in {'http.head','http.data','http.end','ws.open','ws.data','ws.close','request.error'}:
                    queue=agent['requests'].get(rid)
                    if queue:
                        try:await asyncio.wait_for(queue.put(message),5)
                        except asyncio.TimeoutError:raise ValueError('Phone receiver stalled')
                else:raise ValueError('Unknown frame')
        except Exception as exc:
            with contextlib.suppress(Exception):await ws.send_json({'type':'error','error':str(exc)[:160] if isinstance(exc,ValueError) else 'Соединение с ПК закрыто.'})
        finally:
            if not agent or not agent.get('authenticated'):self.authenticating-=1
            if agent:
                for queue in agent['requests'].values():
                    with contextlib.suppress(asyncio.QueueFull):queue.put_nowait({'type':'request.error','error':'Компьютер отключился.'})
                if self.agents.get(agent['id']) is agent:self.agents.pop(agent['id'],None)
            await ws.close()
        return ws

    async def pair_page(self,request):
        return web.FileResponse(self.root/'web/pair.html')

    async def pair_info(self,request):
        self.rate('info:'+request.headers.get('X-Real-IP',request.remote or '?'),60)
        pair=self.pairs.get(digest(request.match_info['token']))
        if not pair or pair['used']:raise web.HTTPGone(text='QR-код истёк. Создайте новый на своём ПК.')
        agent=self.agents.get(pair['client_id'])
        if not agent:raise web.HTTPServiceUnavailable(text='Откройте Freedom GPT на компьютере.')
        return web.json_response({'label':agent['label'],'expires':pair['expires']})

    async def claim(self,request):
        self.check_origin(request,True);self.rate('claim:'+request.headers.get('X-Real-IP',request.remote or '?'),10)
        data=await request.json();pair=self.pairs.get(digest(str(data.get('token',''))))
        if not pair or pair['used']:raise web.HTTPGone(text='QR-код истёк. Создайте новый на ПК.')
        if pair['client_id'] not in self.agents:raise web.HTTPServiceUnavailable(text='Компьютер не в сети.')
        pair['used']=True;raw=secrets.token_urlsafe(32);key=digest(raw)
        label='iPhone · Safari' if 'iPhone' in request.headers.get('User-Agent','') else 'Телефон · браузер'
        self.claims[key]={'client_id':pair['client_id'],'label':label,'code':f'{secrets.randbelow(1000000):06d}',
            'expires':time.time()+300,'state':'waiting'}
        response=web.json_response({'code':self.claims[key]['code'],'state':'waiting'})
        response.set_cookie(CLAIM,raw,secure=self.secure,httponly=True,samesite='Strict',max_age=300,path='/');return response

    async def claim_status(self,request):
        value=request.cookies.get(CLAIM,'');claim=self.claims.get(digest(value)) if value else None
        if not claim:raise web.HTTPGone(text='Подключение истекло. Начните заново на ПК.')
        response=web.json_response({'state':claim['state'],'code':claim['code']})
        if claim['state']=='approved':
            # Re-check revocation: a late poll must not restore a revoked phone.
            row=self.db.execute('SELECT client_id FROM phones WHERE token_hash=?',(digest(claim['session_raw']),)).fetchone()
            if not row:raise web.HTTPForbidden(text='Доступ отозван на ПК.')
            response.set_cookie(COOKIE,claim['session_raw'],secure=self.secure,httponly=True,samesite='Strict',max_age=90*86400,path='/')
            response.del_cookie(CLAIM,path='/')
        return response

    async def logout(self,request):
        self.check_origin(request,True);session=self.session(request)
        if session:
            self.db.execute('DELETE FROM phones WHERE token_hash=?',(session['token_hash'],));self.db.commit();await self.close_phones(session['client_id'])
        response=web.json_response({'ok':True});response.del_cookie(COOKIE,path='/');return response

    async def root_page(self,request):
        session=self.session(request)
        if not session:return web.FileResponse(self.root/'web/index.html')
        text=(self.root/'ui/index.html').read_text(encoding='utf-8')
        text=text.replace('<html ', '<html data-freedom-remote="'+session['client_id']+'" ',1)
        return web.Response(text=text,content_type='text/html')

    async def proxy(self,request):
        self.check_origin(request,request.method not in {'GET','HEAD'})
        if request.headers.get('Upgrade','').lower()=='websocket':self.check_origin(request,True)
        session=self.session(request)
        if not session:raise web.HTTPUnauthorized(text='Подключите телефон через QR-код в приложении.')
        try:path=api_path(request.raw_path)
        except ValueError:raise web.HTTPForbidden(text='Этот раздел доступен только на компьютере.')
        agent=self.agents.get(session['client_id'])
        if not agent:raise web.HTTPServiceUnavailable(text='Компьютер не в сети. Откройте Freedom GPT на ПК.')
        if agent['active_http']>=12:raise web.HTTPTooManyRequests(text='Слишком много одновременных запросов.')
        rid=uuid.uuid4().hex;queue=asyncio.Queue(maxsize=12);agent['requests'][rid]=queue;agent['active_http']+=1
        async def receive():
            item=await asyncio.wait_for(queue.get(),120)
            if item['type']=='request.error':raise web.HTTPServiceUnavailable(text='Нет связи с приложением на ПК.')
            return item
        try:
            if request.headers.get('Upgrade','').lower()=='websocket':
                await self.send(agent,{'type':'ws.open','id':rid,'path':path,'headers':request_headers(dict(request.headers))})
                item=await receive()
                if item['type']!='ws.open':raise web.HTTPBadGateway()
                socket=web.WebSocketResponse(heartbeat=20,compress=False,max_msg_size=MAX_FRAME);await socket.prepare(request)
                self.browser_sockets[agent['id']].add(socket)
                async def to_pc():
                    async for event in socket:
                        if event.type==WSMsgType.TEXT:await self.send(agent,{'type':'ws.data','id':rid,'data':event.data})
                        else:break
                async def from_pc():
                    while True:
                        item=await receive()
                        if item['type']=='ws.close':break
                        if item['type']=='ws.data':await socket.send_str(item['data'])
                tasks=[asyncio.create_task(to_pc()),asyncio.create_task(from_pc())]
                try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for task in tasks:task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True);self.browser_sockets[agent['id']].discard(socket);await socket.close()
                return socket
            if request.method not in {'GET','HEAD','POST','PATCH','PUT','DELETE','OPTIONS'}:raise web.HTTPMethodNotAllowed(request.method,[])
            await self.send(agent,{'type':'http.start','id':rid,'method':request.method,'path':path,'headers':request_headers(dict(request.headers))})
            size=0
            async for chunk in request.content.iter_chunked(CHUNK):
                size+=len(chunk)
                if size>MAX_UPLOAD:raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD,actual_size=size)
                await self.send(agent,{'type':'http.body','id':rid,'data':encode(chunk)})
            await self.send(agent,{'type':'http.body.end','id':rid})
            head=await receive()
            if head['type']!='http.head' or not isinstance(head.get('status'),int) or not 200<=head['status']<=599:raise web.HTTPBadGateway()
            headers=response_headers(head.get('headers',{}),request.path)
            headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','X-Robots-Tag':'noindex, nofollow','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})
            response=web.StreamResponse(status=head['status'],headers=headers);await response.prepare(request);total=0
            while True:
                item=await receive()
                if item['type']=='http.end':break
                if not self.session(request):raise web.HTTPForbidden(text='Доступ отозван.')
                if item['type']!='http.data':raise web.HTTPBadGateway()
                raw=decode(item.get('data'));total+=len(raw)
                if total>MAX_DOWNLOAD:raise web.HTTPBadGateway()
                await response.write(raw)
            await response.write_eof();return response
        finally:
            agent['requests'].pop(rid,None);agent['active_http']-=1
            with contextlib.suppress(Exception):await self.send(agent,{'type':'cancel','id':rid})

    async def health(self,request):return web.json_response({'service':'Freedom GPT Connect','version':VERSION,'online':len(self.agents),'capacity':self.max_online})

    async def cleanup(self,app):
        for agent in list(self.agents.values()):await agent['ws'].close()
        self.db.close()

    def app(self):
        app=web.Application(middlewares=[self.security],client_max_size=MAX_UPLOAD)
        app.router.add_get('/phone/health',self.health);app.router.add_get('/phone/agent',self.agent)
        app.router.add_get('/pair/{token}',self.pair_page);app.router.add_get('/phone/pair-info/{token}',self.pair_info)
        app.router.add_post('/phone/claim',self.claim);app.router.add_get('/phone/claim',self.claim_status);app.router.add_post('/phone/logout',self.logout)
        app.router.add_get('/',self.root_page)
        app.router.add_get('/freedom.svg',lambda r:web.FileResponse(self.root/'ui/freedom.svg'))
        app.router.add_get('/phone/portal.js',lambda r:web.FileResponse(self.root/'web/portal.js'))
        app.router.add_static('/assets/',self.root/'ui/assets')
        app.router.add_route('*','/api/{tail:.*}',self.proxy);app.on_cleanup.append(self.cleanup);return app

if __name__=='__main__':
    relay=Relay(pathlib.Path(os.environ.get('FREEDOM_CONNECT_ROOT',ROOT)),origin=os.environ.get('FREEDOM_CONNECT_ORIGIN','https://aionpc.ru:8445'),
        max_online=int(os.environ.get('FREEDOM_CONNECT_CAPACITY','25')),state=os.environ.get('FREEDOM_CONNECT_STATE'))
    web.run_app(relay.app(),host='127.0.0.1',port=int(os.environ.get('FREEDOM_CONNECT_PORT','18869')),access_log=None,print=None)
