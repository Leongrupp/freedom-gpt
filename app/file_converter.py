"""Private local converter: streaming uploads, persisted queue, isolated cancellable workers."""
import asyncio,contextlib,hashlib,json,mimetypes,os,pathlib,re,shutil,sqlite3,time,uuid
import psutil
from aiohttp import web

IMAGES={'png','jpg','jpeg','webp','avif','heic','heif','bmp','tif','tiff','gif','ico','svg','tga','psd'}
AUDIO={'mp3','wav','flac','m4a','aac','ogg','opus','wma','aiff','aif'}
VIDEO={'mp4','mkv','mov','avi','webm','m4v','mpeg','mpg','wmv','ts','mts'}
DOCS={'doc','docx','odt','rtf','txt','md','html','htm','epub'}
TABLES={'xlsx','xls','ods','csv','tsv'};SLIDES={'pptx','ppt','odp'}

def formats(ext):
    if ext=='pdf':return ['docx','txt','png','jpg','pdf']
    if ext in IMAGES:return ['jpg','png','webp','avif','tif','bmp','gif','ico','pdf','txt','docx']+(['mp4','webm'] if ext=='gif' else [])
    if ext in AUDIO:return ['mp3','wav','flac','m4a','ogg','opus','aac']
    if ext in VIDEO:return ['mp4','mkv','webm','mov','avi','gif','mp3','wav','flac','m4a','ogg','opus','aac']
    if ext in DOCS:return ['pdf','docx','odt','rtf','txt','html','epub']
    if ext in TABLES:return ['pdf','xlsx','ods','csv','tsv','html']+(['json','yaml'] if ext in ('xlsx','csv','tsv') else [])
    if ext in SLIDES:return ['pdf','pptx','odp']
    if ext in ('json','yaml','yml'):return ['json','yaml','csv','tsv','xlsx']
    if ext in ('srt','vtt'):return ['srt','vtt']
    return []

