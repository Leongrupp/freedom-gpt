"""Opt-in paid fal queue jobs. A submitted job is never submitted again on recovery."""
import asyncio,base64,contextlib,json,pathlib,re,shutil,time,urllib.parse
from aiohttp import ClientSession,ClientTimeout,ClientError,web

VIDEO_MODELS=[{'id':'fal-ai/wan-25-preview/text-to-video','name':'Wan 2.5 · fal.ai',
    'durations':['5','10'],'resolutions':['480p','720p','1080p'],'ratios':['16:9','9:16','1:1'],
    'pricing_url':'https://fal.ai/models/fal-ai/wan-25-preview/text-to-video'}]
ACTIVE={'queued','submitting','IN_QUEUE','IN_PROGRESS','downloading','cancel_requested'}
VIDEO_MODELS.append({'id':'fal-ai/wan-25-preview/image-to-video','name':'Wan 2.5 · Image to Video','image_input':True,
    'durations':['5','10'],'resolutions':['480p','720p','1080p'],'ratios':['16:9','9:16','1:1'],
    'pricing_url':'https://fal.ai/models/fal-ai/wan-25-preview/image-to-video'})

class FalVideos:
    def __init__(self,owner):
        self.owner=owner;self.tasks={};self.lock=asyncio.Lock()
        with owner.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cloud_videos(id TEXT PRIMARY KEY,sid TEXT,endpoint TEXT,prompt TEXT,params TEXT,state TEXT,request_id TEXT,status_url TEXT,response_url TEXT,cancel_url TEXT,path TEXT,error TEXT,created REAL,finished REAL)')
            # Queued is known not to have been submitted; submitting without an ID is uncertain.
            db.execute("UPDATE cloud_videos SET state='unknown',error='Исход отправки неизвестен. Проверьте кабинет fal.ai; автоматической повторной отправки нет.' WHERE state IN ('queued','submitting') AND request_id=''")

    def row(self,identifier):
        with self.owner.db() as db:row=db.execute('SELECT * FROM cloud_videos WHERE id=?',(identifier,)).fetchone()
        return dict(row) if row else None

    def change(self,identifier,**fields):
        with self.owner.db() as db:db.execute('UPDATE cloud_videos SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),identifier))

    @staticmethod
    def public(row):
        return {k:row.get(k) for k in ('id','sid','endpoint','prompt','state','error','created','finished')}|{
            'parameters':json.loads(row['params']),
            **({'url':'/api/cloud/videos/'+row['id']+'/file'} if row['state']=='completed' else {})}

    @staticmethod
    def queue_url(value,request_id):
        parsed=urllib.parse.urlsplit(value)
        if parsed.scheme!='https' or parsed.netloc!='queue.fal.run' or parsed.query or parsed.fragment or not parsed.path.startswith('/fal-ai/') or '/requests/'+request_id not in parsed.path:
            raise ValueError('fal.ai вернул неожиданный адрес очереди. Повторная отправка не выполняется.')
        return value

    @staticmethod
    def media_url(value):
        parsed=urllib.parse.urlsplit(value);host=parsed.hostname or ''
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in {None,443} or not (
                host=='fal.media' or host.endswith('.fal.media') or host=='storage.googleapis.com'):
            raise ValueError('fal.ai вернул неподдерживаемый адрес видео.')
        return value

    def spawn(self,identifier,credential,submit=False):
        if identifier in self.tasks:return
        task=asyncio.create_task(self.run(identifier,credential,submit));self.tasks[identifier]=task
        task.add_done_callback(lambda done:self.tasks.pop(identifier,None))

    def image_path(self,value):
        from PIL import Image
        path=pathlib.Path(value).resolve()
        if not path.is_relative_to(self.owner.root.parent.resolve()) or not path.is_file() or not 1<=path.stat().st_size<=10*1024**2:raise ValueError('Исходное изображение должно быть в рабочем пространстве, не более 10 МБ.')
        with Image.open(path) as image:
            if image.format not in {'JPEG','PNG','BMP','WEBP'} or not all(360<=n<=2000 for n in image.size) or 'A' in image.getbands():raise ValueError('Для Wan 2.5 нужен непрозрачный JPEG, PNG, BMP или WEBP размером 360–2000 пикселей.')
            image.verify()
        return path

    async def restore(self,app=None):
        connection=self.owner.connections.get('fal',{})
        if not connection.get('enabled') or not connection.get('paid_consent'):return
        credential=await asyncio.to_thread(self.owner.vault.get,'fal')
        if not credential:return
        with self.owner.db() as db:rows=[dict(row) for row in db.execute("SELECT * FROM cloud_videos WHERE request_id<>'' AND state IN ('IN_QUEUE','IN_PROGRESS','downloading','cancel_requested','paused')")]
        for row in rows:self.spawn(row['id'],credential,False)

    async def status(self,request):
        with self.owner.db() as db:rows=[dict(row) for row in db.execute('SELECT * FROM cloud_videos ORDER BY created DESC LIMIT 20')]
        connection=self.owner.connections.get('fal',{})
        return web.json_response({'connected':bool(connection.get('enabled') and connection.get('paid_consent')),
            'models':VIDEO_MODELS,'usage':self.owner.usage('fal'),
            'current':next((self.public(row) for row in rows if row['state'] in ACTIVE or row['state']=='paused'),None),
            'history':[self.public(row) for row in rows]})

    async def submit(self,request):
        value=await request.json()
        async with self.lock:
            connection=self.owner.connections.get('fal',{})
            if not connection.get('enabled') or not connection.get('paid_consent'):raise ValueError('Сначала подключите fal.ai и разрешите платные запросы.')
            if value.get('confirm_charge') is not True:raise ValueError('Подтвердите платную генерацию перед отправкой в fal.ai.')
            identifier=str(value.get('input_id') or '');sid=str(value.get('sid') or '');prompt=str(value.get('prompt') or '').strip()
            if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',identifier) or not 1<=len(prompt)<=1500:raise ValueError('Введите описание видео до 1500 символов.')
            model=next((row for row in VIDEO_MODELS if row['id']==value.get('model')),None)
            if not model:raise ValueError('Выберите видеомодель из списка fal.ai.')
            parameters={name:str(value.get(name) or default) for name,default in [('duration','5'),('resolution','480p'),('aspect_ratio','16:9')]}
            if parameters['duration'] not in model['durations'] or parameters['resolution'] not in model['resolutions'] or parameters['aspect_ratio'] not in model['ratios']:raise ValueError('Неподдерживаемые параметры видео.')
            if model.get('image_input'):parameters['source_image']=str(self.image_path(str(value.get('source_image') or '')))
            elif value.get('source_image'):raise ValueError('Для исходного изображения выберите Image to Video.')
            params=json.dumps(parameters,sort_keys=True)
            prior=self.row(identifier)
            if prior:
                if (prior['sid'],prior['prompt'],prior['endpoint'],prior['params'])!=(sid,prompt,model['id'],params):raise ValueError('Идентификатор видео уже используется другим заданием.')
                return web.json_response(self.public(prior))
            with self.owner.db() as db:active=db.execute("SELECT 1 FROM cloud_videos WHERE state IN ('queued','submitting','IN_QUEUE','IN_PROGRESS','downloading','cancel_requested','paused') LIMIT 1").fetchone()
            if active:raise ValueError('Дождитесь завершения текущего видео fal.ai или запросите отмену.')
            if shutil.disk_usage(self.owner.root).free<1024**3:raise ValueError('Нужен минимум 1 ГБ свободного места для видео.')
            credential=await asyncio.to_thread(self.owner.vault.get,'fal')
            if not credential:raise ValueError('Подключите API-ключ fal.ai заново.')
            if sid:await self.owner.bridge.resume(sid)
            self.owner.reserve('fal')
            with self.owner.db() as db:db.execute('INSERT INTO cloud_videos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (identifier,sid,model['id'],prompt,params,'queued','','','','','','',time.time(),None))
            self.spawn(identifier,credential,True)
            return web.json_response(self.public(self.row(identifier)))

    async def run(self,identifier,credential,submit):
        headers={'Authorization':'Key '+credential['key']};row=self.row(identifier)
        try:
            async with ClientSession(timeout=ClientTimeout(total=75,connect=15,sock_read=60)) as http:
                if submit:
                    self.change(identifier,state='submitting')
                    body={'prompt':row['prompt'],**json.loads(row['params']),'enable_safety_checker':True,'enable_prompt_expansion':False}
                    if body.get('source_image'):
                        path=self.image_path(body.pop('source_image'));body.pop('aspect_ratio',None)
                        mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.bmp':'image/bmp','.webp':'image/webp'}.get(path.suffix.lower(),'image/png')
                        body['image_url']='data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()
                    # Exactly one billable POST. Transport failures remain unknown.
                    async with http.post('https://queue.fal.run/'+row['endpoint'],json=body,headers=headers,allow_redirects=False) as response:
                        if response.status not in {200,201,202}:
                            self.change(identifier,state='failed',error=self.owner.upstream_error(response.status,True),finished=time.time());return
                        result=await response.json()
                    request_id=str(result.get('request_id') or '')
                    if not re.fullmatch(r'[A-Za-z0-9_-]{8,120}',request_id):raise ValueError('fal.ai не вернул идентификатор. Проверьте кабинет перед новым запуском.')
                    # Persist the vendor ID before validating optional URLs, so recovery never resubmits.
                    self.change(identifier,request_id=request_id,state='IN_QUEUE')
                    urls={key:self.queue_url(str(result.get(key) or ''),request_id) for key in ('status_url','response_url','cancel_url')}
                    self.change(identifier,**urls);row=self.row(identifier)
                if not row.get('status_url'):raise ValueError('Адрес очереди отсутствует. Проверьте запрос в кабинете fal.ai.')
                deadline=time.monotonic()+1800
                while time.monotonic()<deadline:
                    if self.row(identifier)['state']=='cancelled':return
                    async with http.get(self.queue_url(row['status_url'],row['request_id']),headers=headers,allow_redirects=False) as response:
                        if response.status!=200:raise ValueError(self.owner.upstream_error(response.status,True))
                        state=await response.json()
                    status=state.get('status')
                    if self.row(identifier)['state']=='cancelled':return
                    if status=='COMPLETED':break
                    if status not in {'IN_QUEUE','IN_PROGRESS'}:raise ValueError('fal.ai вернул неизвестное состояние. Проверьте кабинет; повторного запуска нет.')
                    current=self.row(identifier)
                    if current['state']!='cancel_requested':self.change(identifier,state=status,error='')
                    await asyncio.sleep(5)
                else:
                    self.change(identifier,state='paused',error='Проверка очереди приостановлена. Запрос остаётся в fal.ai; можно продолжить проверку статуса.');return
                async with http.get(self.queue_url(row['response_url'],row['request_id']),headers=headers,allow_redirects=False) as response:
                    if response.status!=200:raise ValueError(self.owner.upstream_error(response.status,True))
                    result=await response.json()
                if self.row(identifier)['state']=='cancelled':return
                if not isinstance(result.get('video'),dict) or not result['video'].get('url'):raise ValueError('fal.ai не вернул видео. Проверьте результат в кабинете.')
                self.change(identifier,state='downloading',error='')
                folder=self.owner.root/'output/cloud-videos';folder.mkdir(parents=True,exist_ok=True)
                target=folder/(identifier+'.mp4');temporary=folder/(identifier+'.mp4.part');maximum=256*1024**2
                # No credentials are sent to media storage; redirects cannot send us elsewhere.
                async with http.get(self.media_url(result['video']['url']),allow_redirects=False) as response:
                    if response.status!=200 or int(response.headers.get('Content-Length','0'))>maximum:raise ValueError('Не удалось скачать видео или файл превышает 256 МБ.')
                    total=0
                    with temporary.open('wb') as stream:
                        async for chunk in response.content.iter_chunked(1024*1024):
                            total+=len(chunk)
                            if total>maximum:raise ValueError('Видео превышает ограничение 256 МБ.')
                            stream.write(chunk)
                with temporary.open('rb') as stream:signature=stream.read(4096)
                if b'ftyp' not in signature or total<64:raise ValueError('Сервис вернул файл, который не похож на MP4.')
                if self.row(identifier)['state']=='cancelled':return
                temporary.replace(target)
                self.change(identifier,state='completed',path=str(target),error='',finished=time.time())
                if row['sid']:
                    self.owner.artifact(row['sid'],str(target));await self.owner.bridge.broadcast({'type':'artifacts.changed','session_id':row['sid']})
        except asyncio.CancelledError:
            row=self.row(identifier)
            if row['state'] not in {'completed','cancelled','failed'}:
                self.change(identifier,state='paused' if row.get('request_id') else 'unknown',
                    error='Приложение остановлено. Статус отправленного запроса проверится при следующем запуске; повторной отправки нет.')
            raise
        except Exception as error:
            row=self.row(identifier)
            if row['state'] in {'completed','cancelled','failed'}:return
            message=str(error) if isinstance(error,ValueError) else 'Соединение прервано. Проверьте кабинет fal.ai; автоматической повторной отправки нет.'
            message=message.replace(credential['key'],'[REDACTED]')[:600]
            self.change(identifier,state='paused' if row.get('request_id') else 'unknown',error=message)

    async def detail(self,request):
        row=self.row(request.match_info['job'])
        if not row:raise web.HTTPNotFound()
        return web.json_response(self.public(row))

    async def resume(self,request):
        row=self.row(request.match_info['job'])
        if not row:raise web.HTTPNotFound()
        if not row.get('request_id') or row['state'] not in {'paused',*ACTIVE}:raise ValueError('Этот запрос нельзя повторно отправлять. Проверьте кабинет fal.ai.')
        connection=self.owner.connections.get('fal',{})
        if not connection.get('enabled') or not connection.get('paid_consent'):raise ValueError('Подключите исходный аккаунт fal.ai.')
        credential=await asyncio.to_thread(self.owner.vault.get,'fal')
        if not credential:raise ValueError('Подключите ключ fal.ai.')
        self.spawn(row['id'],credential,False)
        return web.json_response(self.public(row))

    async def cancel(self,request):
        row=self.row(request.match_info['job'])
        if not row:raise web.HTTPNotFound()
        if row['state'] not in ACTIVE|{'paused'}:return web.json_response(self.public(row))
        if not row.get('request_id') or not row.get('cancel_url'):raise ValueError('Отправка ещё не подтверждена. Проверьте состояние через несколько секунд.')
        credential=await asyncio.to_thread(self.owner.vault.get,'fal')
        if not credential:raise ValueError('Подключите ключ исходного аккаунта fal.ai.')
        async with ClientSession(timeout=ClientTimeout(total=25)) as http:
            async with http.put(self.queue_url(row['cancel_url'],row['request_id']),headers={'Authorization':'Key '+credential['key']},allow_redirects=False) as response:
                body=await response.json()
                if response.status==200 and body.get('status')=='OK':self.change(row['id'],state='cancelled',finished=time.time(),error='')
                elif response.status==202:self.change(row['id'],state='cancel_requested',error='Отмена запрошена. Уже начатая генерация может завершиться и быть оплачена.')
                elif response.status==400 and body.get('status')=='ALREADY_COMPLETED':self.spawn(row['id'],credential,False)
                else:raise ValueError(self.owner.upstream_error(response.status,True))
        return web.json_response(self.public(self.row(row['id'])))

    async def file(self,request):
        row=self.row(request.match_info['job'])
        if not row or row['state']!='completed':raise web.HTTPNotFound()
        path=pathlib.Path(row['path']).resolve()
        if not path.is_relative_to((self.owner.root/'output/cloud-videos').resolve()) or not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Disposition':'inline; filename="freedom-fal-video.mp4"'})

    async def close(self):
        tasks=list(self.tasks.values())
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)

    def register(self,app):
        app.router.add_get('/api/cloud/videos',self.status);app.router.add_post('/api/cloud/videos',self.submit)
        app.router.add_get('/api/cloud/videos/{job}',self.detail);app.router.add_get('/api/cloud/videos/{job}/file',self.file)
        app.router.add_post('/api/cloud/videos/{job}/resume',self.resume);app.router.add_post('/api/cloud/videos/{job}/cancel',self.cancel)
        app.on_startup.append(self.restore)
