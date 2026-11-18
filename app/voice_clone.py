"""Private, offline reference-voice profiles and bounded CPU synthesis jobs."""
import asyncio,contextlib,hashlib,json,os,pathlib,re,time,uuid,wave
from array import array
import psutil
from aiohttp import web

ID=re.compile(r'[a-f0-9]{32}')

def memory_headroom(physical=True):
    """Usable allocation budget, including Windows commit limits."""
    available=psutil.virtual_memory().available
    if os.name!='nt':return available
    import ctypes as c
    class Performance(c.Structure):
        _fields_=[('cb',c.c_ulong)]+[(name,c.c_size_t) for name in (
            'CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable',
            'SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[
            ('HandleCount',c.c_ulong),('ProcessCount',c.c_ulong),('ThreadCount',c.c_ulong)]
    info=Performance();info.cb=c.sizeof(info)
    if c.windll.psapi.GetPerformanceInfo(c.byref(info),info.cb):
        commit=max(0,(info.CommitLimit-info.CommitTotal)*info.PageSize)
        return min(available,commit) if physical else commit
    return available

def startup_headroom():
    # Windows can page allocations; distinguish RAM pressure from exhausted commit.
    if psutil.virtual_memory().available < 1024**3:return 0
    return memory_headroom(physical=False)

class VoiceClones:
    def __init__(self,root,enabled):
        self.root=pathlib.Path(root);self.enabled=enabled
        self.folder=self.root/'data/speech-profiles';self.folder.mkdir(parents=True,exist_ok=True) if enabled else None
        self.python=self.root/'runtime/personal-speech/clone-python/Scripts/python.exe'
        self.model=self.root/'runtime/personal-speech/models/Qwen3-TTS-12Hz-0.6B-Base'
        self.process=None;self.log=None;self.jobs={};self.tasks=set();self.lock=asyncio.Lock();self.prepare_lock=asyncio.Lock()
        self.used=0;self.reaper=None

    def profile(self,pid):
        if not ID.fullmatch(pid):raise ValueError('Некорректный профиль голоса.')
        path=self.folder/pid/'profile.json'
        if not path.is_file():raise ValueError('Профиль голоса не найден.')
        return json.loads(path.read_text(encoding='utf-8'))

    def save(self,p):
        path=self.folder/p['id']/'profile.json';temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

    def profiles(self):
        rows=[]
        for path in self.folder.glob('*/profile.json') if self.enabled else []:
            with contextlib.suppress(OSError,ValueError):
                p=json.loads(path.read_text(encoding='utf-8'))
                if not p.get('hidden'):rows.append(p)
        return sorted(rows,key=lambda p:p.get('created',0),reverse=True)

    def status(self):
        ready=self.enabled and self.python.is_file() and (self.model/'verified-manifest.json').is_file()
        default=None
        with contextlib.suppress(OSError,ValueError,KeyError):
            pid=json.loads((self.folder/'default.json').read_text())['profile']
            if self.profile(pid)['state']=='ready':default='clone-'+pid
        return {'enabled':self.enabled,'ready':ready,'device':'cpu','offline':True,'model':'Qwen3-TTS 0.6B',
                'profiles':self.profiles(),'max_bytes':16*1024**2,'max_seconds':30,'default_voice':default}

    def voices(self):
        return [{'id':'clone-'+p['id'],'name':p['name']+' · мой голос','language':lang,'engine':'Qwen3-TTS'}
                for p in self.profiles() if p.get('state')=='ready' for lang in ('ru','en')]

    def task(self,coroutine):
        task=asyncio.create_task(coroutine);self.tasks.add(task);task.add_done_callback(self.tasks.discard);return task

    async def command(self,args,timeout=90):
        process=await asyncio.create_subprocess_exec(*map(str,args),cwd=self.root,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=0x08004000)
        try:
            out,err=await asyncio.wait_for(process.communicate(),timeout)
            if process.returncode:raise ValueError('Не удалось обработать звук: '+err.decode(errors='replace')[-180:])
            return out
        finally:
            if process.returncode is None:process.kill();await process.communicate()

    async def prepare(self,pid):
        async with self.prepare_lock:
            p=self.profile(pid);folder=self.folder/pid
            try:
                config=json.loads((self.root/'data/personal-voice.json').read_text(encoding='utf-8-sig'))
                ffmpeg=pathlib.Path(config['ffmpeg']);binary=self.root/config['binary'];model=self.root/config['model']
                if not all(f.is_file() for f in (ffmpeg,binary,model)):raise ValueError('Обработчик звука или распознавание не установлены.')
                await self.command([ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-y','-protocol_whitelist','file,pipe',
                    '-i',folder/'original.audio','-map','0:a:0','-vn','-ar','24000','-ac','1','-c:a','pcm_s16le','-t','31',folder/'reference.wav'],30)
                with wave.open(str(folder/'reference.wav'),'rb') as wav:
                    seconds=wav.getnframes()/wav.getframerate();samples=array('h',wav.readframes(wav.getnframes()))
                if not 3<=seconds<=30.05:raise ValueError('Выберите запись длиной от 3 до 30 секунд.')
                if not samples or max(abs(x) for x in samples)<30:raise ValueError('В записи не слышно речи.')
                p.update(seconds=round(seconds,2),state='transcribing');self.save(p)
                if not p.get('text'):
                    await self.command([ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-y','-i',folder/'reference.wav',
                                        '-ar','16000','-ac','1','-c:a','pcm_s16le',folder/'recognize.wav'],30)
                    await self.command([binary,'-m',model,'-f',folder/'recognize.wav','-t','4','-l',p['language'],
                                        '-ng','-nt','-otxt','-of',folder/'transcript'],120)
                    p['text']=' '.join((folder/'transcript.txt').read_text(encoding='utf-8-sig').split())
                if not p['text'].strip() or p['text'].strip() in ('[BLANK_AUDIO]','[Silence]'):raise ValueError('Не удалось распознать речь. Добавьте текст записи вручную.')
                p.update(state='ready',error='',updated=time.time());self.save(p)
            except Exception as exc:
                p.update(state='error',error=str(exc)[:300]);self.save(p)

    async def upload(self,request):
        if not self.enabled:raise ValueError('Профили собственного голоса недоступны в этой сборке.')
        if sum(p['state'] in ('preparing','transcribing') for p in self.profiles())>=2:raise ValueError('Дождитесь обработки предыдущей записи.')
        pid=uuid.uuid4().hex;folder=self.folder/pid;folder.mkdir()
        p={'id':pid,'name':'Мой голос','language':'ru','text':'','created':time.time(),'state':'preparing','error':''}
        reader=await request.multipart();size=0
        while field:=await reader.next():
            if field.name=='audio':
                with (folder/'original.audio').open('wb') as f:
                    while chunk:=await field.read_chunk(65536):
                        size+=len(chunk)
                        if size>16*1024**2:raise ValueError('Запись должна быть меньше 16 МБ.')
                        f.write(chunk)
            elif field.name in ('name','language','text'):
                raw=await field.read_chunk(8192)
                if not field.at_eof():raise ValueError('Слишком длинное поле профиля.')
                p[field.name]=raw.decode('utf-8').strip()
        if not size:raise ValueError('Выберите аудиозапись.')
        p['name']=(p['name'] or 'Мой голос')[:70]
        if p['language'] not in ('ru','en'):raise ValueError('Выберите русский или английский язык записи.')
        if len(p['text'])>2500:raise ValueError('Слишком длинный текст записи.')
        with (folder/'original.audio').open('rb') as stream:p['source_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
        for previous in self.profiles():
            if previous['state']!='ready' or previous['language']!=p['language']:continue
            source=self.folder/previous['id']/'original.audio'
            if not source.is_file():continue
            with source.open('rb') as stream:prior_hash=hashlib.file_digest(stream,'sha256').hexdigest()
            if prior_hash==p['source_sha256']:
                # Keep the uploaded bytes as a private audit artifact; do not create a duplicate voice.
                return web.json_response(previous)
        self.save(p);self.task(self.prepare(pid));return web.json_response(p,status=202)

    async def update(self,request):
        p=self.profile(request.match_info['pid']);data=await request.json()
        if p['state'] in ('preparing','transcribing'):raise ValueError('Дождитесь обработки записи.')
        if 'text' in data:
            if not isinstance(data['text'],str) or not 1<=len(data['text'].strip())<=2500:raise ValueError('Добавьте текст, произнесённый в записи.')
            p['text']=data['text'].strip()
        if 'name' in data:p['name']=str(data['name']).strip()[:70] or 'Мой голос'
        p.update(updated=time.time(),state='ready',error='');self.save(p)
        return web.json_response(p)

    async def reference(self,request):
        p=self.profile(request.match_info['pid']);path=self.folder/p['id']/'reference.wav'
        if not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Type':'audio/wav'})

    async def _start(self):
        if self.process and self.process.returncode is None:return
        env=os.environ.copy()
        for key in ('PYTHONPATH','PYTHONHOME'):env.pop(key,None)
        env.update(TEMP=str(self.root/'.tmp'),TMP=str(self.root/'.tmp'),TMPDIR=str(self.root/'.tmp'),
            CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='6',MKL_NUM_THREADS='6',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
            HF_HOME=str(self.root/'.cache/huggingface'),NUMBA_CACHE_DIR=str(self.root/'.cache/numba'),TOKENIZERS_PARALLELISM='false')
        (self.root/'logs/voice').mkdir(parents=True,exist_ok=True)
        self.log=(self.root/'logs/voice/clone-worker.log').open('ab')
        self.process=await asyncio.create_subprocess_exec(str(self.python),'-I','-B',str(self.root/'clone_worker.py'),cwd=self.root,
            env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=self.log,creationflags=0x08004000)
        if not self.reaper or self.reaper.done():self.reaper=asyncio.create_task(self._idle())

    async def _stop(self):
        process=self.process;self.process=None
        if process and process.returncode is None:
            if process.stdin:process.stdin.close()
            try:await asyncio.wait_for(process.communicate(),3)
            except (asyncio.TimeoutError,ConnectionError,BrokenPipeError):
                with contextlib.suppress(psutil.Error):
                    owner=psutil.Process(process.pid)
                    if str(self.root/'clone_worker.py').lower() in [arg.lower() for arg in owner.cmdline()]:
                        for child in owner.children(recursive=True):
                            with contextlib.suppress(psutil.Error):child.terminate()
                        owner.terminate()
                with contextlib.suppress(Exception):await asyncio.wait_for(process.communicate(),5)
        if self.log:self.log.close();self.log=None

    async def _idle(self):
        while True:
            await asyncio.sleep(20)
            if self.lock.locked() or time.monotonic()-self.used<60:continue
            async with self.lock:
                if time.monotonic()-self.used<60:continue
                await self._stop();return

    async def generate(self,job,p,text,language,output):
        async with self.lock:
            if job['state']=='cancelled':return
            job.update(state='working',phase='Загружаю модель и переношу голос')
            try:
                if (not self.process or self.process.returncode is not None) and startup_headroom()<3*1024**3:
                    raise ValueError('Недостаточно свободной памяти для голоса. Закройте тяжёлые приложения или уменьшите контекст модели; чат продолжает работать.')
                await self._start();self.used=time.monotonic()
                self.process.stdin.write((json.dumps({'text':text,'language':language,'profile':p,'output':str(output)})+'\n').encode())
                await self.process.stdin.drain()
                while True:
                    raw=await asyncio.wait_for(self.process.stdout.readline(),900)
                    if not raw:raise ValueError('Движок голоса завершился. Повторите озвучку.')
                    result=json.loads(raw)
                    if result.get('progress'):
                        job['phase']=result['progress'];continue
                    if not result.get('ok'):raise ValueError(result.get('error','Не удалось перенести голос.'))
                    job.update(result={**result,'url':'/api/speech/audio/'+output.name});break
            except asyncio.CancelledError:
                job.update(state='cancelled');await self._stop();raise
            except Exception as exc:
                await self._stop()
                message=str(exc)
                job.update(state='error',error=message[:300])
            finally:
                self.used=time.monotonic()
                # A warm TTS model must not starve the microphone recognizer.
                if memory_headroom()<2*1024**3:await self._stop()
                if job['state']=='working' and job.get('result'):job['state']='ready'

    def enqueue(self,text,voice,language):
        if not self.status()['ready']:raise ValueError('Модель собственного голоса не готова.')
        if not isinstance(text,str) or not 1<=len(text.strip())<=700:raise ValueError('Некорректный текст для озвучки.')
        p=self.profile(voice.removeprefix('clone-'))
        if p.get('state')!='ready':raise ValueError('Сначала подготовьте профиль голоса.')
        language='English' if language=='en' else 'Russian'
        key=hashlib.sha256(json.dumps(['clone-v2-pread-chunk24-fulltext',p['id'],p.get('updated'),p['text'],text,language],ensure_ascii=False).encode()).hexdigest()
        output=self.root/'.cache/speech'/(key+'.wav');output.parent.mkdir(parents=True,exist_ok=True)
        if output.is_file():return {'url':'/api/speech/audio/'+key+'.wav','cached':True,'device':'cpu'}
        for job in self.jobs.values():
            if job['key']==key and job['state'] in ('queued','working'):return {'job':job['id']}
        if sum(j['state'] in ('queued','working') for j in self.jobs.values())>=3:raise ValueError('Дождитесь завершения озвучки.')
        # Completed job state is transient; audio and profiles remain on disk.
        if len(self.jobs)>100:self.jobs={k:j for k,j in self.jobs.items() if j['state'] in ('queued','working')}
        jid=uuid.uuid4().hex;job={'id':jid,'key':key,'state':'queued','phase':'Ожидаю озвучку','created':time.time()};self.jobs[jid]=job
        job['_task']=self.task(self.generate(job,p,text,language,output))
        return {'job':jid}

    async def job(self,request):
        j=self.jobs.get(request.match_info['jid'])
        if not j:raise web.HTTPNotFound()
        return web.json_response({k:v for k,v in j.items() if not k.startswith('_')})

    async def cancel(self,request):
        j=self.jobs.get(request.match_info['jid'])
        if j and j['state'] in ('queued','working'):
            j['_task'].cancel();j.update(state='cancelled')
        return web.json_response({'ok':True})

    async def close(self,app=None):
        for task in self.tasks:task.cancel()
        if self.reaper:self.reaper.cancel()
        await asyncio.gather(*list(self.tasks),*([self.reaper] if self.reaper else []),return_exceptions=True)
        await self._stop()

    def register(self,app):
        if not self.enabled:return
        app.router.add_get('/api/speech/profiles',lambda r:web.json_response(self.status()))
        app.router.add_post('/api/speech/profiles',self.upload)
        app.router.add_post('/api/speech/profiles/{pid}',self.update)
        app.router.add_get('/api/speech/profiles/{pid}/audio',self.reference)
        app.router.add_get('/api/speech/jobs/{jid}',self.job)
        app.router.add_post('/api/speech/jobs/{jid}/cancel',self.cancel)
        app.on_cleanup.append(self.close)
