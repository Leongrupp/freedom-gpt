"""Durable local voice-over tracks using the already installed speech engines."""
import asyncio,contextlib,hashlib,json,math,pathlib,re,shutil,time,uuid,wave
from aiohttp import web
from bootstrap import read,write

ACTIVE={'queued','synthesizing','mastering','cancelling'}

def text_parts(text,limit=340):
    """Split at sentence/word boundaries, preserving the user's wording."""
    remaining=text.strip();parts=[]
    while remaining:
        if len(remaining)<=limit:parts.append(remaining);break
        window=remaining[:limit];ends=list(re.finditer(r'[.!?…][\s]+|\n',window));cut=ends[-1].end() if ends else window.rfind(' ')+1
        if cut<limit*.3:cut=limit
        parts.append(remaining[:cut].strip());remaining=remaining[cut:].strip()
    return [part for part in parts if part]

class NarrationStudio:
    def __init__(self,root,speech,ffmpeg,music=None):
        self.root=pathlib.Path(root).resolve();self.speech=speech;self.ffmpeg=ffmpeg;self.music=music
        self.folder=self.root/'data/narration-jobs';self.folder.mkdir(parents=True,exist_ok=True)
        self.current=None;self.task=None;self.stop=asyncio.Event();self.on_complete=None

    def public(self,row):
        if not row:return None
        result={key:value for key,value in row.items() if key not in {'text','request','output','folder'}}
        result['preview']=row.get('text','')[:160]
        if row.get('state')=='complete':
            result.update(url='/api/narration/files/'+row['id']+'/mp3',wav_url='/api/narration/files/'+row['id']+'/wav')
        return result

    def snapshot(self):
        history=[]
        for path in sorted(self.folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
            row=read(path,{})
            if row.get('state') in ACTIVE and (not self.current or self.current['id']!=row['id']):row.update(state='interrupted',error='Озвучка была прервана. Текст сохранён; повторного запуска не было.')
            if row:history.append(self.public(row))
        status=self.speech.status();ready=status.get('ready',False)
        try:self.ffmpeg()
        except (ValueError,OSError):ready=False
        tracks=[]
        if self.music:
            for row in self.music.snapshot().get('history',[]):
                if row.get('state')=='complete':tracks.append({'id':row['id'],'name':row['prompt'][:100],'duration':row.get('duration')})
        return {'ready':ready,'offline':True,'device':'cpu','speech':status,'backgrounds':tracks,'max_chars':12000,
            'current':self.public(self.current),'history':history}

    def validate(self,value):
        text=value.get('text');voice=value.get('voice');language=value.get('language','ru')
        if not isinstance(text,str) or not 1<=len(text.strip())<=12000:raise ValueError('Добавьте текст для диктора: от 1 до 12 000 символов.')
        status=self.speech.status()
        if not status.get('ready'):raise ValueError('Локальные голоса не готовы. Откройте настройки озвучки.')
        voices=[row for row in status.get('voices',[]) if row.get('id')==voice]
        if not voices or language not in {row.get('language') for row in voices}:raise ValueError('Выберите доступный голос и его язык.')
        rate=value.get('rate',1);pause=value.get('pause_ms',200);volume=value.get('background_volume',.12)
        if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or not .8<=rate<=1.2:raise ValueError('Темп озвучки: от 0,8 до 1,2.')
        if type(pause)!=int or not 0<=pause<=1000:raise ValueError('Пауза: от 0 до 1000 мс.')
        if isinstance(volume,bool) or not isinstance(volume,(int,float)) or not math.isfinite(volume) or not 0<=volume<=.35:raise ValueError('Громкость фона: от 0 до 35%.')
        background=str(value.get('background_id') or '')
        if background:
            if not re.fullmatch('[a-f0-9]{32}',background):raise ValueError('Выберите музыку из готовых треков.')
            record=read(self.root/'data/music-jobs'/(background+'.json'),{})
            if record.get('state')!='complete' or not (self.root/'output/music'/background/'track.wav').is_file():raise ValueError('Фоновый трек недоступен.')
        title=value.get('title') or text.strip().splitlines()[0][:70]
        if not isinstance(title,str) or not 1<=len(title)<=100:raise ValueError('Название дорожки: от 1 до 100 символов.')
        return {'text':text.strip(),'voice':voice,'language':language,'rate':rate,'pause_ms':pause,'background_id':background,'background_volume':volume,'title':title.strip(),'session_id':str(value.get('session_id') or '')}

    def save(self,**values):
        self.current.update(values,updated_at=time.time());write(self.folder/(self.current['id']+'.json'),self.current)

    async def start(self,value):
        params=self.validate(value);ident=str(value.get('input_id') or '')
        if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Не указан идентификатор озвучки.')
        prior=read(self.folder/(ident+'.json'),None)
        if prior:
            if prior.get('request')!=params:raise ValueError('Этот идентификатор уже использован для другой озвучки.')
            return self.public(prior)
        if self.task and not self.task.done():raise ValueError('Дождитесь завершения текущей дикторской дорожки.')
        if shutil.disk_usage(self.root).free<512*1024**2:raise ValueError('Освободите 512 МБ для обработки аудио.')
        self.ffmpeg();output=self.root/'output/narration'/ident;output.mkdir(parents=True,exist_ok=True)
        self.stop=asyncio.Event();self.current={**params,'request':params,'id':ident,'state':'queued','created_at':time.time(),'parts':0,'done':0,'progress':0,'folder':str(output)}
        self.save();self.task=asyncio.create_task(self.generate(dict(self.current)));return self.public(self.current)

    def check_cancelled(self):
        if self.stop.is_set():raise InterruptedError('Озвучка остановлена.')

    async def render_piece(self,text,job):
        if job['voice'].startswith('clone-'):
            result=self.speech.clones.enqueue(text,job['voice'],job['language'])
            if result.get('job'):
                deadline=time.monotonic()+950
                while time.monotonic()<deadline:
                    state=self.speech.clones.jobs.get(result['job'],{})
                    if state.get('state')=='ready':result=state['result'];break
                    if state.get('state') in {'error','cancelled'}:raise ValueError(state.get('error') or 'Не удалось озвучить вашим голосом.')
                    if not self.stop.is_set():self.save(phase=state.get('phase') or 'Создаём речь вашим голосом')
                    await asyncio.sleep(.7)
                else:raise TimeoutError('Ваш голос не завершил фрагмент за 15 минут.')
        else:result=await self.speech.synthesize(text,job['voice'])
        # Reuse cache files only; never resolve a URL or arbitrary path from a provider.
        match=re.fullmatch(r'/api/speech/audio/([a-f0-9]{64})\.wav',result.get('url',''))
        if not match:raise ValueError('Движок голоса не вернул аудиофайл.')
        source=self.root/'.cache/speech'/(match[1]+'.wav')
        if not source.is_file():raise ValueError('Не найден созданный фрагмент речи.')
        return source

    async def command(self,args,log,timeout=180):
        with open(log,'ab') as stream:
            process=await asyncio.create_subprocess_exec(*map(str,args),cwd=self.root,stdout=stream,stderr=stream,creationflags=0x08000000)
            deadline=time.monotonic()+timeout
            try:
                while process.returncode is None:
                    self.check_cancelled()
                    if time.monotonic()>deadline:raise TimeoutError('Обработка звука не завершилась вовремя.')
                    try:await asyncio.wait_for(process.wait(),.3)
                    except asyncio.TimeoutError:pass
                if process.returncode:raise ValueError('Не удалось обработать аудио. Журнал: '+str(log))
            finally:
                if process.returncode is None:
                    with contextlib.suppress(ProcessLookupError):process.terminate()
                    try:await asyncio.wait_for(process.wait(),5)
                    except asyncio.TimeoutError:
                        with contextlib.suppress(ProcessLookupError):process.kill()
                        await process.wait()

    async def master(self,job,paths):
        folder=pathlib.Path(job['folder']);listing=[]
        if job['pause_ms']:
            with wave.open(str(paths[0]),'rb') as first:
                rate=first.getframerate();channels=first.getnchannels();width=first.getsampwidth()
            with wave.open(str(folder/'pause.wav'),'wb') as blank:
                blank.setnchannels(channels);blank.setsampwidth(width);blank.setframerate(rate)
                blank.writeframes(b'\0'*int(rate*job['pause_ms']/1000)*channels*width)
        for index,path in enumerate(paths):
            name='part-'+str(index).zfill(4)+'.wav';shutil.copyfile(path,folder/name);listing.append("file '"+name+"'")
            if job['pause_ms'] and index<len(paths)-1:listing.append("file 'pause.wav'")
        (folder/'parts.txt').write_text('\n'.join(listing)+'\n',encoding='utf8')
        binary=self.ffmpeg();log=self.root/'logs'/('narration-'+job['id']+'.log');log.parent.mkdir(parents=True,exist_ok=True)
        common=[binary,'-nostdin','-hide_banner','-loglevel','error','-y','-threads','4','-filter_threads','2']
        await self.command([*common,'-f','concat','-safe','1','-i',folder/'parts.txt','-vn','-af',f"atempo={job['rate']},loudnorm=I=-16:TP=-1.5:LRA=11",'-ar','48000','-ac','2','-c:a','pcm_s16le',folder/'voice.wav'],log)
        with wave.open(str(folder/'voice.wav'),'rb') as reader:seconds=reader.getnframes()/reader.getframerate()
        if job['background_id']:
            background=self.root/'output/music'/job['background_id']/'track.wav'
            filters=f"[1:a]volume={job['background_volume']},afade=t=in:d=0.5,afade=t=out:st={max(0,seconds-1):.3f}:d=1[bg];[0:a][bg]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[mix]"
            await self.command([*common,'-i',folder/'voice.wav','-stream_loop','-1','-i',background,'-filter_complex',filters,'-map','[mix]','-t',str(seconds),'-ar','48000','-ac','2','-c:a','pcm_s16le',folder/'track.wav'],log)
        else:shutil.copyfile(folder/'voice.wav',folder/'track.wav')
        await self.command([*common,'-i',folder/'track.wav','-vn','-c:a','libmp3lame','-b:a','192k',folder/'track.mp3'],log)
        if (folder/'track.mp3').stat().st_size<1000:raise ValueError('Получился пустой файл MP3.')
        return seconds

    async def generate(self,job):
        started=time.monotonic()
        try:
            parts=text_parts(job['text']);self.save(state='synthesizing',parts=len(parts),phase='Создаём дикторскую речь')
            paths=[]
            for index,part in enumerate(parts):
                self.check_cancelled();source=await self.render_piece(part,job);self.check_cancelled()
                paths.append(source);self.save(done=index+1,progress=round((index+1)/len(parts)*85))
            self.save(state='mastering',phase='Выравниваем громкость и сохраняем дорожку',progress=90)
            seconds=await self.master(job,paths);self.check_cancelled()
            self.save(state='complete',seconds=round(seconds,2),generation_seconds=round(time.monotonic()-started,1),progress=100,output=str(pathlib.Path(job['folder'])/'track.mp3'))
            if self.on_complete:
                try:self.on_complete(dict(self.current))
                except Exception:self.save(presentation_error='Аудио сохранено. Не удалось обновить файлы чата.')
            # The master and shared speech cache are retained; temporary assembly copies are disposable.
            for path in pathlib.Path(job['folder']).glob('part-*.wav'):path.unlink(missing_ok=True)
            for name in ('parts.txt','pause.wav','voice.wav'):(pathlib.Path(job['folder'])/name).unlink(missing_ok=True)
        except (InterruptedError,asyncio.CancelledError):self.save(state='cancelled',phase='Озвучка остановлена')
        except Exception as exc:self.save(state='error',error=str(exc)[:700])

    def cancel(self):
        self.stop.set()
        if self.current and self.current.get('state') in ACTIVE:self.save(state='cancelling',phase='Завершаем текущий фрагмент и останавливаем озвучку')
        return {'ok':True}

    async def close(self,app=None):
        self.cancel()
        if self.task and not self.task.done():
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.task

    def register(self,app,bridge,artifact):
        async def status(request):return web.json_response(self.snapshot())
        async def start(request):
            value=await request.json();sid=str(value.get('session_id') or '')
            if sid:await bridge.resume(sid)
            loop=asyncio.get_running_loop()
            def completed(row):
                if row.get('session_id'):
                    artifact(row['session_id'],row['output'])
                    loop.create_task(bridge.broadcast({'type':'artifacts.changed','session_id':row['session_id']}))
            self.on_complete=completed
            return web.json_response(await self.start(value))
        async def cancel(request):return web.json_response(self.cancel())
        async def file(request):
            ident=request.match_info['ident'];kind=request.match_info['kind']
            if not re.fullmatch('[a-f0-9]{32}',ident) or kind not in {'wav','mp3'}:raise web.HTTPNotFound()
            row=read(self.folder/(ident+'.json'),{});path=self.root/'output/narration'/ident/('track.'+kind)
            if row.get('state')!='complete' or not path.is_file():raise web.HTTPNotFound()
            return web.FileResponse(path,headers={'Content-Type':'audio/wav' if kind=='wav' else 'audio/mpeg','Content-Disposition':'inline; filename="Freedom-voice-'+ident[:8]+'.'+kind+'"'})
        app.router.add_get('/api/narration',status);app.router.add_post('/api/narration/generate',start)
        app.router.add_post('/api/narration/cancel',cancel);app.router.add_get('/api/narration/files/{ident}/{kind}',file)
        app.on_shutdown.append(self.close)
