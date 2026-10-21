"""A loopback-only shared browser surface for the user and the local agent."""
import asyncio
import contextlib
import hashlib
import json
import os
import pathlib
import re
import secrets
import shutil
import uuid
from urllib.parse import urlparse

from aiohttp import web


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
        self.lock=asyncio.Lock();self.process=None;self.log=None
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
        if re.match(r'^[A-Za-z]:[\\/]',value):
            p=pathlib.Path(value).resolve()
            if not p.is_relative_to(self.portable.workspace_root()) or not p.is_file() or p.suffix.lower() not in {'.html','.htm'}:raise ValueError('Выберите HTML-файл внутри папки проектов.')
            return p.as_uri()
        if '://' not in value:value=('http://' if re.match(r'^(localhost|127\.0\.0\.1|\[::1\])(:|/|$)',value) else 'https://')+value
        parsed=urlparse(value)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Введите адрес http:// или https:// без логина и пароля в ссылке.')
        return value

    async def start(self):
        if self.process and self.process.returncode is None:return
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
        async with self.lock:
            if action=='status' and (not self.process or self.process.returncode is not None):return {'state':'idle','url':'','title':''}
            await self.start();identifier=uuid.uuid4().hex
            self.process.stdin.write((json.dumps({**data,'sid':sid,'id':identifier})+'\n').encode());await self.process.stdin.drain()
            try:line=await asyncio.wait_for(self.process.stdout.readline(),45)
            except asyncio.TimeoutError:
                await self.stop();raise ValueError('Просмотр не ответил вовремя. Откройте страницу повторно.')
            if not line:raise ValueError('Браузер просмотра остановился. Откройте страницу заново.')
            result=json.loads(line)
            if result.get('id')!=identifier:raise ValueError('Соединение просмотра обновилось. Повторите действие.')
            if result.get('error'):raise ValueError(result['error'])
            result=result['result']
            if result.get('revision'):result['frame']=f'/api/preview/{sid}/frame?v='+str(result['revision'])
            if result.get('screenshot_path'):result['screenshot_url']=f"/api/preview/{sid}/shots/"+pathlib.Path(result['screenshot_path']).name
            return result

    async def status(self,request):return web.json_response(await self.call(request.match_info['sid'],{'action':'status'}))

    async def action(self,request):
        sid=request.match_info['sid'];data=await request.json();result=await self.call(sid,data)
        if data.get('action') not in {'status','inspect'}:await self.bridge.broadcast({'type':'preview.changed','session_id':sid,'preview':result})
        return web.json_response(result)

    async def agent(self,request):
        if not secrets.compare_digest(request.headers.get('Authorization',''),'Bearer '+self.key):raise web.HTTPUnauthorized()
        sid=request.match_info['sid'];data=await request.json();result=await self.call(sid,data)
        await self.bridge.broadcast({'type':'preview.changed','session_id':sid,'preview':result,'open':True})
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
        if self.process and self.process.returncode is None:
            self.process.stdin.close()
            with contextlib.suppress(asyncio.TimeoutError):await asyncio.wait_for(self.process.wait(),5)
            if self.process.returncode is None:self.process.kill();await self.process.wait()
        self.process=None
        if self.log:self.log.close();self.log=None

    def register(self,app):
        app.router.add_get('/api/preview/{sid}',self.status);app.router.add_post('/api/preview/{sid}',self.action)
        app.router.add_get('/api/preview/{sid}/frame',self.frame)
        app.router.add_get('/api/preview/{sid}/shots/{name}',self.shot)
        app.router.add_post('/preview-control/{sid}',self.agent)
