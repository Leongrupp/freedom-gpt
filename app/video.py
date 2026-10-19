"""Offline text-to-video jobs using the bundled native diffusion engine."""
import asyncio,concurrent.futures,contextlib,importlib.util,json,os,pathlib,re,subprocess,threading,time,uuid
from aiohttp import web
from bootstrap import ROOT,STACK,PRIVATE,config,read,write
from library import library

class Videos:
    def __init__(self):
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1);self.lock=threading.Lock();self.stop=threading.Event();self.process=None
        self.current=None;self.records=ROOT/'data/video-jobs';self.records.mkdir(parents=True,exist_ok=True)
    def model(self):return next((m for m in library.catalog if m.get('adapter')=='wan21-t2v'),None)
    def busy(self):return bool(self.current and self.current.get('state') in {'queued','loading','generating','restoring'})
    def snapshot(self):
        item=self.model();ready=bool(item and library.ready(item));history=[]
        for path in sorted(self.records.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
            value=read(path,{})
            if value.get('state') in {'queued','loading','generating','restoring'} and (not self.current or value.get('id')!=self.current.get('id')):value.update(state='interrupted',error='Процесс был остановлен. Готовые файлы сохранены.')
            if value:history.append(self.public(value))
        return {'free':True,'local':True,'model_id':item['id'] if item else None,'ready':ready,'model':item['name'] if item else None,
            'hardware':library.device,'recommendation':library.recommendation(item) if item else None,'total':sum(f['bytes'] for f in item['files']) if item else 0,
            'current':self.public(self.current) if self.current else None,'history':history,'supports_image_input':False}
    def public(self,job):
        value={k:v for k,v in job.items() if k not in {'output','log'}}
        if job.get('state')=='complete':value['url']='/api/video/files/'+job['id']
        return value
    def save(self,**changes):
        self.current.update(changes,updated_at=time.time());write(self.records/(self.current['id']+'.json'),self.current)
    def start(self,value):
        with self.lock:
            if self.busy():raise ValueError('Уже создаётся видео. Дождитесь завершения или остановите его.')
            if (library.activation or {}).get('state')=='loading':raise ValueError('Дождитесь загрузки модели кода перед созданием видео.')
            from gpu_lease import active
            if active():raise ValueError('Видеокарта занята генерацией. Дождитесь завершения текущего задания.')
            item=self.model()
            if not item or not library.ready(item):raise ValueError('Сначала скачайте комплект видеомодели в разделе «Модели».')
            if not library.device.get('cuda') or library.recommendation(item)['level']=='limited':raise ValueError('Для этого видеорежима нужно от 24 ГБ RAM и NVIDIA от 8 ГБ VRAM.')
            prompt=str(value.get('prompt','')).strip()
            if not 1<=len(prompt)<=6000:raise ValueError('Описание видео должно содержать от 1 до 6000 символов.')
            width,height=value.get('width',512),value.get('height',288);frames=value.get('frames',33);steps=value.get('steps',20)
            if (width,height) not in {(256,144),(512,288),(832,480),(480,832)} or frames not in {9,17,33,49,81} or not isinstance(steps,int) or not 4<=steps<=40:raise ValueError('Неподдерживаемые параметры видео.')
            if (width*height>512*288 or frames>33) and library.device.get('vram_gb',0)<11.9:raise ValueError('Для этого размера или длительности рекомендуется от 12 ГБ VRAM. Выберите 512×288 и до 33 кадров.')
            if not PRIVATE and config().get('external_url'):raise ValueError('Видео требует управляемую приложением локальную модель. Остановите внешний сервер и выберите модель из каталога.')
            import shutil
            if shutil.disk_usage(ROOT).free<2*1024**3:raise ValueError('Освободите не менее 2 ГБ для результата и временных файлов.')
            self.stop.clear();ident=uuid.uuid4().hex;folder=ROOT/'output/videos'/ident;folder.mkdir(parents=True)
            self.current={'id':ident,'state':'queued','prompt':prompt,'width':width,'height':height,'frames':frames,'steps':steps,'fps':16,'seed':int(value.get('seed',42))%(2**31),
                'created_at':time.time(),'progress':0,'output':str(folder/'video.webm'),'log':str(ROOT/'logs'/('video-'+ident+'.log')),'free':True}
            self.save();self.pool.submit(self.generate,item,dict(self.current));return self.public(self.current)
    @contextlib.contextmanager
    def handoff(self):
        source=STACK/'creative-kit/image-tool.py';spec=importlib.util.spec_from_file_location('freedom_video_handoff',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if module.ready():
            with module.gpu_handoff() as lease:
                try:yield lease,module
                finally:self.terminate_child()
        else:
            from gpu_lease import acquire,release
            lease=acquire()
            try:yield lease,module
            finally:self.terminate_child();release(lease)
    def terminate_child(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
    def generate(self,item,job):
        started=time.monotonic();success=False
        try:
            if self.stop.is_set():raise InterruptedError()
            folder=library.folder(item);self.save(state='loading')
            with self.handoff() as (lease,module):
                from gpu_lease import add_child
                if self.stop.is_set():raise InterruptedError()
                args=[str(module.engine()),'-M','vid_gen','--diffusion-model',str(folder/'wan2.1_t2v_1.3B_fp16.safetensors'),
                    '--t5xxl',str(folder/'umt5-xxl-encoder-Q4_K_M.gguf'),'--vae',str(folder/'wan_2.1_vae.safetensors'),
                    '-p',job['prompt'],'-n','blurry, distorted, watermark, text, low quality',
                    '-W',str(job['width']),'-H',str(job['height']),'--video-frames',str(job['frames']),'--fps',str(job['fps']),
                    '--steps',str(job['steps']),'--cfg-scale','6.0','--flow-shift','3.0','--sampling-method','euler',
                    '--offload-to-cpu','--clip-on-cpu','--vae-on-cpu','--vae-tiling','--temporal-tiling','--diffusion-fa',
                    '-t',str(max(1,min(16,library.device.get('physical_cores') or 4))),'-s',str(job['seed']),'-o',job['output']]
                with open(job['log'],'wb') as log:
                    child=subprocess.Popen(args,cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
                    self.process=child;add_child(lease,child.pid)
                    while child.poll() is None:
                        if self.stop.wait(1):raise InterruptedError()
                        if time.monotonic()-started>3500:raise TimeoutError('Лимит одного задания — 55 минут.')
                        with open(job['log'],'rb') as reader:
                            reader.seek(0,2);reader.seek(max(0,reader.tell()-8000));text=reader.read().decode('utf8','replace')
                        steps=re.findall(r'(\d+)\s*/\s*'+str(job['steps'])+r'\b',text)
                        if steps:self.save(state='generating',progress=min(95,round(int(steps[-1])/job['steps']*95)))
                    if child.returncode:raise RuntimeError('Видеодвижок завершился с кодом '+str(child.returncode)+'. Журнал: '+job['log'])
                output=pathlib.Path(job['output'])
                if not output.is_file() or output.stat().st_size<1000:raise RuntimeError('Видеодвижок не создал файл WebM.')
                with output.open('rb') as stream:
                    if stream.read(4)!=b'\x1aE\xdf\xa3':raise RuntimeError('Неверный заголовок WebM.')
                self.save(state='restoring',progress=98);success=True
            self.save(state='complete',progress=100,seconds=round(time.monotonic()-started,2),bytes=pathlib.Path(job['output']).stat().st_size)
        except InterruptedError:self.save(state='cancelled',seconds=round(time.monotonic()-started,2))
        except Exception as exc:self.save(state='error',error=str(exc),seconds=round(time.monotonic()-started,2))
        finally:
            self.terminate_child()
            self.process=None
    def cancel(self):self.stop.set();return {'ok':True}

videos=Videos()
def register(app,bridge):
    async def status(request):return web.json_response(videos.snapshot())
    async def start(request):
        listed=await bridge.rpc('session.list',scope='live',limit=200)
        if any(s.get('running') for s in listed.get('sessions',[])):raise ValueError('Сначала дождитесь завершения текущей задачи агента или остановите её.')
        return web.json_response(videos.start(await request.json()))
    async def cancel(request):return web.json_response(videos.cancel())
    async def file(request):
        ident=request.match_info['ident']
        if not re.fullmatch(r'[a-f0-9]{32}',ident):raise web.HTTPNotFound()
        record=read(videos.records/(ident+'.json'),{})
        path=(ROOT/'output/videos'/ident/'video.webm').resolve()
        if record.get('state')!='complete' or not path.is_relative_to((ROOT/'output/videos').resolve()) or not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Type':'video/webm','Content-Disposition':'inline; filename="FreedomGPT-'+ident[:8]+'.webm"'})
    app.router.add_get('/api/video',status);app.router.add_post('/api/video/generate',start);app.router.add_post('/api/video/cancel',cancel);app.router.add_get('/api/video/files/{ident}',file)
