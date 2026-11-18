"""Installed Windows-only Freedom Arcade integration. No agent/model ownership changes."""
import asyncio, importlib.util, json, mimetypes, pathlib, re, subprocess, threading, time, sys
from aiohttp import web
ROOT=pathlib.Path(__file__).resolve().parent.parent/'game-stick-pc'
_instance=None
_lock=threading.Lock()
def library():
    global _instance
    with _lock:
        if _instance is None:
            if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
            spec=importlib.util.spec_from_file_location('freedom_arcade_backend',ROOT/'arcade_backend.py')
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            _instance=mod.Bridge()
    return _instance

def launch_desktop():
    python=pathlib.Path.home()/'AppData/Local/Programs/Python/Python312/pythonw.exe'
    if not python.is_file():raise ValueError('Не найден Python для отдельной библиотеки')
    subprocess.Popen([str(python),str(ROOT/'arcade.pyw')],cwd=ROOT)
    return {'ok':True}

async def call(request):
    data=await request.json();method=data.get('method');args=data.get('args',[])
    if not isinstance(args,list) or len(args)>3:return web.json_response({'error':'Некорректные аргументы'},status=400)
    allowed={'bootstrap','favorite','set_genre','library_state','freedom_status','open_freedom','workshop','play_own','create_game','respond_game','open_downloads','get_controls','save_controls','get_graphics','save_graphics'}
    b=await asyncio.to_thread(library)
    if method=='launch_desktop':result=await asyncio.to_thread(launch_desktop)
    elif method=='import_game':result={'ok':False,'error':'Для добавления файла нажмите «Отдельное приложение» в верхней панели.'}
    elif method=='play':
        if len(args)!=1 or args[0] not in b._index:return web.json_response({'error':'Игра не найдена'},status=404)
        g=b._index[args[0]]
        # Reuse atomic preference writing; do not launch a native emulator from embedded mode.
        def remember():
            with b._lock:
                b.library_state();b._state['recent'][g['id']]=time.time()
                mod_save=b.library_state.__globals__['save'];mod_save(ROOT/'data/library-state.json',b._state)
        await asyncio.to_thread(remember)
        result={'ok':True,'mode':'embedded','title':g['title'],'url':'/arcade/player.html?id='+g['id']}
    elif method in allowed:
        result=await asyncio.to_thread(getattr(b,method),*args)
    else:return web.json_response({'error':'Недоступная операция'},status=400)
    return web.json_response(result)

async def rom(request):
    identifier=request.match_info['id'];b=await asyncio.to_thread(library);g=b._index.get(identifier)
    if not g:raise web.HTTPNotFound()
    path=pathlib.Path(g['path']).resolve()
    if not path.is_relative_to((ROOT/'games').resolve()) or not path.is_file():raise web.HTTPNotFound()
    if request.query.get('info')=='1':
        core='nes' if g['platform']=='nes' else 'segaGG' if g['platform']=='gg' else 'segaMD'
        import controls
        return web.json_response({'title':g['title'],'core':core,'url':'/arcade/rom/'+identifier+'/'+path.name,'name':path.name,'controls':controls.browser(ROOT,g['platform']),'graphics':b.get_graphics()})
    return web.FileResponse(path,headers={'Content-Type':'application/octet-stream','X-Content-Type-Options':'nosniff'})

async def static(request):
    suffix=request.match_info.get('path','') or 'index.html'
    if suffix.startswith('assets/'):base=ROOT/'assets';relative=suffix[7:]
    elif suffix.startswith('emulator/'):base=ROOT/'vendor/emulatorjs/data';relative=suffix[9:]
    else:base=ROOT/'ui';relative=suffix
    path=(base/relative).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():raise web.HTTPNotFound()
    # Never expose development preview/test data.
    if path.name=='preview-data.json':raise web.HTTPNotFound()
    response=web.FileResponse(path)
    if path.suffix=='.html':response.content_type='text/html'
    return response

def register(app):
    if not (ROOT/'arcade_backend.py').is_file():return
    app.router.add_post('/api/arcade/call',call)
    app.router.add_get('/arcade/rom/{id}',rom)
    app.router.add_get('/arcade/rom/{id}/{filename}',rom)
    app.router.add_get('/arcade/',static)
    app.router.add_get('/arcade/{path:.*}',static)
