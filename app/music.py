"""Private Windows music studio: explicit installation, GPU lease, durable WAV results."""
import asyncio,concurrent.futures,contextlib,json,os,pathlib,re,shutil,struct,subprocess,sys,threading,time,uuid,wave
import requests
from aiohttp import web
from bootstrap import ROOT,read,write
from music_setup import COMMIT,environment

ACTIVE={'queued','loading','generating','restoring'}

class MusicStudio:
    def __init__(self,root=ROOT,cloud=None,videos=None,advisor=None):
        self.root=pathlib.Path(root);self.cloud=cloud;self.videos=videos;self.advisor=advisor
        self.lock=threading.RLock();self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.current=None;self.process=None;self.stop=threading.Event();self.on_complete=None;self.future=None;self.agent_idle=None
        self.records=self.root/'data/music-jobs';self.records.mkdir(parents=True,exist_ok=True)
        self.install=read(self.root/'data/music-install.json',{'state':'idle'})
        if self.install.get('state') in {'installing','downloading'}:self.install.update(state='interrupted',message='Установка прервана. Нажмите «Продолжить установку».')
    def ready(self):
        marker=read(self.root/'data/music-installed.json',{})
        folder=self.root/'runtime/music/ACE-Step-1.5'
        if marker.get('commit')!=COMMIT or not self.python().is_file() or not marker.get('files'):return False
        for row in marker['files']:
            path=folder/'checkpoints'/row['name']
            try:
                if not path.is_file() or path.stat().st_size!=row['bytes'] or path.stat().st_mtime_ns!=row['mtime_ns']:return False
            except OSError:return False
        return True
    def python(self):return self.root/'runtime/music/ACE-Step-1.5/.venv/Scripts/python.exe'
    def busy(self):return bool(self.current and self.current.get('state') in ACTIVE)
    def fit(self):
        device=(self.advisor.state.get('hardware') if self.advisor else None) or read(self.root/'data/hardware.json',{})
        reasons=[];free=shutil.disk_usage(self.root).free/1024**3
        if not device.get('cuda') or device.get('vram_gb',0)<11.8:reasons.append('Для этого комплекта Turbo + LM 1.7B нужна NVIDIA с 12 ГБ VRAM или больше.')
        if device.get('ram_gb',0)<23:reasons.append('Рекомендуется не менее 24 ГБ RAM.')
        if free<35 and not self.ready():reasons.append('Для модели, Python и CUDA-библиотек освободите 35 ГБ на диске A:.')
        return {'hardware':device,'free_disk_gb':round(free,1),'fits':not reasons,'reasons':reasons,
            'checked':bool(device.get('cpu')),'model':'ACE-Step 1.5 Turbo','min_vram_gb':12,'recommended_vram_gb':16,'setup_disk_gb':35}
    def public(self,job):
        if not job:return None
        result={k:v for k,v in job.items() if k not in {'output','log'}}
        if job.get('state')=='complete':result['url']='/api/music/files/'+job['id']
        return result
    def snapshot(self):
        history=[]
        for path in sorted(self.records.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
            row=read(path,{})
            if row.get('state') in ACTIVE and (not self.current or row['id']!=self.current['id']):row.update(state='interrupted',error='Задание прервано. Запуск автоматически не повторялся.')
            if row:history.append(self.public(row))
        connection=(self.cloud.connections.get('stability') or {}) if self.cloud else {}
        return {'enabled':os.name=='nt','ready':self.ready(),'model':'ACE-Step 1.5 Turbo','license':'MIT',
            'fit':self.fit(),'install':self.install,'current':self.public(self.current),'history':history,
            'cloud_connected':bool(connection.get('enabled')),'checked':'2026-10-22','weights_downloaded':self.ready()}
    def install_save(self,**values):
        self.install.update(values,updated_at=time.time());write(self.root/'data/music-install.json',self.install)
    def start_install(self):
        with self.lock:
            if self.busy() or self.future and not self.future.done():raise ValueError('Дождитесь текущего музыкального задания.')
            if not self.fit()['checked'] or not self.fit()['fits']:raise ValueError('Сначала проверьте ПК и устраните ограничения из рекомендации.')
            if self.ready():return {'ok':True,'already_installed':True}
            self.stop.clear();self.install_save(state='installing',message='Устанавливаем отдельный Python, зависимости и модель. Можно закрыть окно.',error=None)
            self.future=self.pool.submit(self.install_worker);return {'ok':True,'state':'installing'}
    def run_child(self,args,log,*,cwd=None,lease=None,timeout=3600,online=False):
        import psutil
        from music_setup import environment
        with open(log,'ab') as output:
            self.process=subprocess.Popen([str(a) for a in args],cwd=cwd or self.root,env=environment(self.root,online),
                stdout=output,stderr=output,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if lease:
                from gpu_lease import add_child
                add_child(lease,self.process.pid)
            deadline=time.monotonic()+timeout
            try:
                while self.process.poll() is None:
                    if self.stop.wait(.5):raise InterruptedError()
                    if time.monotonic()>deadline:raise TimeoutError('Превышено время музыкального задания. Журнал сохранён.')
                    if self.current and self.current.get('state')=='loading' and 'FREEDOM_MUSIC_GENERATING' in pathlib.Path(log).read_text(encoding='utf8',errors='replace')[-4000:]:self.save(state='generating')
                if self.process.returncode:raise RuntimeError('Музыкальный процесс завершился с ошибкой. Подробности: '+str(log))
            finally:
                if self.process and self.process.poll() is None:
                    parent=psutil.Process(self.process.pid)
                    children=parent.children(recursive=True)
                    for child in reversed(children):
                        with contextlib.suppress(psutil.Error):child.terminate()
                    with contextlib.suppress(psutil.Error):parent.terminate()
                    _,alive=psutil.wait_procs(children+[parent],timeout=5)
                    for child in alive:
                        with contextlib.suppress(psutil.Error):child.kill()
                self.process=None
    def install_worker(self):
        try:
            self.run_child([sys.executable,'-B',self.root/'music_setup.py',self.root],self.root/'logs/music-install.log',timeout=4*3600,online=True)
            if not self.ready():raise RuntimeError('Комплект музыки не прошёл проверку.')
            self.install_save(state='ready',message='Модель установлена и проверена. Можно создавать музыку.')
        except InterruptedError:self.install_save(state='paused',message='Установка остановлена. Повторный запуск использует уже скачанные файлы.')
        except Exception as exc:self.install_save(state='error',error=str(exc),message='Не удалось завершить установку. Уже скачанные файлы сохранены.')
    def save(self,**values):
        self.current.update(values,updated_at=time.time());write(self.records/(self.current['id']+'.json'),self.current)
    @staticmethod
    def validate(value):
        prompt=value.get('prompt');lyrics=value.get('lyrics','');duration=value.get('duration',30);bpm=value.get('bpm',0);seed=value.get('seed',42)
        if not isinstance(prompt,str) or not 3<=len(prompt.strip())<=4000:raise ValueError('Опишите музыку: от 3 до 4000 символов.')
        if not isinstance(lyrics,str) or len(lyrics)>8000:raise ValueError('Текст песни: не более 8000 символов.')
        if type(duration)!=int or duration not in {15,30,60,120,180}:raise ValueError('Выберите длительность из списка.')
        if type(bpm)!=int or bpm!=0 and not 40<=bpm<=240:raise ValueError('Темп: авто или 40–240 BPM.')
        if type(seed)!=int or not 0<=seed<=2147483647:raise ValueError('Неверный seed.')
        source=value.get('source','local');instrumental=value.get('instrumental',True)
        if source not in {'local','stability'} or type(instrumental)!=bool:raise ValueError('Неподдерживаемый режим музыки.')
        if value.get('language','ru') not in {'ru','en','es','fr','de','zh','ja','ko'}:raise ValueError('Выберите язык из списка.')
        if source=='local' and not instrumental and not lyrics.strip():raise ValueError('Добавьте текст песни или выберите «Без вокала».')
        if source=='stability' and (not instrumental or lyrics.strip()):raise ValueError('Stable Audio в этой студии создаёт инструментальную музыку; используйте локальную модель для текста песни.')
        return {'prompt':prompt.strip(),'lyrics':lyrics.strip(),'duration':duration,'bpm':bpm,'seed':seed,'source':source,'instrumental':instrumental,'language':value.get('language','ru')}
    def start(self,value):
        params=self.validate(value);intent=str(value.get('input_id') or '')
        if not re.fullmatch(r'[a-f0-9]{32}',intent):raise ValueError('Не указан идентификатор музыкального задания.')
        with self.lock:
            prior=read(self.records/(intent+'.json'),None)
            if prior:
                if prior.get('session_id','')!=str(value.get('session_id') or '') or any(prior.get(k)!=v for k,v in params.items()):raise ValueError('Этот идентификатор уже использован для другого задания.')
                return self.public(prior)
            if self.busy() or self.future and not self.future.done():raise ValueError('Дождитесь музыки или установки модели.')
            if params['source']=='local' and not self.ready():raise ValueError('Сначала установите музыкальную модель после проверки ПК.')
            if params['source']=='local' and not self.fit()['fits']:raise ValueError('ПК не соответствует требованиям локальной модели.')
            if params['source']=='stability':
                if not self.cloud or not (self.cloud.connections.get('stability') or {}).get('enabled'):raise ValueError('Подключите Stable Audio в разделе API.')
                if value.get('credit_consent') is not True:raise ValueError('Подтвердите расход стартовых API-кредитов.')
            folder=self.root/'output/music'/intent;folder.mkdir(parents=True,exist_ok=True)
            self.stop.clear();self.current={**params,'id':intent,'state':'queued','created_at':time.time(),
                'session_id':str(value.get('session_id') or ''),'output':str(folder/'track.wav'),'log':str(self.root/'logs'/('music-'+intent+'.log'))}
            self.save();self.future=self.pool.submit(self.generate,dict(self.current));return self.public(self.current)
    @staticmethod
    def validate_wav(path):
        # Both PCM16 and IEEE-float WAV are valid model outputs (wave.open rejects float).
        size=pathlib.Path(path).stat().st_size
        if not 44<=size<=160*1024**2:raise ValueError('Движок вернул пустой или слишком большой аудиофайл.')
        with open(path,'rb') as stream:
            header=stream.read(12)
            if header[:4]!=b'RIFF' or header[8:]!=b'WAVE':raise ValueError('Движок не вернул файл WAV.')
            fmt=None;data=None
            for _ in range(256):
                raw=stream.read(8)
                if len(raw)<8:break
                name,length=struct.unpack('<4sI',raw);end=stream.tell()+length
                if end>size:raise ValueError('Неполный файл WAV.')
                if name==b'fmt ':
                    content=stream.read(min(length,64))
                    if len(content)<16:raise ValueError('Неверный формат WAV.')
                    fmt=struct.unpack('<HHIIHH',content[:16])
                if name==b'data':data=length
                stream.seek(end+(length%2))
                if fmt and data is not None:break
            if not fmt or data is None or fmt[0] not in {1,3,65534} or fmt[1] not in {1,2} or not 8000<=fmt[2]<=192000 or data<fmt[3]:raise ValueError('Движок вернул пустой аудиофайл или неподдерживаемый WAV.')
    def generate(self,job):
        started=time.monotonic()
        try:
            if self.stop.is_set():raise InterruptedError()
            if job['source']=='local':
                deadline=time.monotonic()+1800
                while self.agent_idle and not self.agent_idle():
                    if self.stop.wait(2):raise InterruptedError()
                    if time.monotonic()>deadline:raise TimeoutError('Агент не освободил видеокарту за 30 минут. Музыка не запускалась.')
                self.save(state='loading')
                with self.videos.handoff() as (lease,_):
                    self.run_child([self.python(),'-B',self.root/'music_worker.py',self.root,self.records/(job['id']+'.json')],job['log'],lease=lease,timeout=2400)
                    self.validate_wav(job['output']);self.save(state='restoring')
            else:self.cloud_generate(job);self.validate_wav(job['output'])
            self.save(state='complete',seconds=round(time.monotonic()-started,1),bytes=pathlib.Path(job['output']).stat().st_size)
            if self.on_complete:
                try:self.on_complete(dict(self.current))
                except Exception:self.save(presentation_error='Трек сохранён. Не удалось обновить список файлов чата.')
        except InterruptedError:self.save(state='cancelled')
        except requests.RequestException:self.save(state='unknown',error='Связь с API оборвалась. Результат запроса неизвестен; кредиты могли быть использованы. Генерация не отправляется повторно. Проверьте историю в кабинете Stability AI.')
        except Exception as exc:self.save(state='error',error=str(exc)[:700])
    def cloud_generate(self,job):
        credential=self.cloud.vault.get('stability')
        if not credential:raise ValueError('API-ключ Stable Audio недоступен. Подключите его заново.')
        self.cloud.reserve('stability');self.save(state='generating',submitted_at=time.time())
        headers={'Authorization':'Bearer '+credential['key'],'Accept':'audio/*'}
        # No retries of a credit-consuming POST. Result polling uses GET only.
        with requests.post('https://api.stability.ai/v2beta/audio/stable-audio/text-to-audio',headers=headers,
            files={'none':('','')},data={'model':'stable-audio-3','prompt':job['prompt'],'duration':job['duration'],'output_format':'wav','seed':job['seed']},timeout=(15,90),allow_redirects=False) as response:
            if response.status_code not in {200,202}:raise ValueError(self.cloud.upstream_error(response.status_code))
            if 'json' in response.headers.get('Content-Type',''):
                ident=response.json().get('id')
                if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',ident):raise ValueError('API не вернул идентификатор аудио.')
                self.save(remote_id=ident)
            else:pathlib.Path(job['output']).write_bytes(response.content);return
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            if self.stop.wait(2):raise InterruptedError()
            with requests.get('https://api.stability.ai/v2beta/audio/results/'+ident,headers=headers,timeout=(10,45),allow_redirects=False) as result:
                if result.status_code==202:continue
                if result.status_code!=200:raise ValueError(self.cloud.upstream_error(result.status_code))
                pathlib.Path(job['output']).write_bytes(result.content);return
        raise TimeoutError('API не завершил трек за 15 минут. Задание не отправлялось повторно.')
    def cancel(self):self.stop.set();return {'ok':True}
    def register(self,app,bridge,artifact):
        async def status(request):return web.json_response(self.snapshot())
        async def scan(request):
            result=await asyncio.to_thread(self.advisor.scan)
            return web.json_response(self.snapshot())
        async def install(request):return web.json_response(self.start_install())
        async def cancel(request):return web.json_response(self.cancel())
        async def generate(request):
            value=await request.json();params=self.validate(value)
            if params['source']=='local':
                listed=await bridge.rpc('session.list',scope='live',limit=200)
                if any(row.get('running') for row in listed.get('sessions',[])) and value.get('defer_until_idle') is not True:raise ValueError('Локальная музыка использует видеокарту. Дождитесь завершения задачи агента; история чатов сохранится.')
                if app.get('performance_busy'):raise ValueError('Дождитесь окончания настройки видеокарты.')
            sid=str(value.get('session_id') or '')
            if sid:await bridge.resume(sid)
            loop=asyncio.get_running_loop()
            def agent_idle():
                result=asyncio.run_coroutine_threadsafe(bridge.rpc('session.list',scope='live',limit=200),loop).result(timeout=25)
                return not any(row.get('running') for row in result.get('sessions',[]))
            self.agent_idle=agent_idle
            def completed(job):
                if job.get('session_id'):
                    artifact(job['session_id'],job['output'])
                    asyncio.run_coroutine_threadsafe(bridge.broadcast({'type':'artifacts.changed','session_id':job['session_id']}),loop)
            self.on_complete=completed
            return web.json_response(self.start(value))
        async def file(request):
            ident=request.match_info['ident']
            if not re.fullmatch(r'[a-f0-9]{32}',ident):raise web.HTTPNotFound()
            row=read(self.records/(ident+'.json'),{});path=self.root/'output/music'/ident/'track.wav'
            if row.get('state')!='complete' or not path.is_file():raise web.HTTPNotFound()
            return web.FileResponse(path,headers={'Content-Type':'audio/wav','Content-Disposition':'inline; filename="FreedomGPT-'+ident[:8]+'.wav"'})
        app.router.add_get('/api/music',status);app.router.add_post('/api/music/scan',scan)
        app.router.add_post('/api/music/install',install);app.router.add_post('/api/music/cancel',cancel)
        app.router.add_post('/api/music/generate',generate);app.router.add_get('/api/music/files/{ident}',file)
