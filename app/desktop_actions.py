"""Explicit desktop actions from the local UI, never shell commands from URLs."""
import asyncio,os,pathlib,subprocess,sys
from urllib.parse import urlsplit
from aiohttp import web

def checked_url(value):
    value=str(value or '').strip()
    if any(ord(c)<32 for c in value):raise ValueError('Некорректная ссылка.')
    parsed=urlsplit(value)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Можно открыть только ссылку http:// или https:// без пароля.')
    return value

def default_browser(url):
    if sys.platform=='win32':os.startfile(url)
    else:subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def reveal_file(path):
    if sys.platform=='win32':subprocess.Popen(['explorer.exe','/select,',str(path)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    elif sys.platform=='darwin':subprocess.Popen(['open','-R',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:subprocess.Popen(['xdg-open',str(path.parent)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

class DesktopActions:
    def __init__(self,artifacts):self.artifacts=artifacts

    async def reveal(self,request):
        if request.path.startswith('/api/files/'):
            with self.artifacts.db() as conn:row=conn.execute('SELECT * FROM files WHERE id=?',(request.match_info['fid'],)).fetchone()
            if not row:raise web.HTTPNotFound(text='Файл не найден.')
        else:row=self.artifacts.row(request.match_info['fid'])
        path=self.artifacts.path(row['path'])
        await asyncio.to_thread(reveal_file,path)
        return web.json_response({'opened':True})

    async def external(self,request):
        url=checked_url((await request.json()).get('url'))
        await asyncio.to_thread(default_browser,url)
        return web.json_response({'opened':True})

    def register(self,app):
        app.router.add_post('/api/artifacts/{fid}/reveal',self.reveal)
        app.router.add_post('/api/files/{fid}/reveal',self.reveal)
        app.router.add_post('/api/desktop/open-url',self.external)
