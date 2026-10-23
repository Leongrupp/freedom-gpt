"""Local account settings and agent broker; no compulsory login or external writes on startup."""
import asyncio,contextlib,datetime,io,os,pathlib,secrets,shutil
from aiohttp import web
from github_access import access as github
from hf_access import access as huggingface
from cloud_vault import account_options

class AccountConnections:
    def __init__(self,root,portable):
        self.root,self.portable=root,portable
        path=root/'data/accounts-control.json';old=portable.read(path,{})
        self.key=old.get('key') or secrets.token_urlsafe(40)
        portable.write(path,{'key':self.key,'url':f"http://127.0.0.1:{portable.config()['ui_port']}/accounts-control/github"})
        self.install_plugin()

    def install_plugin(self):
        name='freedom-accounts';source=self.root/'agent_plugins'/name;target=self.portable.HOME/'plugins'/name
        if not source.is_dir():source=self.root/'runtime/freedom/agent_plugins'/name
        target.mkdir(parents=True,exist_ok=True)
        for filename in ('__init__.py','plugin.yaml'):
            data=(source/filename).read_bytes();path=target/filename
            if not path.exists() or path.read_bytes()!=data:path.write_bytes(data)
        self.portable.write(target/'runtime.json',{'app_relative':os.path.relpath(self.root,target)})
        path=self.portable.HOME/'config.yaml'
        if not path.is_file():return
        from ruamel.yaml import YAML
        yaml=YAML();yaml.preserve_quotes=True;data=yaml.load(path.read_text(encoding='utf-8'))
        enabled=data.setdefault('plugins',{}).setdefault('enabled',[])
        if name in enabled:return
        backup=self.root/'archive/accounts-20261021'
        backup.mkdir(exist_ok=True,parents=True)
        if not (backup/'agent-config-before.yaml').exists():shutil.copy2(path,backup/'agent-config-before.yaml')
        enabled.append(name);out=io.StringIO();yaml.dump(data,out)
        temporary=path.with_name('config.freedom-accounts.new');temporary.write_text(out.getvalue(),encoding='utf-8');os.replace(temporary,path)

    def snapshot(self):
        return {'github':github.status(),'huggingface':huggingface.status(),'optional':True}

    def register(self,app):
        async def status(request):return web.json_response(self.snapshot())
        async def connect(request):
            data=await request.json();options=account_options(data,write_access=True,token_required=True)
            result=await asyncio.to_thread(github.check,data['token'],**options)
            return web.json_response(result)
        async def cli(request):
            data=await request.json();options=account_options(data,write_access=True)
            return web.json_response(await asyncio.to_thread(github.use_cli,**options))
        async def check(request):return web.json_response(await asyncio.to_thread(github.check))
        async def disconnect(request):return web.json_response(github.disconnect())
        async def settings(request):
            data=await request.json();account_options(data,write_access=True)
            return web.json_response(github.settings(data.get('allow_write')))
        async def agent(request):
            supplied=request.headers.get('Authorization','')
            if not secrets.compare_digest(supplied,'Bearer '+self.key):raise web.HTTPForbidden()
            return web.json_response(await asyncio.to_thread(github.operate,await request.json()))
        app.router.add_get('/api/accounts',status)
        for name,handler in [('connect',connect),('cli',cli),('check',check),('disconnect',disconnect),('settings',settings)]:app.router.add_post('/api/accounts/github/'+name,handler)
        app.router.add_post('/accounts-control/github',agent)