class FileConverter:
    def __init__(self,root,enabled=False,artifact=None):
        self.root=pathlib.Path(root).resolve();self.enabled=enabled;self.artifact=artifact
        self.database=self.root/'data/converter.sqlite3';self.python=self.root/'runtime/converter/python/Scripts/python.exe'
        self.queue=asyncio.Queue();self.worker=None;self.process=None;self.current=None;self.closing=False
        if enabled:
            with self.db() as conn:
                conn.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,created REAL,updated REAL,state TEXT,spec TEXT,progress TEXT,percent REAL,result TEXT,error TEXT,hidden INTEGER DEFAULT 0)')

    @contextlib.contextmanager
    def db(self):
        connection=sqlite3.connect(self.database,timeout=10);connection.row_factory=sqlite3.Row
        try:yield connection;connection.commit()
        finally:connection.close()

    def status(self):
        tools={}
        with contextlib.suppress(OSError,ValueError):tools=json.loads((self.root/'runtime/converter/tools.json').read_text(encoding='utf-8'))
        engines={key:bool(value and pathlib.Path(value).is_file()) for key,value in tools.items() if key in ('soffice','ffmpeg','ffprobe','tesseract')}
        return {'enabled':self.enabled,'ready':self.enabled and self.python.is_file() and all(engines.get(k) for k in ('soffice','ffmpeg','ffprobe','tesseract')),
                'offline':True,'engines':engines,'max_bytes':2*1024**3,'max_files':12,'max_total_bytes':4*1024**3,'max_document_bytes':200*1024**2,'max_data_bytes':50*1024**2,
                'formats':{ext:formats(ext) for ext in sorted(IMAGES|AUDIO|VIDEO|DOCS|TABLES|SLIDES|{'pdf','json','yaml','yml','srt','vtt'})}}

    def row(self,jid):
        if not re.fullmatch('[a-f0-9]{32}',jid):raise web.HTTPNotFound()
        with self.db() as conn:row=conn.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:raise web.HTTPNotFound()
        return dict(row)

    def update(self,jid,**data):
        if set(data)-{'state','progress','percent','result','error','hidden'}:raise ValueError('Invalid converter update')
        with self.db() as conn:conn.execute('UPDATE jobs SET '+','.join(k+'=?' for k in data)+',updated=? WHERE id=?',(*data.values(),time.time(),jid))

    def public(self,row):
        spec=json.loads(row['spec']);result=json.loads(row['result']) if row['result'] else {}
        return {'id':row['id'],'created':row['created'],'state':row['state'],'progress':row['progress'],'percent':row['percent'],
                'error':row['error'],'target':spec['target'],'names':[f['name'] for f in spec['files']],
                'seconds':result.get('seconds'),'warnings':result.get('warnings',[]),
                'files':[{**{k:f[k] for k in ('name','bytes')},'url':f"/api/converter/jobs/{row['id']}/files/{i}"} for i,f in enumerate(result.get('files',[]))]}

    async def catalog(self,request):return web.json_response(self.status())

    async def listing(self,request):
        with self.db() as conn:rows=conn.execute('SELECT * FROM jobs WHERE hidden=0 ORDER BY created DESC LIMIT 40').fetchall()
        return web.json_response({'jobs':[self.public(row) for row in rows]})

    async def upload(self,request):
        if not self.status()['ready']:raise ValueError('Локальные движки конвертера ещё подготавливаются.')
        with self.db() as conn:count=conn.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','working')").fetchone()[0]
        if count>=20:raise ValueError('В очереди уже 20 заданий. Дождитесь завершения части файлов.')
        jid=uuid.uuid4().hex;folder=self.root/'uploads/converter'/jid;folder.mkdir(parents=True)
        payload={};files=[];total=0
        reader=await request.multipart()
        while field:=await reader.next():
            if field.name=='files':
                if len(files)>=12:raise ValueError('Выберите не больше 12 файлов за раз.')
                name=pathlib.Path(field.filename or 'file').name[:180];ext=pathlib.Path(name).suffix.lower()[1:]
                if not formats(ext):raise ValueError('Формат не поддерживается: '+ext)
                path=folder/(str(len(files))+'.'+ext);size=0
                with path.open('wb') as stream:
                    while chunk:=await field.read_chunk(1024*1024):
                        size+=len(chunk);total+=len(chunk)
                        if size>2*1024**3 or total>4*1024**3:raise ValueError('Лимит: 2 ГБ на файл и 4 ГБ на пакет.')
                        limit=50*1024**2 if ext in ('json','yaml','yml','csv','tsv','html','htm','md','txt') else 200*1024**2
                        if ext not in AUDIO|VIDEO and size>limit:raise ValueError('Лимит: 50 МБ для текста и данных, 200 МБ для документов и фото.')
                        if total%(16*1024**2)<len(chunk) and shutil.disk_usage(self.root).free<500*1024**2:raise ValueError('На диске осталось меньше 500 МБ.')
                        stream.write(chunk)
                if not size:raise ValueError('Пустой файл: '+name)
                files.append({'name':name,'path':str(path.relative_to(self.root)),'bytes':size,'extension':ext})
            elif field.name=='options':
                raw=await field.read_chunk(8192)
                if not field.at_eof():raise ValueError('Некорректные параметры преобразования.')
                payload=json.loads(raw)
        if not files:raise ValueError('Выберите файлы.')
        target=payload.get('target');options=payload.get('options') or {}
        if not all(target in formats(f['extension']) for f in files):raise ValueError('Выбранный формат не подходит для всех файлов.')
        if options.get('quality','balanced') not in ('small','balanced','high'):raise ValueError('Выберите качество.')
        if options.get('video_size',0) not in (0,720,1080) or options.get('image_size',0) not in (0,1024,2048,4096):raise ValueError('Некорректный размер результата.')
        options={k:options[k] for k in ('quality','video_size','image_size','ocr','merge') if k in options}
        spec={'id':jid,'target':target,'options':options,'files':files,'session_id':payload.get('session_id')}
        now=time.time()
        with self.db() as conn:conn.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,0)',(jid,now,now,'queued',json.dumps(spec,ensure_ascii=False),'В очереди',0,None,''))
        self.queue.put_nowait(jid);return web.json_response(self.public(self.row(jid)),status=202)

    async def terminate(self):
        process=self.process
        if not process or process.returncode is not None:return
        with contextlib.suppress(psutil.Error):
            owner=psutil.Process(process.pid)
            if str(self.root/'convert_worker.py').lower() in [a.lower() for a in owner.cmdline()]:
                for child in reversed(owner.children(recursive=True)):
                    with contextlib.suppress(psutil.Error):child.terminate()
                owner.terminate()

    async def run(self):
        while True:
            jid=await self.queue.get();self.current=jid
            try:
                row=self.row(jid)
                if row['state']!='queued':continue
                spec=json.loads(row['spec']);self.update(jid,state='working',progress='Запускаю локальный движок',percent=0,error='')
                env=os.environ.copy()
                for key in ('PYTHONPATH','PYTHONHOME'):env.pop(key,None)
                env.update(TEMP=str(self.root/'.tmp'),TMP=str(self.root/'.tmp'),TMPDIR=str(self.root/'.tmp'),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
                logs=self.root/'logs/converter';logs.mkdir(exist_ok=True)
                with (logs/(jid+'.log')).open('ab') as log:
                    process=await asyncio.create_subprocess_exec(str(self.python),'-I','-B',str(self.root/'convert_worker.py'),cwd=self.root,env=env,
                        stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=log,creationflags=0x08004000,limit=2*1024**2)
                    self.process=process
                    if self.row(jid)['state']=='cancelled':
                        await self.terminate();await process.communicate();continue
                    process.stdin.write(json.dumps(spec).encode());await process.stdin.drain();process.stdin.close()
                    result=None;deadline=time.monotonic()+4*3600
                    while True:
                        raw=await asyncio.wait_for(process.stdout.readline(),min(600,max(1,deadline-time.monotonic())))
                        if not raw:break
                        try:value=json.loads(raw)
                        except ValueError:log.write(raw);continue
                        if 'progress' in value:self.update(jid,progress=value['progress'],percent=value.get('percent'))
                        elif 'ok' in value:result=value
                        if time.monotonic()>deadline:raise ValueError('Преобразование заняло больше четырёх часов.')
                    await process.wait()
                    if self.row(jid)['state']=='cancelled':continue
                    if not result or not result.get('ok'):raise ValueError((result or {}).get('error','Движок завершился без результата. Подробности в журнале задания.'))
                    self.update(jid,state='ready',result=json.dumps(result,ensure_ascii=False),progress='Готово',percent=100)
                    if spec.get('session_id') and self.artifact:
                        for item in result['files']:self.artifact(spec['session_id'],self.root/item['path'])
            except asyncio.CancelledError:
                await self.terminate()
                if self.row(jid)['state']=='working':self.update(jid,state='queued',progress='Продолжу после перезапуска')
                raise
            except Exception as exc:
                await self.terminate()
                if self.row(jid)['state']!='cancelled':self.update(jid,state='error',error=str(exc)[:450],progress='Не удалось преобразовать')
            finally:self.process=None;self.current=None;self.queue.task_done()

    async def cancel(self,request):
        jid=request.match_info['jid'];row=self.row(jid)
        if row['state'] in ('queued','working'):
            self.update(jid,state='cancelled',progress='Остановлено')
            if self.current==jid:await self.terminate()
        return web.json_response(self.public(self.row(jid)))

    async def download(self,request):
        row=self.row(request.match_info['jid']);result=json.loads(row['result']) if row['result'] else {}
        index=int(request.match_info['index']);files=result.get('files',[])
        if row['state']!='ready' or not 0<=index<len(files):raise web.HTTPNotFound()
        path=(self.root/files[index]['path']).resolve()
        if not path.is_relative_to((self.root/'output/converter'/row['id']).resolve()) or not path.is_file():raise web.HTTPNotFound()
        from urllib.parse import quote
        response=web.FileResponse(path)
        response.content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        response.headers['Content-Disposition']="attachment; filename*=UTF-8''"+quote(path.name)
        return response

    async def folder(self,request):
        row=self.row(request.match_info['jid']);data=await request.json()
        path=self.root/('exports/converter' if data.get('exported') else 'output/converter')/row['id']
        if row['state']!='ready' or not path.is_dir():raise ValueError('Папка результата ещё не создана.')
        os.startfile(path);return web.json_response({'ok':True})

    async def export(self,request):
        row=self.row(request.match_info['jid']);result=json.loads(row['result']) if row['result'] else {};index=int(request.match_info['index'])
        files=result.get('files',[])
        if row['state']!='ready' or not 0<=index<len(files):raise web.HTTPNotFound()
        source=(self.root/files[index]['path']).resolve()
        if not source.is_relative_to((self.root/'output/converter'/row['id']).resolve()) or not source.is_file():raise web.HTTPNotFound()
        folder=self.root/'exports/converter'/row['id'];folder.mkdir(parents=True,exist_ok=True)
        destination=folder/source.name
        def copy():
            nonlocal destination
            if destination.exists():
                with source.open('rb') as a,destination.open('rb') as b:
                    if hashlib.file_digest(a,'sha256').digest()==hashlib.file_digest(b,'sha256').digest():return
                destination=folder/(source.stem+'_'+uuid.uuid4().hex[:6]+source.suffix)
            if shutil.disk_usage(self.root).free<source.stat().st_size+500*1024**2:raise ValueError('Недостаточно места для второй копии. Исходный результат уже сохранён: нажмите «Открыть папку».')
            shutil.copy2(source,destination)
        await asyncio.to_thread(copy)
        return web.json_response({'saved':True,'name':destination.name,'bytes':destination.stat().st_size,'path':str(destination)})

    async def start(self,app):
        with self.db() as conn:
            conn.execute("UPDATE jobs SET state='queued',progress='Возобновляю после перезапуска' WHERE state='working'")
            queued=[r['id'] for r in conn.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created")]
        for jid in queued:self.queue.put_nowait(jid)
        self.worker=asyncio.create_task(self.run())

    async def close(self,app):
        if self.worker:
            self.worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.worker

    def register(self,app):
        if not self.enabled:return
        app.router.add_get('/api/converter',self.catalog)
        app.router.add_get('/api/converter/jobs',self.listing)
        app.router.add_post('/api/converter/jobs',self.upload)
        app.router.add_post('/api/converter/jobs/{jid}/cancel',self.cancel)
        app.router.add_get('/api/converter/jobs/{jid}/files/{index:\\d+}',self.download)
        app.router.add_post('/api/converter/jobs/{jid}/folder',self.folder)
        app.router.add_post('/api/converter/jobs/{jid}/export/{index:\\d+}',self.export)
        app.on_startup.append(self.start);app.on_cleanup.append(self.close)
