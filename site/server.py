"""Local release website. No upload, external listener or publication action."""
import json,os,pathlib
from aiohttp import web
ROOT=pathlib.Path(__file__).resolve().parent;PROJECT=ROOT.parent;PORT=int(os.environ.get('FREEDOM_SITE_PORT','17900'))
def load(path,default):
 try:return json.loads(path.read_text(encoding='utf8'))
 except (OSError,ValueError):return default
@web.middleware
async def headers(request,handler):
 if request.host not in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}:return web.json_response({'error':'Local host only'},status=403)
 response=await handler(request)
 response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','Cache-Control':'no-cache',
  'Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"})
 return response
async def index(request):return web.FileResponse(ROOT/('en.html' if request.path.startswith('/en') else 'index.html'),headers={'Content-Type':'text/html; charset=utf-8'})
async def release(request):
 value=load(PROJECT/'release/release.json',None) or load(ROOT/'release.json',None)
 return web.json_response(value or {'error':'Установщик ещё собирается'},status=200 if value else 503)
async def catalog(request):return web.json_response(load(PROJECT/'app/catalog.json',[]))
async def models(request):return web.json_response({'models':[]})
async def download(request):
 name=request.match_info['name'];manifest=load(PROJECT/'release/release.json',{})
 allowed={f['name'] for f in manifest.get('files',[])}|{'SHA256SUMS.txt','FreedomGPT-source-1.1.0.zip'}
 if name not in allowed:return web.Response(status=404)
 file=PROJECT/'release'/name
 if not file.is_file():return web.Response(status=404)
 return web.FileResponse(file,headers={'Content-Type':'application/octet-stream','Content-Disposition':'attachment; filename="'+name+'"'})
def create_app():
 app=web.Application(middlewares=[headers]);app.router.add_get('/',index);app.router.add_get('/en/',index);app.router.add_get('/api/release',release);app.router.add_get('/api/catalog',catalog);app.router.add_get('/downloads/{name}',download)
 app.router.add_get('/api/models',models)
 for name in ['style.css','app.js','freedom.svg']:app.router.add_get('/'+name,lambda request,n=name:web.FileResponse(ROOT/n))
 app.router.add_static('/fonts/',ROOT/'fonts');app.router.add_static('/media/',PROJECT/'assets');return app
if __name__=='__main__':web.run_app(create_app(),host='127.0.0.1',port=PORT,access_log=None)
