"""A loopback-only shared browser surface for the user and the local agent."""
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import pathlib
import re
import secrets
import shutil
import time
import uuid
from urllib.parse import urlparse

from aiohttp import web
log=logging.getLogger('freedom.preview')


class PreviewBrowser:
    def __init__(self,root,portable,bridge,artifact):
        self.root,self.portable,self.bridge,self.artifact=root,portable,bridge,artifact
        source=root/'agent_plugins/freedom-preview'
        if not source.is_dir():source=root/'runtime/freedom/agent_plugins/freedom-preview'
        if source.is_dir():
            target=portable.HOME/'plugins/freedom-preview';target.mkdir(parents=True,exist_ok=True)
            for name in ('__init__.py','plugin.yaml'):
                data=(source/name).read_bytes();file=target/name
                if not file.exists() or file.read_bytes()!=data:file.write_bytes(data)
            portable.write(target/'runtime.json',{'app_relative':__import__('os').path.relpath(root,target)})
        self.lock=asyncio.Lock();self.start_lock=asyncio.Lock();self.process=None;self.log=None
        self.reader=None;self.pending={};self.pending_processes={};self.latest={};self.activities={};self.notifications=set()
        self.sequences={};self.presentation_epoch=uuid.uuid4().hex
        path=root/'data/preview-control.json';saved=portable.read(path,{})
        self.key=saved.get('key') or secrets.token_urlsafe(40)
        portable.write(path,{'key':self.key,'url':f"http://127.0.0.1:{portable.config()['ui_port']}/preview-control"})

    @staticmethod
    def session(value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,140}',value):raise ValueError('Некорректный чат просмотра.')
        return value

    def target(self,value):
        value=str(value or '').strip()
        if value.lower().startswith('file:'):
            parsed=urlparse(value)
            if parsed.netloc not in {'','localhost'}:raise ValueError('Для просмотра выберите локальный HTML-файл проекта.')
            from urllib.request import url2pathname
            value=url2pathname(parsed.path)
        if re.match(r'^[A-Za-z]:[\\/]',value) or value.startswith('/'):
            p=pathlib.Path(value).resolve()
            if not p.is_relative_to(self.portable.workspace_root()) or not p.is_file() or p.suffix.lower() not in {'.html','.htm'}:raise ValueError('Выберите HTML-файл внутри папки проектов.')
            return p.as_uri()
        if re.match(r'^(javascript|data|vbscript|blob|about):',value,re.I):raise ValueError('Введите адрес http:// или https://.')
        if '://' not in value:value=('http://' if re.match(r'^(localhost|127\.0\.0\.1|\[::1\])(:|/|$)',value,re.I) else 'https://')+value
        parsed=urlparse(value)
        try:port=parsed.port
        except ValueError:raise ValueError('Укажите корректный порт сайта.') from None
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or any(char.isspace() for char in parsed.netloc):raise ValueError('Введите адрес http:// или https:// без логина и пароля в ссылке.')
        return value

    async def start(self):
        async with self.start_lock:await self._start()

    async def _start(self):
        if self.process and self.process.returncode is None and self.reader and not self.reader.done():return
        if self.process or self.reader:await self._stop()
        allowed={'PATH','SYSTEMROOT','WINDIR','COMSPEC','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PATHEXT','USERPROFILE','LOCALAPPDATA','APPDATA','HOMEDRIVE','HOMEPATH'}
        env={k:v for k,v in os.environ.items() if k.upper() in allowed}
        home=self.root/'.cache/preview-browser';home.mkdir(parents=True,exist_ok=True)
        # Keep Windows identity folders valid for Edge's OS services. Playwright's
        # isolated user-data-dir, temp files, disk cache and crash dumps stay on A:.
        env.update(TEMP=str(self.root/'.tmp'),TMP=str(self.root/'.tmp'),HOME=str(home))
        node=self.root/'runtime/node/node.exe'
        if not node.is_file():node=self.root/'runtime/node/bin/node'
        self.log=(self.root/'logs/preview-browser.log').open('ab')
        script=self.root/'scripts/preview-browser.mjs'
        if not script.is_file():script=self.root/'runtime/freedom/scripts/preview-browser.mjs'
        self.process=await asyncio.create_subprocess_exec(str(node),str(script),cwd=self.root,env=env,
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=self.log,
            creationflags=getattr(__import__('subprocess'),'CREATE_NO_WINDOW',0),limit=1024*1024)
        self.reader=asyncio.create_task(self.read_events(self.process))

    def presentation(self,sid,result):
        result=dict(result)
        self.sequences=getattr(self,'sequences',{})
        self.sequences[sid]=self.sequences.get(sid,0)+1
        result.update(sequence=self.sequences[sid],presentation_epoch=getattr(self,'presentation_epoch','legacy'))
        if result.get('revision'):result['frame']=f'/api/preview/{sid}/frame?v='+str(result['revision'])
        if result.get('screenshot_path'):result['screenshot_url']=f"/api/preview/{sid}/shots/"+pathlib.Path(result['screenshot_path']).name
        result['activity']=dict(self.activities.get(sid,{'active':False}))
        self.latest[sid]={key:value for key,value in result.items() if key not in {'snapshot','screenshot_path'}}
        return result

    async def read_events(self,process):
        try:
            while line:=await process.stdout.readline():
                result=json.loads(line)
                if result.get('event')=='preview.changed':
                    if process is not self.process:continue
                    sid=self.session(result.get('sid'));state=self.presentation(sid,result['result'])
                    if len(self.notifications)<32:
                        task=asyncio.create_task(self.bridge.broadcast({'type':'preview.changed','session_id':sid,'preview':state,
                            'open':bool(result.get('open') and self.activities.get(sid,{}).get('active'))}))
                        self.notifications.add(task);task.add_done_callback(self.notifications.discard)
                elif result.get('event')=='preview.closed':
                    if process is self.process:await self.worker_page_closed(self.session(result.get('sid')))
                else:
                    future=self.pending.get(result.get('id'))
                    if future and not future.done():future.set_result(result)
        except asyncio.CancelledError:raise
        except Exception as exc:
            log.warning('Preview worker stream stopped: %s',type(exc).__name__)
        finally:
            for identifier,future in list(self.pending.items()):
                owner=getattr(self,'pending_processes',{}).get(identifier,self.process)
                if owner is process and not future.done():future.set_exception(ValueError('Браузер просмотра остановился. Откройте страницу заново.'))
            if process is self.process:
                for sid in list(self.activities):await self.worker_page_closed(sid)

    async def worker_page_closed(self,sid):
        previous=self.latest.get(sid,{})
        self.latest[sid]={'state':'idle','url':previous.get('url',''),'title':previous.get('title',''),
                          'error':'Браузер просмотра остановился. Откройте страницу заново.'}
        await self.finish(sid)

    async def finish(self,sid):
        if not self.activities.get(sid,{}).get('active'):return
        self.activities[sid].update(active=False,finished_at=time.time())
        state=self.presentation(sid,self.latest.get(sid,{'state':'idle','url':'','title':''}))
        await self.bridge.broadcast({'type':'preview.finished','session_id':sid,'preview':state,
                                     'reason':'turn.complete'})

    async def call(self,sid,data):
        sid=self.session(sid);data=dict(data);action=data.get('action','status')
        if action=='open':data['url']=self.target(data.get('url'))
        if action=='adopt':data['from']=self.session(data.get('from'))
        if action=='viewport':
            data['width']=max(320,min(1920,int(data.get('width',1280))));data['height']=max(320,min(1200,int(data.get('height',800))))
        if action in {'click','fill'} and data.get('ref') and not re.fullmatch(r'p[0-9]{1,3}',str(data['ref'])):raise ValueError('Обновите снимок страницы перед выбором элемента.')
        if action=='click' and not data.get('ref'):
            data['x']=max(0,min(1920,float(data.get('x',0))));data['y']=max(0,min(1200,float(data.get('y',0))))
        if action in {'fill','type'}:data['text']=str(data.get('text',''))[:12000]
        if action=='scroll':data['dy']=max(-2000,min(2000,int(data.get('dy',500))))
        if action=='press':data['key']=str(data.get('key','Enter'))[:60]
        if action=='status' and (not self.process or self.process.returncode is not None):
            if self.activities.get(sid,{}).get('active'):await self.worker_page_closed(sid)
            return self.presentation(sid,self.latest.get(sid,{'state':'idle','url':'','title':''}))
        if action=='status' and self.pending and sid in self.latest:return self.presentation(sid,self.latest[sid])
        await self.start();identifier=uuid.uuid4().hex;future=asyncio.get_running_loop().create_future()
        self.pending[identifier]=future
        process=self.process;self.pending_processes[identifier]=process
        try:
            async with self.lock:
                process.stdin.write((json.dumps({**data,'sid':sid,'id':identifier})+'\n').encode());await process.stdin.drain()
            try:result=await asyncio.wait_for(future,45)
            except asyncio.TimeoutError:
                await self.stop();raise ValueError('Просмотр не ответил вовремя. Откройте страницу повторно.')
            if result.get('error'):raise ValueError(result['error'])
            if result['result'].get('state')=='idle' and self.activities.get(sid,{}).get('active'):await self.finish(sid)
            return self.presentation(sid,result['result'])
        finally:
            self.pending.pop(identifier,None);self.pending_processes.pop(identifier,None)

    async def status(self,request):return web.json_response(await self.call(request.match_info['sid'],{'action':'status'}))

    async def action(self,request):
        sid=request.match_info['sid'];data={**await request.json(),'source':'user'};result=await self.call(sid,data)
        if data.get('action') not in {'status','inspect'}:await self.bridge.broadcast({'type':'preview.changed','session_id':sid,'preview':result})
        return web.json_response(result)

    async def agent(self,request):
        if not secrets.compare_digest(request.headers.get('Authorization',''),'Bearer '+self.key):raise web.HTTPUnauthorized()
        sid=self.session(request.match_info['sid']);data={**await request.json(),'source':'agent'};action=data.get('action','status')
        if action not in {'status','close'}:
            await self.start()
            previous=self.activities.get(sid,{})
            self.activities[sid]={'active':True,'started_at':previous.get('started_at',time.time()) if previous.get('active') else time.time(),'action':action}
            initial=self.presentation(sid,self.latest.get(sid,{'state':'loading','url':data.get('url',''),'title':''}))
            await self.bridge.broadcast({'type':'preview.changed','session_id':sid,'preview':initial,'open':True})
        try:result=await self.call(sid,data)
        except Exception:
            await self.finish(sid);raise
        if action=='close':
            await self.finish(sid)
            result['activity']=dict(self.activities.get(sid,{'active':False}))
        await self.bridge.broadcast({'type':'preview.changed','session_id':sid,'preview':result,'open':action not in {'status','close'} and bool(self.activities.get(sid,{}).get('active'))})
        # Screenshots remain evidence for the agent; they do not fill the chat's generated-media gallery.
        return web.json_response(result)

    async def frame(self,request):
        sid=self.session(request.match_info['sid']);key=hashlib.sha256(sid.encode()).hexdigest()[:24]
        path=self.root/'.cache/preview-frames'/(key+'.jpg')
        if not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Type':'image/jpeg','Cache-Control':'no-store'})

    async def shot(self,request):
        sid=self.session(request.match_info['sid']);key=hashlib.sha256(sid.encode()).hexdigest()[:24]
        name=request.match_info['name']
        if not re.fullmatch('preview-'+key+r'-[0-9]+\.png',name):raise web.HTTPNotFound()
        path=self.root/'output/browser-preview'/name
        if not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Type':'image/png','Content-Disposition':'attachment; filename="FreedomGPT-preview.png"'})

    async def stop(self):
        async with self.start_lock:await self._stop()

    async def _stop(self):
        if self.process and self.process.returncode is None:
            self.process.stdin.close()
            with contextlib.suppress(asyncio.TimeoutError):await asyncio.wait_for(self.process.wait(),5)
            if self.process.returncode is None:self.process.kill();await self.process.wait()
        if self.reader:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.reader
            self.reader=None
        self.process=None
        tasks=list(self.notifications)
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        self.notifications.clear()
        if self.log:self.log.close();self.log=None

    def register(self,app):
        app.router.add_get('/api/preview/{sid}',self.status);app.router.add_post('/api/preview/{sid}',self.action)
        app.router.add_get('/api/preview/{sid}/frame',self.frame)
        app.router.add_get('/api/preview/{sid}/shots/{name}',self.shot)
        app.router.add_post('/preview-control/{sid}',self.agent)
