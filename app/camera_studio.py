"""Owner-only Windows camera studio. Raw camera frames are never an output fallback."""
from __future__ import annotations
import asyncio,base64,contextlib,hashlib,io,json,math,os,pathlib,secrets,socket,struct,subprocess,sys,time,uuid
from aiohttp import web,ClientSession,ClientTimeout,ClientError,ClientConnectorError
from PIL import Image,ImageDraw,ImageOps
import psutil
from bootstrap import ROOT,STACK,PRIVATE,read,write,model_url
from platform_support import PROCESS_FLAGS

BASE=ROOT/'camera-studio'
MAX_IMAGE=2*1024*1024

def decode_image(value,limit=MAX_IMAGE):
    if not isinstance(value,str) or len(value)>limit*1.4+100:raise ValueError('Изображение слишком большое.')
    raw=base64.b64decode(value.split(',',1)[-1],validate=True)
    if len(raw)>limit:raise ValueError('Изображение слишком большое.')
    with Image.open(io.BytesIO(raw)) as image:
        if image.width*image.height>4096*4096:raise ValueError('Изображение слишком большое.')
        image.verify()
    return raw

def jpeg(raw):
    with Image.open(io.BytesIO(raw)) as image:
        image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1280,720))
        output=io.BytesIO();image.save(output,'JPEG',quality=88)
    return output.getvalue()

def vrm_metadata(raw):
    if len(raw)<24 or len(raw)>50*1024**2:raise ValueError('Выберите VRM до 50 МБ.')
    magic,version,total=struct.unpack_from('<4sII',raw)
    length,kind=struct.unpack_from('<II',raw,12)
    if magic!=b'glTF' or version!=2 or total!=len(raw) or kind!=0x4e4f534a or length>4*1024**2:raise ValueError('Некорректный файл VRM.')
    data=json.loads(raw[20:20+length])
    for section in ('buffers','images'):
        for item in data.get(section,[]):
            if item.get('uri') and not str(item['uri']).startswith('data:'):raise ValueError('VRM должен содержать все ресурсы внутри файла.')
    extensions=data.get('extensions',{})
    meta=extensions.get('VRMC_vrm',{}).get('meta') or extensions.get('VRM',{}).get('meta')
    if not isinstance(meta,dict):raise ValueError('В файле нет метаданных VRM.')
    return meta

