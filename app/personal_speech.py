"""Local speech output for this private Windows installation only."""
import asyncio,contextlib,hashlib,json,os,pathlib,re,time,wave
import psutil
from aiohttp import web
from voice_clone import VoiceClones

VOICES=[{'id':'ru-xenia','name':'Ксения · русский','language':'ru','engine':'Silero'},
        {'id':'ru-kseniya','name':'Ксения 2 · русский','language':'ru','engine':'Silero'},
        {'id':'ru-eugene','name':'Евгений · русский','language':'ru','engine':'Silero'},
        {'id':'ru-aidar','name':'Айдар · русский','language':'ru','engine':'Silero'},
        {'id':'ru-tars','name':'ТАРС · низкий роботизированный','language':'ru','engine':'Silero + local DSP'},
        {'id':'ru-baya','name':'Бая · русский','language':'ru','engine':'Silero'},
        {'id':'en-amy','name':'Amy · English (US)','language':'en','engine':'Piper'}]

class PersonalSpeech:
    def __init__(self,root,enabled=False):
        self.root=pathlib.Path(root).resolve();self.enabled=bool(enabled and os.name=='nt')
        self.folder=self.root/'runtime/personal-speech';self.cache=self.root/'.cache/speech'
        self.python=self.root/'runtime/personal-voice/python/Scripts/python.exe'
        self.process=None;self.lock=asyncio.Lock();self.log=None;self.used=0;self.reaper=None
        self.clones=VoiceClones(self.root,self.enabled)

    def status(self):
        required=[self.python,self.folder/'manifest.json',self.folder/'models/silero-v5_6_ru.pt',
                  self.folder/'models/en_US-amy-medium.onnx',self.folder/'models/en_US-amy-medium.onnx.json']
        return {'enabled':self.enabled,'ready':self.enabled and all(p.is_file() and p.stat().st_size>0 for p in required),
                'device':'cpu','offline':True,'voices':(VOICES+self.clones.voices()) if self.enabled else [],'cloning':self.clones.status()}

    async def _start(self):
        if self.process and self.process.returncode is None:return
        env=os.environ.copy()
        for key in ('PYTHONPATH','PYTHONHOME'):env.pop(key,None)
        env.update(TEMP=str(self.root/'.tmp'),TMP=str(self.root/'.tmp'),TMPDIR=str(self.root/'.tmp'),
                   CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',
                   TORCH_HOME=str(self.root/'.cache/torch'),HF_HOME=str(self.root/'.cache/huggingface'),
                   HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        self.cache.mkdir(parents=True,exist_ok=True)
        (self.root/'logs/voice').mkdir(parents=True,exist_ok=True)
        self.log=(self.root/'logs/voice/speech-worker.log').open('ab')
        self.process=await asyncio.create_subprocess_exec(str(self.python),'-I','-B',str(self.root/'speech_worker.py'),
            cwd=self.root,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=self.log,
            creationflags=0x08000000)
        if not self.reaper or self.reaper.done():self.reaper=asyncio.create_task(self._idle())

    async def _stop(self):
        process=self.process;self.process=None
        log=self.log;self.log=None
        if process and process.returncode is None:
            # Windows venv launchers have a child interpreter. EOF shuts down both cleanly.
            if process.stdin:process.stdin.close()
            try:await asyncio.wait_for(process.communicate(),5)
            except (asyncio.TimeoutError,BrokenPipeError,ConnectionError):
                with contextlib.suppress(psutil.Error):
                    owner=psutil.Process(process.pid)
                    if any(str(self.root/'speech_worker.py').lower()==str(arg).lower() for arg in owner.cmdline()):
                        for child in owner.children(recursive=True):
                            with contextlib.suppress(psutil.Error):child.terminate()
                        owner.terminate()
                with contextlib.suppress(Exception):await asyncio.wait_for(process.communicate(),5)
        elif process:
            with contextlib.suppress(Exception):await process.communicate()
        if log:log.close()

    async def _idle(self):
        while True:
            await asyncio.sleep(30)
            if self.lock.locked() or time.monotonic()-self.used<120:continue
            async with self.lock:
                if time.monotonic()-self.used<120:continue
                await self._stop();return

    async def synthesize(self,text,voice):
        if not self.status()['ready']:raise ValueError('Озвучка ещё не готова. Откройте настройки голоса.')
        if not isinstance(text,str) or not text.strip() or len(text)>700:raise ValueError('Некорректный фрагмент для озвучки.')
        if voice not in {row['id'] for row in VOICES}:raise ValueError('Выберите установленный голос.')
        key=hashlib.sha256(('speech-v2-numbers\0'+voice+'\0'+text).encode('utf-8')).hexdigest()
        output=self.cache/(key+'.wav')
        async with self.lock:
            if output.is_file():
                with wave.open(str(output),'rb') as wav:seconds=wav.getnframes()/wav.getframerate()
                return {'url':'/api/speech/audio/'+key+'.wav','seconds':seconds,'cached':True,'device':'cpu'}
            await self._start();self.used=time.monotonic()
            try:
                self.process.stdin.write((json.dumps({'text':text,'voice':voice,'output':str(output)},ensure_ascii=True)+'\n').encode())
                await self.process.stdin.drain()
                raw=await asyncio.wait_for(self.process.stdout.readline(),90)
                result=json.loads(raw)
                if not result.get('ok'):raise ValueError(result.get('error') or 'Не удалось создать озвучку.')
            except asyncio.CancelledError:
                # Discard the interrupted response before another request uses this pipe.
                await self._stop()
                raise
            except (asyncio.TimeoutError,BrokenPipeError,ConnectionError,ValueError) as exc:
                await self._stop()
                raise ValueError('Не удалось создать озвучку: '+str(exc)[:230]) from exc
            finally:self.used=time.monotonic()
            return {**result,'url':'/api/speech/audio/'+key+'.wav','cached':False}

    async def read(self,request):
        payload=await request.json()
        if isinstance(payload.get('voice'),str) and payload['voice'].startswith('clone-'):
            return web.json_response(self.clones.enqueue(payload.get('text'),payload['voice'],payload.get('language')))
        return web.json_response(await self.synthesize(payload.get('text'),payload.get('voice')))

    async def audio(self,request):
        key=request.match_info['key']
        if not re.fullmatch(r'[a-f0-9]{64}',key):raise web.HTTPNotFound()
        path=self.cache/(key+'.wav')
        if not path.is_file():raise web.HTTPNotFound()
        response=web.FileResponse(path);response.content_type='audio/wav'
        response.headers['Cache-Control']='private, max-age=86400'
        return response

    async def close(self,app=None):
        if self.reaper:
            self.reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.reaper
        async with self.lock:await self._stop()

    def register(self,app):
        if not self.enabled:return
        self.clones.register(app)
        app.router.add_get('/api/speech/status',lambda request:web.json_response(self.status()))
        app.router.add_post('/api/speech/synthesize',self.read)
        app.router.add_get('/api/speech/audio/{key}.wav',self.audio)
        app.on_cleanup.append(self.close)
