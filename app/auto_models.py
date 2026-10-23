"""Per-chat orchestration over the canonical owner history. No agent/history replacement."""
import asyncio,contextlib,hashlib,json,os,pathlib,re,subprocess,sys,time,urllib.parse,uuid
from aiohttp import web,ClientSession,ClientTimeout,ClientError

ROLES=('planning','code','review','image','video')
class RequestView:
    def __init__(self,request,data,match=None):self.request,self.data=request,data;self.match_info=match or request.match_info
    async def json(self):return self.data
    def __getattr__(self,name):return getattr(self.request,name)

class AutoModels:
    def __init__(self,root,portable,db,cloud,workspace,bridge,videos,image_status,artifact):
        self.root,self.portable,self.db,self.cloud,self.workspace,self.bridge=root,portable,db,cloud,workspace,bridge
        self.videos,self.image_status,self.artifact=videos,image_status,artifact
        self.locks={};self.tasks={};self.processes={}
        with db() as conn:conn.executescript('''
          CREATE TABLE IF NOT EXISTS auto_models(sid TEXT PRIMARY KEY,alias TEXT UNIQUE,policy TEXT,role TEXT,last_user TEXT,last_model TEXT,manual_model TEXT,enabled INTEGER);
          CREATE TABLE IF NOT EXISTS auto_events(id INTEGER PRIMARY KEY,sid TEXT,role TEXT,model TEXT,detail TEXT,created REAL);
          CREATE TABLE IF NOT EXISTS auto_overrides(sid TEXT,role TEXT,model TEXT,PRIMARY KEY(sid,role));
          CREATE TABLE IF NOT EXISTS auto_jobs(id TEXT PRIMARY KEY,sid TEXT,request TEXT,state TEXT,result TEXT,error TEXT,created REAL,updated REAL);
        ''')
        with db() as conn:conn.execute("UPDATE auto_jobs SET state='unknown',error='Приложение перезапущено. Проверьте результат; повторной генерации нет.' WHERE state IN ('queued','running')")

    def row(self,sid):
        with self.db() as conn:row=conn.execute('SELECT * FROM auto_models WHERE sid=?',(sid,)).fetchone()
        if not row:return None
        value=dict(row);value['policy']=json.loads(value['policy']);return value

    def target(self,alias):
        with self.db() as conn:row=conn.execute('SELECT sid FROM auto_models WHERE alias=? AND enabled=1',(alias,)).fetchone()
        return {'id':alias,'remote_id':alias,'name':'Авто','provider_id':'auto','provider_name':'Freedom','kind':'cloud','context_length':65536,'vision':True,'paid':False,'auto_sid':row['sid']} if row else None

    def aliases(self):
        with self.db() as conn:rows=conn.execute('SELECT alias FROM auto_models WHERE enabled=1').fetchall()
        return [self.target(row['alias']) for row in rows]

    def catalog(self):
        rows=[{'id':self.portable.model_id(),'name':'Локальная модель','kind':'local','roles':['planning','code','review'],'paid':False,'vision':True,'available':True}]
        for row in self.cloud.models():
            if row.get('context_length',0)<65536:continue
            rows.append({**row,'roles':['planning','code','review'],'available':True})
        image=self.image_status();video=self.videos.snapshot()
        rows.append({'id':'image:local','name':image.get('model') or 'Локальные изображения','kind':'image','roles':['image'],'paid':False,'available':bool(image.get('ready'))})
        rows.append({'id':'video:local','name':video.get('model') or 'Локальное видео','kind':'video','roles':['video'],'paid':False,'available':bool(video.get('ready')),'image_input':False})
        if self.cloud.connections.get('cloudflare',{}).get('enabled'):
            rows.append({'id':'image:cloudflare','name':'FLUX.1 Schnell · Cloudflare','kind':'image','roles':['image'],'paid':False,'available':True})
        fal=self.cloud.connections.get('fal',{})
        if fal.get('enabled') and fal.get('paid_consent'):
            rows.append({'id':'video:fal','name':'Wan 2.5 · fal.ai','kind':'video','roles':['video'],'paid':True,'available':True,'image_input':True})
        return rows

    def defaults(self):
        return {'allowed':[row['id'] for row in self.catalog() if row['available'] and not row['paid']],
                'roles':{role:'auto' for role in ROLES},'allow_paid':False,'media_limit':5}

    def public(self,sid):
        row=self.row(sid)
        with self.db() as conn:
            events=[dict(x) for x in conn.execute('SELECT role,model,detail,created FROM auto_events WHERE sid=? ORDER BY id DESC LIMIT 12',(sid,))]
            jobs=[self.job_public(dict(x)) for x in conn.execute('SELECT * FROM auto_jobs WHERE sid=? ORDER BY created DESC LIMIT 10',(sid,))]
        catalog=self.catalog();current=next((x for x in catalog if row and x['id']==row['last_model']),None)
        return {'enabled':bool(row and row['enabled']),'policy':row['policy'] if row else self.defaults(),
                'role':row['role'] if row else 'planning','current':current,'events':events,'jobs':jobs}

    async def event(self,sid,role,model,detail):
        with self.db() as conn:
            conn.execute('INSERT INTO auto_events(sid,role,model,detail,created) VALUES(?,?,?,?,?)',(sid,role,model,detail[:1600],time.time()))
            conn.execute('DELETE FROM auto_events WHERE sid=? AND id NOT IN (SELECT id FROM auto_events WHERE sid=? ORDER BY id DESC LIMIT 200)',(sid,sid))
        await self.bridge.broadcast({'type':'auto.changed','session_id':sid,'auto_route':self.public(sid)})

    async def status(self,request):
        sid=request.match_info['sid'];snapshot=await self.bridge.resume(sid)
        return web.json_response({**self.public(sid),'models':self.catalog(),'running':bool(snapshot.get('running') or snapshot.get('pending') or any(self.job(j).get('sid')==sid for j in self.tasks))})

    async def configure(self,request):
        sid=request.match_info['sid'];data=await request.json()
        async with self.locks.setdefault(sid,asyncio.Lock()):
            snapshot=await self.bridge.resume(sid)
            if snapshot.get('running') or snapshot.get('pending'):raise ValueError('Измените настройки Авто после завершения работы и очереди.')
            if any(self.job(j).get('sid')==sid for j in self.tasks):raise ValueError('Дождитесь завершения медиагенерации этого чата.')
            previous=self.row(sid);enabled=data.get('enabled') is True
            policy=data.get('policy') or (previous['policy'] if previous else self.defaults())
            if not isinstance(policy,dict):raise ValueError('Некорректные настройки Авто.')
            catalog={row['id']:row for row in self.catalog()};allowed=policy.get('allowed',[]);roles=policy.get('roles',{})
            if not enabled:
                allowed=[x for x in allowed if x in catalog];roles={role:(value if value=='auto' or value in allowed else 'auto') for role,value in roles.items()}
            if not isinstance(allowed,list) or len(allowed)>100 or any(not isinstance(x,str) or x not in catalog for x in allowed):raise ValueError('Выберите доступные модели из списка.')
            allow_paid=policy.get('allow_paid') is True
            if any(catalog[x]['paid'] for x in allowed) and not allow_paid:raise ValueError('Платные модели требуют отдельного разрешения в Авто.')
            if enabled and not any(catalog[x]['kind'] in {'cloud','local'} for x in allowed):raise ValueError('Разрешите хотя бы одну текстовую модель.')
            if not isinstance(roles,dict) or any(role not in ROLES for role in roles):raise ValueError('Неизвестная роль модели.')
            for role,value in roles.items():
                if value!='auto' and (value not in allowed or role not in catalog[value]['roles']):raise ValueError('Модель для роли должна быть разрешена и поддерживать эту задачу.')
            limit=policy.get('media_limit',5)
            if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Лимит генераций: от 1 до 100.')
            policy={'allowed':list(dict.fromkeys(allowed)),'roles':{role:roles.get(role,'auto') for role in ROLES},'allow_paid':allow_paid,'media_limit':limit}
            alias='freedom-auto-'+hashlib.sha256(sid.encode()).hexdigest()[:20]
            manual=previous['manual_model'] if previous else (snapshot.get('info') or {}).get('model') or self.portable.model_id()
            with self.db() as conn:conn.execute('INSERT OR REPLACE INTO auto_models VALUES(?,?,?,?,?,?,?,?)',
                (sid,alias,json.dumps(policy),previous['role'] if previous else 'planning',previous['last_user'] if previous else '',previous['last_model'] if previous else '',manual,1))
            selected=alias if enabled else manual
            if not enabled and selected!=self.portable.model_id() and not self.cloud.target(selected):selected=self.portable.model_id()
            try:
                result=await self.workspace.model_set(RequestView(request,{'model':selected,'confirm':data.get('confirm'),'force':True},{'sid':sid}))
                value=json.loads(result.body)
                if value.get('status')=='confirmation_required':
                    self.restore_row(sid,previous);return result
            except Exception:self.restore_row(sid,previous);raise
            with self.db() as conn:conn.execute('UPDATE auto_models SET enabled=? WHERE sid=?',(int(enabled),sid))
            await self.event(sid,'planning',selected,'Авто включено' if enabled else 'Выбрана ручная модель')
            return web.json_response({'ok':True,**self.public(sid)})

    def restore_row(self,sid,row):
        with self.db() as conn:
            conn.execute('DELETE FROM auto_models WHERE sid=?',(sid,))
            if row:conn.execute('INSERT INTO auto_models VALUES(?,?,?,?,?,?,?,?)',tuple(json.dumps(row[k]) if k=='policy' else row[k] for k in ('sid','alias','policy','role','last_user','last_model','manual_model','enabled')))

    def manual(self,sid):
        with self.db() as conn:conn.execute('UPDATE auto_models SET enabled=0 WHERE sid=?',(sid,))

    def pick(self,row,role,requested=None,vision=False,source_image=False):
        policy=row['policy'];choices=[x for x in self.catalog() if x['available'] and x['id'] in policy['allowed'] and role in x['roles'] and (policy['allow_paid'] or not x['paid'])]
        if vision:choices=[x for x in choices if x.get('vision')]
        if source_image:choices=[x for x in choices if x.get('image_input')]
        if requested is None:
            requested=policy['roles'].get(role,'auto')
            if requested=='auto':
                with self.db() as conn:override=conn.execute('SELECT model FROM auto_overrides WHERE sid=? AND role=?',(row['sid'],role)).fetchone()
                if override:requested=override['model']
        if policy['roles'].get(role,'auto')!='auto' and requested not in {'auto',policy['roles'][role]}:raise ValueError('Модель роли закреплена владельцем.')
        if policy['roles'].get(role,'auto')!='auto':requested=policy['roles'][role]
        if requested!='auto':
            result=next((x for x in choices if x['id']==requested),None)
            if not result:raise ValueError('Выбранная модель недоступна или не разрешена для этой роли.')
            return result
        if not choices:raise ValueError('Нет разрешённой модели для этапа '+role+'. Подключите модель или измените настройки Авто.')
        def score(model):
            name=model['name'].lower();provider=model.get('provider_id','');value=0
            if model['kind']=='local':value+=95 if role=='code' else 35
            if provider=='gemini':value+=85 if role=='planning' else 45
            if provider=='openrouter':value+=55
            if provider=='groq':value-=20 # Small free input quota is unsuitable for long owner prompts.
            if any(word in name for word in ('coder','coding','code','qwen')) and role=='code':value+=30
            if any(word in name for word in ('nemotron','reason','sonnet','opus')) and role in {'planning','review'}:value+=20
            if model['id']=='image:cloudflare':value+=70
            if model['id']=='image:local':value+=50
            if model['id']=='video:local':value+=50
            if model['paid']:value-=5
            return value
        return max(choices,key=score)

    @staticmethod
    def classify(messages):
        content=next((m.get('content','') for m in reversed(messages) if m.get('role')=='user'),'')
        text=content if isinstance(content,str) else ' '.join(p.get('text','') for p in content if p.get('type')=='text')
        lower=text.lower()
        role='review' if re.search(r'проверь|ошибк|ревью|review|debug|test',lower) else 'code' if re.search(r'код|программ|сайт|приложени|code|implement|website',lower) else 'planning'
        return role,hashlib.sha256(text.encode()).hexdigest()

    def instructions(self,row,selected):
        command=subprocess.list2cmdline([sys.executable,'-B',str(self.root/'agent-model-control.py'),'--session',row['sid']])
        available=[{'id':x['id'],'name':x['name'],'roles':x['roles'],'paid':x['paid'],'image_input':x.get('image_input',False)} for x in self.catalog() if x['available'] and x['id'] in row['policy']['allowed']]
        return ('FREEDOM AUTO: You are the SAME agent in one canonical chat. All user messages, files, goals, tools and project memory remain shared. '
          'Choose specialized models between stages; do not create another chat or lose the owner goal. Current role/model: '+row['role']+'/'+selected['name']+'. '
          'Selection is a capability heuristic, not a benchmark. Allowed models: '+json.dumps(available,ensure_ascii=False)+'. '
          'Use your existing terminal tool to control routing: '+command+' --action select --role planning|code|review --model auto (or an allowed exact id). '
          'A role change applies to your NEXT model request, including the rest of the same turn; the full conversation stays. '
          'For multi-stage coding: plan, select code, implement, then select review and verify against the owner goal. Do not switch without a task reason or bounce in a loop. '
          'For advertising: write a script and shot list; then create actual image/video files when requested. To generate, first write the prompt to a UTF-8 file under A:/CodexProjects, then use '+command+
          ' --action generate --role image|video --prompt-file <absolute-path> --input-id <unique-uuid>. Optional --source-image <absolute-path> creates image-to-video through an allowed capable model; local Wan is text-to-video only. '
          'The command starts a durable job, never silently resubmits it. Poll with --action status --job <id>. Reuse the SAME input-id after a lost response. '
          'Native terminal background completion is supported. Never announce a media result until state=completed and a real output path is returned. If a tool is unavailable, explain the missing capability instead of fabricating a file. '
          'Agent-initiated model changes and media require Full access; otherwise ask the owner to select the role/model or use the media panel. Paid use requires the separate Auto permission and the provider connection consent. '
          'Never read provider API keys, install models, change the pool or enable paid access yourself. User steering and Stop take precedence over the goal. Respond in the user language.')

    @staticmethod
    def request_messages(messages,instructions):
        """One system message for strict local templates; never edit stored history.

        Keep the original system prefix intact and append this request's Auto
        guidance. A second system message is rejected by Qwen chat templates.
        """
        messages=list(messages)
        if messages and messages[0].get('role')=='system':
            first=dict(messages[0]);content=first.get('content')
            if isinstance(content,list):
                first['content']=[*content,{'type':'text','text':instructions}]
            else:
                first['content']=(content or '')+'\n\n'+instructions
            return [first,*messages[1:]]
        return [{'role':'system','content':instructions},*messages]

    async def chat(self,request,target,incoming):
        sid=target['auto_sid'];row=self.row(sid);role,fingerprint=self.classify(incoming.get('messages',[]))
        if row['last_user']!=fingerprint:
            with self.db() as conn:conn.execute('UPDATE auto_models SET role=?,last_user=? WHERE sid=?',(role,fingerprint,sid))
            row=self.row(sid)
        vision=any(isinstance(m.get('content'),list) and any(p.get('type')=='image_url' for p in m['content']) for m in incoming.get('messages',[]))
        selected=self.pick(row,row['role'],vision=vision)
        if selected['id']!=row['last_model']:
            with self.db() as conn:conn.execute('UPDATE auto_models SET last_model=? WHERE sid=?',(selected['id'],sid))
            await self.event(sid,row['role'],selected['id'],'Выбор модели для текущего этапа')
        body={**incoming,'model':selected['id'],'messages':self.request_messages(incoming.get('messages',[]),self.instructions(row,selected))}
        if selected['kind']=='cloud':
            result=await self.cloud.chat(RequestView(request,body))
            if result.status in {401,402,403,429,503} and not selected['paid'] and self.portable.model_id() in row['policy']['allowed'] and row['policy']['roles'].get(row['role'],'auto')=='auto':
                selected=next(x for x in self.catalog() if x['id']==self.portable.model_id());body['model']=selected['id']
                with self.db() as conn:conn.execute('UPDATE auto_models SET last_model=? WHERE sid=?',(selected['id'],sid))
                await self.event(sid,row['role'],selected['id'],'Бесплатный API недоступен; продолжаем локально')
                return await self.local_chat(request,target,body)
            self.cloud.calls[target['id']]=self.cloud.calls.get(selected['id'],{})
            return result
        return await self.local_chat(request,target,body)

    async def local_chat(self,request,target,body):
        origin=urllib.parse.urlsplit(self.portable.model_url())
        if origin.scheme!='http' or origin.hostname not in {'127.0.0.1','localhost','::1'}:raise ValueError('Авто требует локальный адрес модели.')
        # Media can temporarily lease the GPU. Keep the UI responsive and never generate the job again.
        deadline=time.monotonic()+3500
        while any(not task.done() for job,task in self.tasks.items() if self.job(job).get('local')):
            if time.monotonic()>deadline:raise ValueError('Локальный медиарендер ещё работает. Результат сохранится в чате.')
            await asyncio.sleep(1)
        started=time.monotonic();tokens=0
        try:
            async with ClientSession(timeout=ClientTimeout(total=900,connect=15,sock_read=180),read_bufsize=1024*1024) as http:
                async with http.post(self.portable.model_url()+'/chat/completions',json=body,headers={'Authorization':'Bearer local'},allow_redirects=False) as upstream:
                    if upstream.status!=200:return web.json_response({'error':{'message':'Локальная модель сейчас недоступна.','type':'local_unavailable'}},status=400)
                    if not body.get('stream'):
                        value=await upstream.json();tokens=(value.get('usage') or {}).get('completion_tokens',0);return web.json_response(value)
                    response=web.StreamResponse(headers={'Content-Type':'text/event-stream','Cache-Control':'no-store'});await response.prepare(request)
                    async for line in upstream.content:
                        if line.startswith(b'data: '):
                            with contextlib.suppress(ValueError,TypeError):tokens=max(tokens,(json.loads(line[6:]).get('usage') or {}).get('completion_tokens',0))
                        await response.write(line)
                    await response.write_eof();return response
        except (ClientError,asyncio.TimeoutError,ConnectionError):
            if 'response' in locals():return response
            return web.json_response({'error':{'message':'Связь с локальной моделью прервалась.','type':'local_unavailable'}},status=400)
        finally:
            elapsed=max(.001,time.monotonic()-started);self.cloud.calls[target['id']]={'output_tokens':tokens,'seconds':elapsed,'tokens_per_second':round(tokens/elapsed,1) if tokens else None,'time':time.time()}

    def job(self,identifier):
        with self.db() as conn:row=conn.execute('SELECT * FROM auto_jobs WHERE id=?',(identifier,)).fetchone()
        if not row:return {}
        value=dict(row);value.update(json.loads(value['request']));return value

    @staticmethod
    def job_public(row):
        return {k:row.get(k) for k in ('id','state','error','created','updated')}|{'result':json.loads(row.get('result') or '{}')}

    async def control(self,request):
        if not self.cloud.authorize(request):raise web.HTTPForbidden()
        sid=request.match_info['sid'];data=await request.json();row=self.row(sid)
        if not row or not row['enabled']:raise ValueError('Авто не включено для этого чата.')
        action=data.get('action')
        if action=='status':
            job=self.job(str(data.get('job') or ''))
            if not job or job['sid']!=sid:raise ValueError('Задание не найдено в этом чате.')
            return web.json_response(self.job_public(job))
        snapshot=await self.bridge.resume(sid)
        if not (snapshot.get('info') or {}).get('yolo'):raise ValueError('Для действий агента в Авто включите Полный доступ. Настройки владельца не менялись.')
        role=data.get('role')
        if role not in ROLES:raise ValueError('Неизвестная роль модели.')
        selected=self.pick(row,role,data.get('model'),source_image=bool(data.get('source_image')))
        if action=='select':
            if role not in {'planning','code','review'}:raise ValueError('Для изображений и видео используйте generate.')
            with self.db() as conn:
                conn.execute('UPDATE auto_models SET role=?,last_model=? WHERE sid=?',(role,selected['id'],sid))
                conn.execute('INSERT OR REPLACE INTO auto_overrides VALUES(?,?,?)',(sid,role,data.get('model') or 'auto'))
            await self.event(sid,role,selected['id'],'Агент выбрал модель для следующего этапа')
            return web.json_response({'ok':True,'role':role,'model':selected['id'],'name':selected['name'],'same_chat':True})
        if action!='generate' or role not in {'image','video'}:raise ValueError('Неизвестное действие Авто.')
        identifier=str(data.get('input_id') or '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',identifier):raise ValueError('Нужен постоянный input-id задания.')
        prompt=str(data.get('prompt') or '').strip()
        if not 1<=len(prompt)<=1500:raise ValueError('Описание: от 1 до 1500 символов.')
        jobdata={'role':role,'model':selected['id'],'prompt':prompt,'source_image':str(data.get('source_image') or ''),'local':selected['id'].endswith(':local')}
        raw=json.dumps(jobdata,sort_keys=True)
        async with self.locks.setdefault(sid,asyncio.Lock()):
            prior=self.job(identifier)
            if prior:
                if prior['sid']!=sid or prior['request']!=raw:raise ValueError('input-id уже относится к другому заданию.')
                return web.json_response(self.job_public(prior))
            with self.db() as conn:count=conn.execute('SELECT COUNT(*) FROM auto_jobs WHERE sid=?',(sid,)).fetchone()[0]
            if count>=row['policy']['media_limit']:raise ValueError('Достигнут лимит медиагенераций Авто. Изменить его может владелец в настройках чата.')
            if jobdata['local']:
                live=await self.bridge.rpc('session.list',scope='live',limit=200)
                if any(x.get('running') and (x.get('session_id') or x.get('id'))!=sid for x in live.get('sessions',[])):raise ValueError('GPU нужен другому работающему чату. Дождитесь его завершения или выберите облачный генератор.')
            with self.db() as conn:conn.execute('INSERT INTO auto_jobs VALUES(?,?,?,?,?,?,?,?)',(identifier,sid,raw,'queued','{}','',time.time(),time.time()))
            task=asyncio.create_task(self.generate(identifier,request));self.tasks[identifier]=task;task.add_done_callback(lambda done:self.tasks.pop(identifier,None))
            await self.event(sid,role,selected['id'],'Начат этап генерации медиа')
            return web.json_response(self.job_public(self.job(identifier)))

    async def generate(self,identifier,request):
        job=self.job(identifier);sid=job['sid'];result={}
        def update(state,**fields):
            with self.db() as conn:conn.execute('UPDATE auto_jobs SET state=?,result=?,error=?,updated=? WHERE id=?',(state,json.dumps(fields.get('result',{})),fields.get('error',''),time.time(),identifier))
        try:
            update('running')
            if job['model']=='image:cloudflare':
                receipt=await self.cloud.image_submit(RequestView(request,{'sid':sid,'prompt':job['prompt'],'input_id':identifier}))
                for _ in range(210):
                    with self.db() as conn:row=dict(conn.execute('SELECT * FROM cloud_images WHERE id=?',(identifier,)).fetchone())
                    if row['state']=='completed':result={'path':row['path']};break
                    if row['state'] in {'failed','unknown'}:raise ValueError(row['error'])
                    await asyncio.sleep(1)
                else:raise ValueError('Изображение ещё обрабатывается. Проверьте историю API-изображений; повторной отправки нет.')
            elif job['model']=='video:fal':
                from fal_video import VIDEO_MODELS
                model=next(x for x in VIDEO_MODELS if bool(x.get('image_input'))==bool(job['source_image']))
                receipt=await self.cloud.fal.submit(RequestView(request,{'sid':sid,'prompt':job['prompt'],'input_id':identifier,'model':model['id'],'confirm_charge':True,'source_image':job['source_image']}))
                for _ in range(1900):
                    row=self.cloud.fal.row(identifier)
                    if row['state']=='completed':result={'path':row['path']};break
                    if row['state'] in {'failed','cancelled','unknown','paused'}:raise ValueError(row.get('error') or 'Проверка очереди fal.ai приостановлена.')
                    await asyncio.sleep(1)
                else:raise ValueError('Проверьте очередь fal.ai. Новый запрос не создавался.')
            elif job['model']=='image:local':
                folder=self.root/'data/image-requests';folder.mkdir(exist_ok=True);path=folder/(identifier+'.json');path.write_text(json.dumps({'prompt':job['prompt']}),encoding='utf-8')
                process=await asyncio.create_subprocess_exec(sys.executable,'-B',str(self.root/'generate-image-request.py'),str(path),cwd=self.root,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.processes[identifier]=process
                # GPU helpers own restoration. Retain the process across a UI disconnect.
                stdout,stderr=await process.communicate()
                self.processes.pop(identifier,None)
                if process.returncode:raise ValueError('Локальный генератор завершился с ошибкой. Повторной генерации нет.')
                path=self.root/'output/images'/identifier/'image.png'
                if not path.is_file():raise ValueError('Генератор не вернул изображение.')
                result={'path':str(path)}
            else:
                receipt=self.videos.start({'prompt':job['prompt'],'session_id':sid,'width':512,'height':288,'frames':33,'steps':20})
                for _ in range(3550):
                    row=self.videos.current
                    if row.get('id')!=receipt['id']:raise ValueError('Состояние локального видео изменилось.')
                    if row['state']=='complete':result={'path':row['output']};break
                    if row['state'] in {'error','cancelled','interrupted'}:raise ValueError(row.get('error') or 'Видео остановлено.')
                    await asyncio.sleep(1)
                else:raise ValueError('Проверьте историю локального видео.')
            asset=self.artifact(sid,result['path']);result.update(asset=asset)
            update('completed',result=result);await self.bridge.broadcast({'type':'artifacts.changed','session_id':sid})
            await self.event(sid,job['role'],job['model'],'Готовый файл: '+result['path'])
        except asyncio.CancelledError:
            update('unknown',error='Ожидание остановлено. Проверьте историю генератора; автоматической повторной отправки нет.');raise
        except Exception as error:
            update('failed',error=str(error)[:500] if isinstance(error,ValueError) else 'Не удалось завершить этап. Повторной генерации нет.')
            await self.event(sid,job['role'],job['model'],'Этап остановлен. Результат и причина сохранены.')

    async def clone(self,parent,child,request):
        row=self.row(parent)
        if not row or not row['enabled'] or self.row(child):return
        original=dict(row);row['sid']=child;row['alias']='freedom-auto-'+hashlib.sha256(child.encode()).hexdigest()[:20];row['last_user']='';row['last_model']=''
        self.restore_row(child,row)
        try:
            result=await self.workspace.model_set(RequestView(request,{'model':row['alias']},{'sid':child}))
            if json.loads(result.body).get('status')=='confirmation_required':raise ValueError('Подтвердите Авто в новой ветке.')
        except Exception:
            self.manual(child)
            # Preserve a usable independent route even if the optional switch is unavailable.
            await self.workspace.model_set(RequestView(request,{'model':original['manual_model']},{'sid':child}))

    async def close(self):
        tasks=list(self.tasks.values())
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)

    async def stop(self,sid,request):
        with self.db() as conn:rows=[dict(x) for x in conn.execute("SELECT * FROM auto_jobs WHERE sid=? AND state IN ('queued','running')",(sid,))]
        for row in rows:
            job=self.job(row['id'])
            if job['model']=='video:local':self.videos.cancel();continue
            if job['model']=='image:local':
                process=self.processes.get(row['id'])
                if process and process.returncode is None:
                    import psutil
                    with contextlib.suppress(psutil.Error):
                        for child in psutil.Process(process.pid).children(recursive=True):
                            with contextlib.suppress(psutil.Error):child.terminate()
                # Keep the helper alive so its finally block restores the code model.
                continue
            if job['model']=='video:fal':
                with contextlib.suppress(Exception):await self.cloud.fal.cancel(RequestView(request,{}, {'job':row['id']}))
            task=self.tasks.get(row['id'])
            if task:task.cancel()
        if rows:await self.event(sid,'review','','Остановка владельцем. Проверьте историю уже отправленных генераций.')

    def register(self,app):
        app.router.add_get('/api/sessions/{sid}/auto',self.status);app.router.add_post('/api/sessions/{sid}/auto',self.configure)
        app.router.add_post('/internal/auto/{sid}/control',self.control)