class CameraStudio:
    def __init__(self,bridge):
        self.bridge=bridge;self.supported=os.name=='nt' and bool(PRIVATE)
        self.config_path=BASE/'data/settings.json';self.config=read(self.config_path,{})
        if self.supported and not self.config.get('output_key'):
            self.config['output_key']=secrets.token_urlsafe(32);write(self.config_path,self.config)
        self.state='stopped';self.mode='avatar';self.input='pc';self.style='swap';self.error=None
        self.session=None;self.started=0;self.last_input=0;self.last_output=0;self.output_frame=None;self.sequence=-1
        self.process=None;self.worker_port=None;self.worker_key=None;self.lease=None;self.start_task=None;self.worker_job=None;self.worker_device=None
        self.http=None;self.watch_task=None;self.app=None;self.frame_lock=asyncio.Lock();self.control_lock=asyncio.Lock()
        self.room=None;self.timings=[];self.generation=0
        image=Image.new('RGB',(1280,720),'#111318');draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((530,245,750,465),radius=55,fill='#24232f',outline='#a895ee',width=2)
        draw.text((607,326),'F.',fill='#bba7f1',font_size=64)
        draw.text((560,510),'Freedom Avatar',fill='#b2b4bf',font_size=21)
        draw.text((536,550),'Protected video output',fill='#777b8c',font_size=17)
        data=io.BytesIO();image.save(data,'JPEG',quality=88);self.placeholder=data.getvalue()

    def require(self):
        if not self.supported:raise web.HTTPNotFound()

    def current_output(self):
        return self.output_frame if self.state=='running' and self.last_output>time.monotonic()-1.5 else self.placeholder

    def asset_ready(self):
        manifest=read(BASE/'manifest.json',{})
        return bool(manifest.get('assets')) and all((BASE/item['path']).is_file() and (BASE/item['path']).stat().st_size==item['bytes'] for item in manifest.get('assets',[]))

    def status_data(self):
        origin=f"http://127.0.0.1:{self.app['camera_port']}" if self.app else ''
        output_url=origin+'/camera-output/'+self.config.get('output_key','')
        remote=self.app.get('phone_access') if self.app else None
        remote_state=remote.status() if remote else {}
        legacy=read(ROOT/'data/phone/settings.json',{})
        legacy_ready=legacy.get('enabled') and legacy.get('fingerprint') and legacy.get('public_url')
        public=legacy['public_url']+'/' if legacy_ready else remote_state.get('public_url') or origin+'/'
        phone_url=public.split('?',1)[0]+'?camera_phone='+self.room['id'] if self.room else None
        avatar=read(BASE/'models/avatar-license.json',{}).get('meta',{})
        stats=self.timings[-30:];fps=(len(stats)-1)/(stats[-1]-stats[0]) if len(stats)>1 and stats[-1]>stats[0] else 0
        return {'supported':self.supported,'state':self.state,'mode':self.mode,'input':self.input,'style':self.style,
                'session':self.session,'error':self.error,'ready':self.asset_ready(),'photo_ready':(BASE/'runtime/ready.json').is_file(),'fps':round(fps,1),
                'protected':self.current_output() is self.placeholder,'output_url':output_url,
                'phone_url':phone_url,'phone_remote_ready':bool(legacy_ready or remote_state.get('state')=='connected'),
                'portrait':bool(self.config.get('portrait')),'avatar_name':self.config.get('avatar_name') or avatar.get('name','VRM Sample'),
                'portrait_updated':self.config.get('portrait_updated',0),'avatar_revision':self.config.get('avatar','models/default.vrm'),'custom_avatar':bool(self.config.get('avatar')),
                'avatar_meta':self.config.get('avatar_meta') or avatar,'obs_found':bool(self.obs_executable()),
                'local_only':True,'photoreal_engine':'LivePortrait · MIT','worker_device':self.worker_device,'tracking_engine':'MediaPipe · Apache-2.0'}

    async def status(self,request):
        self.require();return web.json_response(self.status_data())

    async def load(self,app):
        self.app=app;self.http=ClientSession(timeout=ClientTimeout(total=20))
        if self.supported:self.watch_task=asyncio.create_task(self.watch())

    async def close(self,app):
        if self.watch_task:self.watch_task.cancel();await asyncio.gather(self.watch_task,return_exceptions=True)
        await self.stop_internal()
        if self.http:await self.http.close()

    async def watch(self):
        while True:
            await asyncio.sleep(1)
            if self.process and self.process.poll() is not None:
                self.error='Видеомодуль завершился. Выход защищён заглушкой.';await self.stop_internal(keep_error=True)
            if self.state=='running' and ((self.last_input and time.monotonic()-self.last_input>20) or (not self.last_input and time.monotonic()-self.started>180)):
                await self.stop_internal()
            if self.state=='running' and self.input=='phone' and self.room and self.room.get('phone_seen') and time.monotonic()-self.room['phone_seen']>20:
                self.error='Связь с камерой телефона потеряна. Подключите её заново через новый QR-код.'
                await self.stop_internal(keep_error=True)
            if self.lease:
                from gpu_lease import write as lease_write
                self.lease['expires']=time.time()+90;lease_write(self.lease)

    async def start(self,request):
        self.require();data=await request.json()
        if data.get('mode') not in {'avatar','photo'} or data.get('input') not in {'pc','phone'}:raise ValueError('Выберите режим и источник камеры.')
        if data.get('style','swap') not in {'swap','portrait'}:raise ValueError('Выберите вид фоторежима.')
        async with self.control_lock:
            if self.state in {'starting','running'}:raise ValueError('Сначала остановите текущий видеорежим.')
            if not self.asset_ready():raise ValueError('Модели видеорежима ещё устанавливаются.')
            if data['mode']=='photo' and not self.config.get('portrait'):raise ValueError('Сначала выберите фотографию персонажа.')
            if data['mode']=='photo':
                if not (BASE/'runtime/ready.json').is_file():raise ValueError('Компоненты фоторежима ещё устанавливаются.')
                if self.app.get('performance_busy') or self.app.get('prompt_admissions') or any(s.get('running') or s.get('pending') for s in self.bridge.snapshots.values()):
                    raise ValueError('Дождитесь завершения задач агента перед включением фоторежима.')
                # A goal can be between two turns while its model slot is idle.
                # Do not take its GPU until the owner has paused the goal.
                try:
                    controls=await asyncio.wait_for(asyncio.gather(*(self.bridge.rpc('session.control.read',session_id=sid) for sid in tuple(self.bridge.snapshots))),6)
                except (asyncio.TimeoutError,RuntimeError):raise ValueError('Не удалось проверить задачи агента. Повторите включение камеры после восстановления связи.')
                if any(((value.get('control') or {}).get('goal') or {}).get('status')=='active' for value in controls):
                    raise ValueError('Поставьте активную цель агента на паузу перед включением фоторежима.')
                if any(s.get('running') or s.get('pending') for s in self.bridge.snapshots.values()):raise ValueError('Агент начал задание. Дождитесь его завершения.')
                from managed_models import idle
                await asyncio.to_thread(idle)
            self.mode=data['mode'];self.input=data['input'];self.style=data.get('style','swap');self.session=uuid.uuid4().hex
            self.generation+=1;self.error=None;self.output_frame=None;self.last_input=0;self.last_output=0;self.sequence=-1;self.timings=[];self.started=time.monotonic()
            self.room={'id':secrets.token_urlsafe(24),'offer':None,'answer':None,'created':time.monotonic()} if self.input=='phone' else None
            self.state='starting' if self.mode=='photo' else 'running'
            if self.mode=='photo':self.start_task=asyncio.create_task(self.start_worker(self.generation))
            return web.json_response(self.status_data())

    async def start_worker(self,generation):
        try:
            python=BASE/'runtime/Scripts/python.exe'
            if not python.is_file():raise ValueError('Изолированная среда фоторежима ещё устанавливается.')
            from gpu_lease import acquire,stamp,write as lease_write
            from managed_models import owned_supervisor
            supervisor=owned_supervisor()
            if not supervisor:raise ValueError('Не подтверждён процесс локальной модели. Перезапустите Freedom перед включением фоторежима.')
            owners=[]
            for child in supervisor.children():
                try:
                    if child.name().lower()=='llama-server.exe' and pathlib.Path(child.exe()).resolve().is_relative_to((STACK/'engine').resolve()):owners.append(child)
                except psutil.Error:pass
            if not owners:raise ValueError('Локальная модель ещё загружается. Повторите включение после её готовности.')
            self.lease=acquire()
            # Confirm release of the owned CUDA process itself. On Windows a
            # cancelled health connection can time out after the listener exits.
            for _ in range(120):
                if not any(process.is_running() for process in owners):break
                await asyncio.sleep(.25)
            else:raise ValueError('Не удалось освободить видеокарту. Фоторежим не запущен; модель агента сохранена.')
            with socket.socket() as port:port.bind(('127.0.0.1',0));self.worker_port=port.getsockname()[1]
            self.worker_key=secrets.token_urlsafe(32)
            env=os.environ.copy();env.update(CAMERA_WORKER_KEY=self.worker_key,TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),PYTHONPATH=str(BASE/'vendor/LivePortrait'),PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1')
            from camera_job import WorkerJob,CREATE_SUSPENDED
            self.worker_job=WorkerJob()
            with (ROOT/'logs/camera-worker.log').open('ab') as log:
                self.process=subprocess.Popen([str(python),'-B',str(BASE/'worker.py'),'--port',str(self.worker_port),'--portrait',str(BASE/self.config['portrait'])],cwd=BASE,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=PROCESS_FLAGS|CREATE_SUSPENDED)
            self.worker_job.assign_and_resume(self.process)
            self.lease['processes']=[{'pid':self.process.pid,'stamp':stamp(self.process.pid)}];lease_write(self.lease)
            for _ in range(240):
                if generation!=self.generation:return
                if self.process.poll() is not None:raise ValueError('Не удалось загрузить фоторежим. См. журнал видеомодуля.')
                try:
                    async with self.http.get(self.worker_url('/health'),headers=self.worker_headers(),timeout=ClientTimeout(total=1)) as response:
                        if response.status==200:self.worker_device=(await response.json()).get('device');self.state='running';return
                except (ClientError,OSError,asyncio.TimeoutError):pass
                await asyncio.sleep(.5)
            raise ValueError('Загрузка фоторежима превысила время ожидания.')
        except asyncio.CancelledError:raise
        except Exception as exc:
            self.error=str(exc);await self.stop_internal(keep_error=True,from_start=True)

    def worker_url(self,path):return f'http://127.0.0.1:{self.worker_port}'+path
    def worker_headers(self):return {'X-Camera-Worker':self.worker_key or ''}

    async def stop_internal(self,keep_error=False,from_start=False):
        self.generation+=1;self.state='stopped';self.output_frame=None;self.last_output=0;self.room=None
        if self.start_task and not from_start:
            self.start_task.cancel();await asyncio.gather(self.start_task,return_exceptions=True)
        self.start_task=None
        if self.worker_job:self.worker_job.close();self.worker_job=None
        self.worker_device=None
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:await asyncio.to_thread(self.process.wait,10)
                except subprocess.TimeoutExpired:self.process.kill();await asyncio.to_thread(self.process.wait,5)
            self.process=None
        if self.lease:
            from gpu_lease import release
            release(self.lease);self.lease=None
        if not keep_error:self.error=None

    async def stop(self,request):
        self.require()
        async with self.control_lock:await self.stop_internal()
        return web.json_response(self.status_data())

    async def frame(self,request):
        self.require()
        if request.content_length and request.content_length>3*1024**2:raise web.HTTPRequestEntityTooLarge(max_size=3*1024**2,actual_size=request.content_length)
        data=await request.json()
        if self.state!='running' or data.get('session')!=self.session:return web.json_response({'error':self.error or 'Видеосеанс остановлен. Включите камеру снова.'},status=409)
        sequence=data.get('sequence')
        if type(sequence) is not int or sequence<=self.sequence:return web.json_response({'accepted':False})
        if self.frame_lock.locked():return web.json_response({'accepted':False,'busy':True})
        async with self.frame_lock:
            generation=self.generation;self.last_input=time.monotonic();self.sequence=sequence
            if self.input=='phone' and (not self.room or time.monotonic()-self.room.get('phone_seen',0)>4):
                self.output_frame=None;self.last_output=0;return web.json_response({'accepted':True,'protected':True})
            if data.get('faces')!=1:
                self.output_frame=None;self.last_output=0;return web.json_response({'accepted':True,'protected':True})
            raw=await asyncio.to_thread(decode_image,data.get('image'))
            if self.mode=='avatar':
                if data.get('rendered')!='vrm':raise ValueError('Разрешён только отрисованный аватар.')
                result=await asyncio.to_thread(jpeg,raw)
            else:
                crop=data.get('crop')
                if not isinstance(crop,dict) or set(crop)!={'cx','cy','size','angle'} or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in crop.values()):raise ValueError('Не найдена область лица.')
                async with self.http.post(self.worker_url('/frame'),json={'image':base64.b64encode(raw).decode(),'crop':crop,'style':self.style},headers=self.worker_headers(),timeout=ClientTimeout(total=8)) as response:
                    if response.status!=200:self.output_frame=None;self.last_output=0;raise ValueError('Видеомодуль не обработал кадр. Выход закрыт заглушкой.')
                    result=await response.read()
            if generation!=self.generation:return web.json_response({'accepted':False})
            self.output_frame=result;self.last_output=time.monotonic();self.timings.append(self.last_output);self.timings=self.timings[-60:]
            return web.json_response({'accepted':True,'protected':False})

    async def portrait(self,request):
        self.require()
        if self.state!='stopped':raise ValueError('Остановите камеру перед сменой персонажа.')
        data=await request.json();raw=await asyncio.to_thread(decode_image,data.get('image'),8*1024**2)
        with Image.open(io.BytesIO(raw)) as image:
            image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1024,1024));folder=BASE/'data/portraits';folder.mkdir(parents=True,exist_ok=True)
            path=folder/(uuid.uuid4().hex+'.png');image.save(path,'PNG')
        self.config['portrait']=str(path.relative_to(BASE));self.config['portrait_updated']=time.time();write(self.config_path,self.config)
        return web.json_response({'ok':True})

    async def avatar(self,request):
        self.require()
        if self.state!='stopped':raise ValueError('Остановите камеру перед сменой персонажа.')
        if request.content_type=='application/json':
            if (await request.json()).get('action')!='default':raise ValueError('Неизвестное действие.')
            for key in ['avatar','avatar_name','avatar_meta']:self.config.pop(key,None)
            write(self.config_path,self.config);return web.json_response({'ok':True})
        raw=await request.read();meta=await asyncio.to_thread(vrm_metadata,raw)
        folder=BASE/'data/avatars';folder.mkdir(parents=True,exist_ok=True);path=folder/(uuid.uuid4().hex+'.vrm');path.write_bytes(raw)
        self.config.update(avatar=str(path.relative_to(BASE)),avatar_name=str(meta.get('name') or meta.get('title') or 'Мой аватар')[:100],avatar_meta=meta);write(self.config_path,self.config)
        return web.json_response({'ok':True,'meta':meta})

    async def asset(self,request):
        self.require();name=request.match_info['name']
        known={'face_landmarker.task':BASE/'models/face_landmarker.task','avatar.vrm':BASE/self.config.get('avatar','models/default.vrm'),
               'portrait.png':BASE/self.config.get('portrait','models/not-selected.png'),'output.js':ROOT/'src/camera/output.js'}
        wasm=BASE/'web/node_modules/@mediapipe/tasks-vision/wasm'
        for path in wasm.glob('*'):
            if path.is_file() and path.suffix in {'.js','.wasm'}:known[path.name]=path
        if name not in known or not known[name].is_file():raise web.HTTPNotFound()
        response=web.FileResponse(known[name]);response.headers['Cache-Control']='private, max-age=3600' if name.endswith(('.wasm','.task')) else 'no-store'
        if name.endswith('.wasm'):response.content_type='application/wasm'
        return response

    async def output(self,request):
        self.require()
        if not secrets.compare_digest(str(request.query.get('key','')),self.config.get('output_key','')):raise web.HTTPForbidden()
        return web.Response(body=self.current_output(),content_type='image/jpeg',headers={'Cache-Control':'no-store'})

    async def output_page(self,request):
        self.require()
        if not secrets.compare_digest(request.match_info['key'],self.config.get('output_key','')):raise web.HTTPForbidden()
        return web.Response(text='<!doctype html><html><head><meta charset="utf-8"><title>Freedom Avatar · OBS</title><link rel="icon" href="/freedom.svg"></head><body style="margin:0;background:#111318;overflow:hidden"><img id="output" alt="Freedom Avatar" style="display:block;width:100vw;height:100vh;object-fit:contain"><script type="module" src="/api/camera/assets/output.js"></script></body></html>',content_type='text/html')

    async def signal(self,request):
        self.require();data=await request.json()
        if not self.room or data.get('room')!=self.room['id']:return web.json_response({'error':'Подключение камеры истекло. Создайте новое на ПК.'},status=410)
        role=data.get('role');action=data.get('action')
        if role not in {'host','phone'}:raise ValueError('Некорректный участник.')
        if role=='phone' and action=='stop':
            async with self.control_lock:await self.stop_internal()
            return web.json_response({'ok':True})
        if role=='phone':self.room['phone_seen']=time.monotonic()
        if action=='offer' and role=='host':
            sdp=data.get('sdp')
            if not isinstance(sdp,str) or len(sdp)>128*1024:raise ValueError('Некорректное описание соединения.')
            self.room['offer']={'type':'offer','sdp':sdp};self.room['answer']=None
        elif action=='answer' and role=='phone':
            sdp=data.get('sdp')
            if not isinstance(sdp,str) or len(sdp)>128*1024:raise ValueError('Некорректное описание соединения.')
            self.room['answer']={'type':'answer','sdp':sdp}
        elif action not in {'poll','heartbeat'}:raise ValueError('Некорректное действие.')
        return web.json_response({'room':self.room['id'],'offer':self.room['offer'] if role=='phone' else None,'answer':self.room['answer'] if role=='host' else None})

    async def phone_qr(self,request):
        self.require()
        if not self.room:raise web.HTTPGone()
        import qrcode,qrcode.image.svg
        output=io.BytesIO();qrcode.make(self.status_data()['phone_url'],image_factory=qrcode.image.svg.SvgPathImage).save(output)
        return web.Response(body=output.getvalue(),content_type='image/svg+xml')

    def obs_executable(self):
        paths=[pathlib.Path(os.environ.get('ProgramFiles','C:/Program Files'))/'obs-studio/bin/64bit/obs64.exe',BASE/'obs/bin/64bit/obs64.exe']
        return next((path for path in paths if path.is_file()),None)

    async def obs(self,request):
        self.require();folder=BASE/'exports';folder.mkdir(parents=True,exist_ok=True)
        source_id=str(uuid.uuid4());scene_id=str(uuid.uuid4());name='Freedom Avatar'
        source={'uuid':source_id,'name':'Freedom Avatar · Protected Output','id':'browser_source','versioned_id':'browser_source','settings':{'url':self.status_data()['output_url'],'width':1280,'height':720,'fps':30,'fps_custom':True,'shutdown':False,'restart_when_active':True},'mixers':0,'volume':0.0,'enabled':True}
        scene={'uuid':scene_id,'name':name,'id':'scene','versioned_id':'scene','settings':{'items':[{'name':source['name'],'source_uuid':source_id,'visible':True,'locked':True,'rot':0.0,'pos':{'x':0.0,'y':0.0},'scale':{'x':1.0,'y':1.0},'align':5,'bounds_type':0,'bounds_align':0,'bounds':{'x':0.0,'y':0.0},'crop_left':0,'crop_top':0,'crop_right':0,'crop_bottom':0,'id':1}],'id_counter':1}}
        path=folder/'Freedom-Avatar-OBS.json';write(path,{'name':name,'current_scene':name,'current_program_scene':name,'scene_order':[{'name':name}],'sources':[source,scene],'groups':[],'modules':{},'transition_duration':300,'transitions':[],'current_transition':'Fade','quick_transitions':[]})
        return web.json_response({'ok':True,'path':str(path),'url':self.status_data()['output_url'],'download':'/api/camera/obs-scene'})

    async def obs_scene(self,request):
        self.require();path=BASE/'exports/Freedom-Avatar-OBS.json'
        if not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Disposition':'attachment; filename="Freedom-Avatar-OBS.json"'})

    async def obs_open(self,request):
        self.require()
        if not (BASE/'exports/Freedom-Avatar-OBS.json').is_file():await self.obs(request)
        from camera_obs import launch
        return web.json_response(await asyncio.to_thread(launch,BASE/'exports/Freedom-Avatar-OBS.json'))

    def register(self,app,port):
        if not self.supported:return
        app['camera_port']=port;app.on_startup.append(self.load);app.on_cleanup.append(self.close)
        app.router.add_get('/api/camera/status',self.status);app.router.add_post('/api/camera/start',self.start);app.router.add_post('/api/camera/stop',self.stop)
        app.router.add_post('/api/camera/frame',self.frame);app.router.add_post('/api/camera/portrait',self.portrait);app.router.add_post('/api/camera/avatar',self.avatar)
        app.router.add_get('/api/camera/assets/{name}',self.asset);app.router.add_get('/api/camera/output.jpg',self.output);app.router.add_get('/camera-output/{key}',self.output_page)
        app.router.add_post('/api/camera/signal',self.signal);app.router.add_get('/api/camera/phone-qr.svg',self.phone_qr)
        app.router.add_post('/api/camera/obs',self.obs);app.router.add_get('/api/camera/obs-scene',self.obs_scene);app.router.add_post('/api/camera/obs/open',self.obs_open)
