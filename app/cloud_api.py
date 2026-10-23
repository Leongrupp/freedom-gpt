"""Optional cloud routes with separate free and explicitly authorized paid providers."""
from __future__ import annotations
import asyncio,base64,contextlib,datetime,hashlib,io,json,os,pathlib,re,secrets,threading,time,uuid
from decimal import Decimal,InvalidOperation
from aiohttp import web,ClientSession,ClientTimeout,ClientError
from cloud_catalog import PROVIDERS,UNAVAILABLE,CHECKED
from cloud_vault import CloudVault
from paid_responses import ResponsesAdapter
from fal_video import FalVideos


class CloudAPI:
    def __init__(self,root,portable,db,bridge,artifact):
        self.root,self.portable,self.db,self.bridge,self.artifact=root,portable,db,bridge,artifact
        self.vault=CloudVault(root);self.lock=threading.RLock();self.connect_lock=asyncio.Lock();self.image_lock=asyncio.Lock()
        self.connections=portable.read(root/'data/cloud-connections.json',{})
        # Upgrade the original Groq records that mistook the TPM quota for context.
        # Keep credentials, aliases, connection consent and all user fields intact.
        migrated=False
        groq_windows={row['remote_id']:row['context_length'] for row in PROVIDERS['groq']['models']}
        for row in self.connections.get('groq',{}).get('models',[]):
            if row.get('context_length')==8192 and row.get('remote_id') in groq_windows:
                row['context_length']=groq_windows[row['remote_id']];migrated=True
        if migrated:portable.write(root/'data/cloud-connections.json',self.connections)
        for connection in self.connections.values():
            if connection.get('storage')=='session':connection['enabled']=False
        self.catalog=None;self.catalog_time=0;self.catalog_lock=asyncio.Lock()
        self.calls={};self.image_tasks=set()
        self.auto=None
        self.responses=ResponsesAdapter(self);self.fal=FalVideos(self)
        self.proxy_key=portable.read(root/'data/cloud-proxy.json',{}).get('key')
        if not self.proxy_key:
            self.proxy_key=secrets.token_urlsafe(40);portable.write(root/'data/cloud-proxy.json',{'key':self.proxy_key})
        with db() as c:c.executescript('''
        CREATE TABLE IF NOT EXISTS cloud_usage(provider TEXT,day TEXT,requests INTEGER DEFAULT 0,PRIMARY KEY(provider,day));
        CREATE TABLE IF NOT EXISTS cloud_images(id TEXT PRIMARY KEY,provider TEXT,prompt TEXT,sid TEXT,state TEXT,path TEXT,error TEXT,created REAL,finished REAL);
        ''')
        # A lost server process must not silently resubmit a possibly accepted generation.
        with db() as c:c.execute("UPDATE cloud_images SET state='unknown',error='Приложение перезапущено. Исход запроса неизвестен; автоматического повтора не было.' WHERE state IN ('queued','running')")

    def proxy_url(self):return f"http://127.0.0.1:{self.portable.config()['ui_port']}/cloud/v1"

    @staticmethod
    def alias(provider,remote):return 'freedom-api-'+provider+'-'+hashlib.sha256(remote.encode()).hexdigest()[:12]

    def target(self,model):
        if self.auto and str(model or '').startswith('freedom-auto-'):return self.auto.target(model)
        for provider,connection in self.connections.items():
            if not connection.get('enabled') or provider not in PROVIDERS or PROVIDERS[provider]['kind']!='chat':continue
            if PROVIDERS[provider].get('billing')=='paid' and not connection.get('paid_consent'):continue
            for row in connection.get('models',[]):
                if row['id']==model:return {**row,'provider_id':provider,'provider_name':PROVIDERS[provider]['name'],'kind':'cloud','paid':PROVIDERS[provider].get('billing')=='paid'}
        return None

    def models(self):
        return [{**row,'provider_id':p,'provider_name':PROVIDERS[p]['name'],'kind':'cloud','paid':PROVIDERS[p].get('billing')=='paid'}
                for p,c in self.connections.items() if c.get('enabled') and p in PROVIDERS and PROVIDERS[p]['kind']=='chat'
                and (PROVIDERS[p].get('billing')!='paid' or c.get('paid_consent')) for row in c.get('models',[])]

    def usage(self,provider):
        day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        with self.db() as c:row=c.execute('SELECT requests FROM cloud_usage WHERE provider=? AND day=?',(provider,day)).fetchone()
        cap=PROVIDERS[provider]['daily_cap']
        if PROVIDERS[provider].get('billing')=='paid':cap=self.connections.get(provider,{}).get('request_limit',cap)
        return {'used':row[0] if row else 0,'cap':cap,'reset':'00:00 UTC'}

    def reserve(self,provider):
        day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        cap=self.usage(provider)['cap']
        with self.lock,self.db() as c:
            c.execute('BEGIN IMMEDIATE');c.execute('INSERT OR IGNORE INTO cloud_usage VALUES(?,?,0)',(provider,day))
            row=c.execute('SELECT requests FROM cloud_usage WHERE provider=? AND day=?',(provider,day)).fetchone()
            if row[0]>=cap:raise ValueError('Достигнут дневной лимит приложения для этого API. Дождитесь 00:00 UTC или выберите локальную модель.')
            c.execute('UPDATE cloud_usage SET requests=requests+1 WHERE provider=? AND day=?',(provider,day))

    def sync_aliases(self):
        """Append only this feature's aliases, preserving the configured default and other settings."""
        import hermes_yaml as yaml
        path=self.portable.HOME/'config.yaml'
        with self.lock:
            original=path.read_text(encoding='utf-8-sig');cfg=yaml.safe_load(original) or {}
            aliases=cfg.setdefault('model_aliases',{})
            local='freedom-local-runtime'
            expected={'model':self.portable.model_id(),'provider':'custom','base_url':self.portable.model_url(),'api_key':'local'}
            if local in aliases and {key:value for key,value in aliases[local].items() if key!='context_length'}!=expected:raise ValueError('Имя локального маршрута уже занято другой настройкой.')
            expected['context_length']=self.portable.context_size()
            aliases[local]=expected
            from library import library
            for row in library.session_models():
                aliases[row['id']]={'model':row['id'],'provider':'custom','base_url':self.portable.model_url(),'api_key':'local'}
                if row.get('context_length'):aliases[row['id']]['context_length']=row['context_length']
            for row in self.models()+(self.auto.aliases() if self.auto else []):
                aliases[row['id']]={'model':row['id'],'provider':'custom','base_url':self.proxy_url(),'api_key':self.proxy_key}
                if row.get('context_length'):aliases[row['id']]['context_length']=row['context_length']
            model=cfg.get('model',{})
            if isinstance(model,dict) and model.get('default')==self.portable.model_id() and str(model.get('base_url','')).rstrip('/')==self.portable.model_url().rstrip('/'):
                old_context=model.get('context_length');model['context_length']=self.portable.context_size()
                for provider in (cfg.get('providers') or {}).values():
                    if not isinstance(provider,dict) or str(provider.get('base_url','')).rstrip('/')!=self.portable.model_url().rstrip('/'):continue
                    for name,value in (provider.get('models') or {}).items():
                        if name==self.portable.model_id() and isinstance(value,dict):value['context_length']=self.portable.context_size()
                # Migrate only the original app-generated 32K compression cap.
                # User-defined caps and the configured compression ratio survive.
                compression=cfg.get('compression',{})
                if old_context==65536 and isinstance(compression,dict) and compression.get('threshold_tokens')==32768 and compression.get('threshold',.5)==.5:
                    compression.pop('threshold_tokens',None)
            updated=yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False)
            if original==updated:return
            archive=self.root/'archive/cloud-api-config';archive.mkdir(parents=True,exist_ok=True)
            backup=archive/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.yaml');backup.write_text(original,encoding='utf-8')
            temp=path.with_name('cloud-config-'+uuid.uuid4().hex+'.new')
            with temp.open('w',encoding='utf-8') as stream:stream.write(updated);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,path)

    async def get_catalog(self,force=False):
        if self.catalog is not None and not force and time.monotonic()-self.catalog_time<300:return self.catalog
        async with self.catalog_lock:
            if self.catalog is not None and not force and time.monotonic()-self.catalog_time<300:return self.catalog
            async with ClientSession(timeout=ClientTimeout(total=18)) as http:
                async with http.get(PROVIDERS['openrouter']['base']+'/models',allow_redirects=False) as r:
                    if r.status!=200:raise ValueError('Каталог бесплатных моделей OpenRouter сейчас недоступен. Повторите позже.')
                    body=await r.json()
            result=[]
            for row in body.get('data',[]):
                remote=row.get('id','');pricing=row.get('pricing') or {};parameters=row.get('supported_parameters') or []
                try:zero=all(Decimal(str(pricing.get(k,'-1')))==0 for k in ['prompt','completion']) and all(Decimal(str(v))==0 for k,v in pricing.items() if k in {'request','image','web_search','internal_reasoning'})
                except (InvalidOperation,TypeError,ValueError):zero=False
                if not remote.endswith(':free') or not zero or 'tools' not in parameters:continue
                if (row.get('architecture') or {}).get('output_modalities')!=['text']:continue
                context=min(65536,int(row.get('context_length') or 0))
                if context<16384:continue
                result.append({'remote_id':remote,'name':str(row.get('name') or remote)[:150],'context_length':context,
                               'vision':'image' in ((row.get('architecture') or {}).get('input_modalities') or []),'parameters':parameters})
            self.catalog=result;self.catalog_time=time.monotonic()
            # Public metadata only; useful to inspect the provider list without credentials.
            self.portable.write(self.root/'.cache/openrouter-free-models.json',{'checked':time.time(),'models':result})
            return result

    async def status(self,request):
        cards=[]
        for provider,card in PROVIDERS.items():
            public={k:v for k,v in card.items() if k not in {'base','models','daily_cap'}}
            connection=self.connections.get(provider,{})
            cards.append({**public,'id':provider,'connected':bool(connection.get('enabled')),'models':connection.get('models',[]),'storage':connection.get('storage'),'usage':self.usage(provider)})
        return web.json_response({'providers':cards,'unavailable':UNAVAILABLE,'checked':CHECKED,'secret_storage':'Windows DPAPI' if os.name=='nt' else 'session','default_model':self.portable.model_id()})

    async def refresh(self,request):
        rows=await self.get_catalog(True)
        return web.json_response({'count':len(rows),'models':rows,'checked':time.time()})

    @staticmethod
    def upstream_error(status,paid=False):
        if paid:
            if status==401:return 'API отклонил ключ. Проверьте ключ выбранного провайдера.'
            if status==402:return 'Провайдер требует доступный баланс API. Проверьте кабинет и тариф; приложение не пополняет баланс.'
            if status==403:return 'Провайдер отказал в доступе. Проверьте разрешения ключа, модель и регион.'
            if status==429:return 'Провайдер ограничил частоту или квоту API. Автоматического перехода к другому платному сервису нет.'
            if status in {400,413,422}:return 'Платный API отклонил параметры или контекст. Проверьте модель и размер запроса.'
            return 'Платный API сейчас недоступен. Автоматического перехода к другому сервису нет.'
        if status==401:return 'API отклонил ключ. Создайте или вставьте действующий ключ в разделе «Подключить по API».'
        if status==402:return 'Бесплатный доступ недоступен. Приложение не пополняет баланс и не переключается на платную модель.'
        if status==403:return 'API отказал в доступе. Проверьте права ключа, бесплатный тариф и доступность сервиса в вашем регионе.'
        if status==429:return 'Исчерпан бесплатный лимит или превышена скорость запросов. Дождитесь восстановления квоты либо выберите локальную модель.'
        if status in {400,413}:return 'API отклонил параметры или размер контекста. Для большого агента выберите модель с большим бесплатным лимитом.'
        return 'Провайдер API временно недоступен. Запрос автоматически не перенаправляется в платный сервис.'

    async def connect(self,request):
        data=await request.json();provider=data.get('provider');key=str(data.get('key') or '').strip()
        if provider not in PROVIDERS or not 12<=len(key)<=8192 or '\n' in key or '\r' in key:raise ValueError('Выберите провайдера и вставьте API-ключ.')
        paid=PROVIDERS[provider].get('billing')=='paid'
        if data.get('data_consent') is not True:raise ValueError('Разрешите отправку данных выбранному API.')
        if paid and data.get('paid_consent') is not True:raise ValueError('Явно разрешите платные запросы к этому провайдеру.')
        if not paid and data.get('free_plan') is not True:raise ValueError('Подтвердите бесплатный тариф и отправку данных выбранному API.')
        request_limit=data.get('request_limit',PROVIDERS[provider]['daily_cap'])
        if paid and (isinstance(request_limit,bool) or not isinstance(request_limit,int) or not 1<=request_limit<=1000):raise ValueError('Лимит приложения: от 1 до 1000 запросов в день.')
        workspace=str(data.get('workspace_id') or '').strip() if provider=='anthropic' else ''
        if workspace and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',workspace):raise ValueError('Проверьте Workspace ID Anthropic.')
        async with self.connect_lock:
            card=PROVIDERS[provider];headers={'Authorization':'Bearer '+key}
            async with ClientSession(timeout=ClientTimeout(total=22)) as http:
                if provider=='anthropic':
                    headers={'x-api-key':key,'anthropic-version':'2023-06-01'};url=card['base']+'/models?limit=100'
                    if workspace:headers['anthropic-workspace-id']=workspace
                elif provider=='fal':
                    headers={'Authorization':'Key '+key}
                    url='https://api.fal.ai/v1/models/requests/by-endpoint?endpoint_id=fal-ai%2Fwan-25-preview%2Ftext-to-video&limit=1'
                elif provider=='cloudflare':
                    account=str(data.get('account_id') or '').strip()
                    if not re.fullmatch(r'[a-fA-F0-9]{32}',account):raise ValueError('Account ID Cloudflare должен содержать 32 шестнадцатеричных символа.')
                    url='https://api.cloudflare.com/client/v4/user/tokens/verify'
                elif provider=='openrouter':url=card['base']+'/key'
                elif provider=='gemini':
                    url='https://generativelanguage.googleapis.com/v1beta/models';headers={'x-goog-api-key':key}
                else:url=card['base']+'/models'
                async with http.get(url,headers=headers,allow_redirects=False) as r:
                    if r.status!=200:raise ValueError(self.upstream_error(r.status,paid))
                    body=await r.json()
            if provider=='fal':rows=[]
            elif provider=='cloudflare':
                if not body.get('success') or (body.get('result') or {}).get('status')!='active':raise ValueError('Cloudflare не подтвердил активность токена.')
                rows=[]
            elif provider=='openrouter':rows=await self.get_catalog(True)
            else:
                available={m.get('id') or str(m.get('name','')).removeprefix('models/') for m in body.get('data',body.get('models',[]))}
                rows=[m for m in card['models'] if m['remote_id'] in available]
            if card['kind']=='chat' and not rows:raise ValueError('У ключа нет доступных моделей из списка этого провайдера.')
            models=[{**row,'id':self.alias(provider,row['remote_id'])} for row in rows]
            credential={'key':key,**({'account_id':account} if provider=='cloudflare' else {})}
            if workspace:credential['workspace_id']=workspace
            persist=data.get('remember',True) is True
            await asyncio.to_thread(self.vault.set,provider,credential,persist)
            self.connections[provider]={'enabled':True,'models':models,'storage':'device' if persist else 'session','connected_at':time.time(),
                **({'paid_consent':True,'request_limit':request_limit} if paid else {})}
            self.portable.write(self.root/'data/cloud-connections.json',self.connections)
            if models:await asyncio.to_thread(self.sync_aliases)
            if provider=='fal':await self.fal.restore()
            return web.json_response({'ok':True,'provider':provider,'models':models,'key_checked':True,'generation_checked':False})

    async def disconnect(self,request):
        provider=(await request.json()).get('provider')
        if provider not in PROVIDERS:raise ValueError('Провайдер не найден.')
        async with self.connect_lock:
            await asyncio.to_thread(self.vault.remove,provider)
            self.connections.pop(provider,None);self.portable.write(self.root/'data/cloud-connections.json',self.connections)
        return web.json_response({'ok':True})

    def authorize(self,request):
        value=request.headers.get('Authorization','')
        return secrets.compare_digest(value,'Bearer '+self.proxy_key)

    async def proxy_models(self,request):
        return web.json_response({'object':'list','data':[{'id':m['id'],'object':'model','owned_by':m['provider_id'],'context_length':m['context_length'],'max_model_len':m['context_length'],'context_window':m['context_length'],'capabilities':{'tools':True,'vision':m['vision']}} for m in self.models()+(self.auto.aliases() if self.auto else [])]})

    async def chat(self,request):
        if not self.authorize(request):return web.json_response({'error':{'message':'Local API route authentication failed','type':'authentication_error'}},status=401)
        incoming=await request.json();target=self.target(incoming.get('model'))
        if not target:return web.json_response({'error':{'message':'Подключение отключено или модель больше недоступна. Выберите модель заново.','type':'invalid_model'}},status=400)
        if target.get('auto_sid'):return await self.auto.chat(request,target,incoming)
        provider=target['provider_id'];credential=await asyncio.to_thread(self.vault.get,provider)
        if not credential:return web.json_response({'error':{'message':'API-ключ не сохранён или хранение до закрытия приложения завершено. Подключите провайдера заново.','type':'authentication_error'}},status=401)
        if provider=='openrouter':
            try:current=await self.get_catalog()
            except (ClientError,asyncio.TimeoutError,ValueError):return web.json_response({'error':{'message':'Не удалось подтвердить нулевую цену модели OpenRouter. Запрос остановлен.','type':'free_catalog_unavailable'}},status=503)
            if not any(r['remote_id']==target['remote_id'] for r in current):return web.json_response({'error':{'message':'Бесплатная модель исчезла из каталога или изменила условия. Обновите подключение.','type':'not_free'}},status=403)
        allowed={'messages','tools','tool_choice','stream','temperature','top_p','stop','seed','response_format','parallel_tool_calls','reasoning_effort'}
        body={k:v for k,v in incoming.items() if k in allowed and v is not None};body['model']=target['remote_id']
        body['max_tokens']=min(4096,max(1,int(incoming.get('max_tokens') or incoming.get('max_completion_tokens') or 2048)))
        if provider=='openrouter':
            body['provider']={'max_price':{'prompt':0,'completion':0},'allow_fallbacks':False,'require_parameters':True}
            if body.get('reasoning_effort')=='none':body.pop('reasoning_effort')
            if 'reasoning_effort' not in target.get('parameters',[]):body.pop('reasoning_effort',None)
        elif provider=='gemini':
            body.pop('parallel_tool_calls',None);body.pop('seed',None)
            if body.get('reasoning_effort') in {'none','minimal'}:body['reasoning_effort']='low'
        elif provider=='deepseek':
            body.pop('parallel_tool_calls',None)
            effort=body.get('reasoning_effort','none')
            body['reasoning_effort']={'minimal':'low','medium':'high','xhigh':'high'}.get(effort,effort)
            body['messages']=[{k:v for k,v in message.items() if k not in {'reasoning_details','refusal'}} for message in body.get('messages',[])]
        elif provider in {'groq','anthropic'}:
            if body.get('reasoning_effort')=='none':body.pop('reasoning_effort')
            # Other providers can return reasoning annotations in assistant history.
            # Groq rejects these output-only fields when replayed as input.
            if isinstance(body.get('messages'),list):
                output_only={'reasoning_content','reasoning_details','reasoning','refusal','name'}
                body['messages']=[{k:v for k,v in message.items() if k not in output_only}
                                  if isinstance(message,dict) else message for message in body['messages']]
            if provider=='anthropic':
                for key in ('temperature','top_p','seed','reasoning_effort','response_format'):body.pop(key,None)
                if body.get('tool_choice') not in (None,'auto','none'):
                    return web.json_response({'error':{'message':'Эта модель Claude поддерживает автоматический выбор инструментов, без принудительного вызова.','type':'unsupported_tool_choice'}},status=400)
        if body.get('stream'):body['stream_options']={'include_usage':True}
        try:self.reserve(provider)
        except ValueError as e:return web.json_response({'error':{'message':str(e),'type':'local_daily_limit'}},status=429)
        if target.get('protocol')=='responses':return await self.responses.chat(request,target,body,credential)
        headers={'Authorization':'Bearer '+credential['key'],'Content-Type':'application/json'}
        if provider=='openrouter':headers['X-Title']='Freedom GPT'
        if provider=='anthropic' and credential.get('workspace_id'):headers['anthropic-workspace-id']=credential['workspace_id']
        started=time.monotonic();completion=0;first_output=None;upstream_detail=None
        try:
            async with ClientSession(timeout=ClientTimeout(total=240,connect=15,sock_read=120),read_bufsize=1024*1024) as http:
                async with http.post(PROVIDERS[provider]['base']+'/chat/completions',json=body,headers=headers,allow_redirects=False) as upstream:
                    if upstream.status!=200:
                        # Keep a small credential-redacted diagnosis, never a request body
                        # or raw nested provider metadata. Successful calls clear it.
                        with contextlib.suppress(ValueError,TypeError):
                            failure=await upstream.json(content_type=None)
                            if isinstance(failure,list):failure=next((item for item in failure if isinstance(item,dict)),{})
                            failure=failure.get('error',{}) if isinstance(failure,dict) else {}
                            if not isinstance(failure,dict):failure={}
                            upstream_detail={'status':upstream.status}
                            for field in ('message','code','type','param'):
                                value=failure.get(field)
                                if isinstance(value,(str,int)):
                                    value=str(value)
                                    for secret in credential.values():
                                        if isinstance(secret,str) and secret:value=value.replace(secret,'[REDACTED]')
                                    upstream_detail[field]=value[:800]
                        # Paid 5xx/transport errors must not trigger the SDK's automatic retry.
                        status=upstream.status if upstream.status in {400,401,402,403,413,422,429} else 400 if target.get('paid') else 503
                        return web.json_response({'error':{'message':self.upstream_error(upstream.status,target.get('paid',False)),'type':'upstream_error'}},status=status)
                    if not body.get('stream'):
                        result=await upstream.json();usage=result.get('usage') or {};completion=int(usage.get('completion_tokens') or 0)
                        return web.json_response(result)
                    response=web.StreamResponse(status=200,headers={'Content-Type':'text/event-stream','Cache-Control':'no-store','X-Accel-Buffering':'no'})
                    await response.prepare(request)
                    async for line in upstream.content:
                        if request.transport is None or request.transport.is_closing():break
                        if line.startswith(b'data: '):
                            with contextlib.suppress(ValueError,TypeError):
                                event=json.loads(line[6:]);usage=event.get('usage') or {}
                                completion=max(completion,int(usage.get('completion_tokens') or 0))
                                if first_output is None and any((c.get('delta') or {}).get('content') or (c.get('delta') or {}).get('reasoning_content') for c in event.get('choices',[])):first_output=time.monotonic()
                        await response.write(line)
                    with contextlib.suppress(ConnectionError):await response.write_eof()
                    return response
        except (ClientError,asyncio.TimeoutError):
            if 'response' in locals():return response
            if target.get('paid'):return web.json_response({'error':{'message':'Связь с платным API прервалась. Исход запроса неизвестен. Проверьте кабинет перед повтором.','type':'outcome_unknown'}},status=400)
            return web.json_response({'error':{'message':'Нет связи с API. Проверьте интернет; автоматического перехода на платный сервис нет.','type':'connection_error'}},status=503)
        except (ConnectionError,asyncio.CancelledError):
            if 'response' in locals():return response
            raise
        finally:
            elapsed=max(.001,time.monotonic()-started)
            self.calls[target['id']]={'tokens_per_second':round(completion/max(.001,time.monotonic()-(first_output or started)),1) if completion else None,'output_tokens':completion,'seconds':round(elapsed,2),'time':time.time(),**({'last_error':upstream_detail} if upstream_detail else {})}

    async def image_submit(self,request):
        async with self.image_lock:
            return await self._image_submit(request)

    async def _image_submit(self,request):
        data=await request.json();identifier=str(data.get('input_id') or '');prompt=str(data.get('prompt') or '').strip();sid=str(data.get('sid') or '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',identifier) or not 1<=len(prompt)<=4000:raise ValueError('Введите описание изображения до 4 000 символов.')
        if not self.connections.get('cloudflare',{}).get('enabled'):raise ValueError('Сначала подключите Cloudflare Workers AI.')
        with self.db() as c:
            old=c.execute('SELECT * FROM cloud_images WHERE id=?',(identifier,)).fetchone()
            if old:
                if old['prompt']!=prompt or old['sid']!=sid:raise ValueError('Идентификатор изображения уже использован.')
                return web.json_response(self.image_public(dict(old)))
        credential=await asyncio.to_thread(self.vault.get,'cloudflare')
        if not credential:raise ValueError('Вставьте API-токен Cloudflare заново.')
        if sid:await self.bridge.resume(sid)
        self.reserve('cloudflare')
        with self.db() as c:c.execute('INSERT INTO cloud_images VALUES(?,?,?,?,?,?,?,?,?)',(identifier,'cloudflare',prompt,sid,'queued','','',time.time(),None))
        task=asyncio.create_task(self.generate(identifier,credential));self.image_tasks.add(task);task.add_done_callback(self.image_tasks.discard)
        return web.json_response({'id':identifier,'state':'queued'})

    @staticmethod
    def image_public(row):
        return {k:row[k] for k in ['id','state','error','created','finished'] if k in row}|({'url':'/api/cloud/images/'+row['id']+'/file'} if row.get('state')=='completed' else {})

    async def generate(self,identifier,credential):
        with self.db() as c:
            row=dict(c.execute('SELECT * FROM cloud_images WHERE id=?',(identifier,)).fetchone());c.execute("UPDATE cloud_images SET state='running' WHERE id=?",(identifier,))
        try:
            url='https://api.cloudflare.com/client/v4/accounts/'+credential['account_id']+'/ai/run/@cf/black-forest-labs/flux-1-schnell'
            async with ClientSession(timeout=ClientTimeout(total=150,connect=15)) as http:
                async with http.post(url,json={'prompt':row['prompt'],'steps':4},headers={'Authorization':'Bearer '+credential['key']},allow_redirects=False) as r:
                    if r.status!=200:raise ValueError(self.upstream_error(r.status))
                    result=await r.json()
            encoded=(result.get('result') or {}).get('image')
            if not result.get('success') or not isinstance(encoded,str) or len(encoded)>40*1024**2:raise ValueError('API не вернул изображение. Автоматического повтора не было.')
            raw=base64.b64decode(encoded,validate=True)
            from PIL import Image
            image=Image.open(io.BytesIO(raw));image.verify()
            folder=self.root/'output/cloud-images';folder.mkdir(parents=True,exist_ok=True);target=folder/(identifier+'.jpg')
            with Image.open(io.BytesIO(raw)) as image:image.convert('RGB').save(target,format='JPEG',quality=95)
            with self.db() as c:c.execute("UPDATE cloud_images SET state='completed',path=?,finished=? WHERE id=?",(str(target),time.time(),identifier))
            if row['sid']:
                self.artifact(row['sid'],str(target));await self.bridge.broadcast({'type':'artifacts.changed','session_id':row['sid']})
        except asyncio.CancelledError:
            with self.db() as c:c.execute("UPDATE cloud_images SET state='unknown',error='Операция прервана. Исход запроса неизвестен; повтор не выполнялся.' WHERE id=?",(identifier,))
            raise
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else 'Не удалось получить изображение из API. Автоматического повтора не было.'
            with self.db() as c:c.execute("UPDATE cloud_images SET state='failed',error=?,finished=? WHERE id=?",(message,time.time(),identifier))

    async def image_status(self,request):
        with self.db() as c:row=c.execute('SELECT * FROM cloud_images WHERE id=?',(request.match_info['job'],)).fetchone()
        if not row:raise web.HTTPNotFound()
        return web.json_response(self.image_public(dict(row)))

    async def image_file(self,request):
        with self.db() as c:row=c.execute('SELECT * FROM cloud_images WHERE id=?',(request.match_info['job'],)).fetchone()
        if not row or row['state']!='completed':raise web.HTTPNotFound()
        path=pathlib.Path(row['path']).resolve()
        if not path.is_relative_to((self.root/'output/cloud-images').resolve()) or not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Content-Disposition':'inline; filename="freedom-api-image.jpg"'})

    async def close(self):
        await self.fal.close()
        for task in list(self.image_tasks):task.cancel()
        if self.image_tasks:await asyncio.gather(*self.image_tasks,return_exceptions=True)

    def register(self,app):
        self.fal.register(app)
        app.router.add_get('/api/cloud',self.status);app.router.add_post('/api/cloud/connect',self.connect)
        app.router.add_post('/api/cloud/disconnect',self.disconnect);app.router.add_post('/api/cloud/refresh',self.refresh)
        app.router.add_post('/api/cloud/images',self.image_submit);app.router.add_get('/api/cloud/images/{job}',self.image_status)
        app.router.add_get('/api/cloud/images/{job}/file',self.image_file)
        app.router.add_get('/cloud/v1/models',self.proxy_models);app.router.add_post('/cloud/v1/chat/completions',self.chat)
