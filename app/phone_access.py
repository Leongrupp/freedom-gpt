"""Private, optional iPhone bridge. The agent and model stay on loopback.

This controller has two separate trust boundaries: a local, CSRF-protected
management page, and a pinned SSH relay requiring mTLS at the owner's VPS.
No password, profile, pairing URL or message content is written to logs.
"""
from __future__ import annotations
import asyncio, base64, contextlib, datetime as dt, hashlib, hmac, io, json, logging, os
import pathlib, plistlib, secrets, subprocess, sys, time, uuid
from urllib.parse import urlsplit
import bootstrap
from bootstrap import ROOT, read, write
from cloud_vault import CloudVault
from aiohttp import web, ClientSession, ClientTimeout, WSMsgType
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

FOLDER=ROOT/'data/phone'
CONFIG=FOLDER/'settings.json'
VAULT=FOLDER/'identity.dpapi'
PROCESS=ROOT/'.tmp/phone-process.json'
SCRIPT=pathlib.Path(__file__).resolve()
log=logging.getLogger('freedom.phone')
sys.path.insert(0,str(FOLDER/'lib'))

def phone_content_security_policy(upstream,public_url):
    """Retain app capabilities (including WASM), adapting only its socket origin."""
    parts=[part.strip() for part in upstream.split(';') if part.strip()]
    parts=[part for part in parts if part.split(None,1)[0].lower()!='connect-src']
    origin=urlsplit(public_url)
    socket_origin=('wss' if origin.scheme=='https' else 'ws')+'://'+origin.netloc
    parts.append("connect-src 'self' blob: "+socket_origin)
    return '; '.join(parts)

def save_secrets(value):
    FOLDER.mkdir(parents=True,exist_ok=True)
    raw=CloudVault.crypt(json.dumps(value).encode())
    path=VAULT.with_suffix('.'+uuid.uuid4().hex+'.new')
    path.write_bytes(raw);os.replace(path,VAULT)

def load_secrets():
    return json.loads(CloudVault.crypt(VAULT.read_bytes(),True))

def pem_key(key):
    return key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()

def initialize():
    """Prepare private identities once; never replace an existing owner identity."""
    if CONFIG.exists() or VAULT.exists():
        if not (CONFIG.exists() and VAULT.exists()):raise RuntimeError('Неполные настройки телефона. Исходные файлы сохранены.')
        return
    now=dt.datetime.now(dt.timezone.utc)
    key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Freedom GPT private phone CA')])
    ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=5))
        .not_valid_after(now+dt.timedelta(days=1825)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,
            data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=False,decipher_only=False),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False).sign(key,hashes.SHA256()))
    ssh=ed25519.Ed25519PrivateKey.generate()
    save_secrets({'relay_secret':secrets.token_urlsafe(48),'ca_key':pem_key(key),
        'ca_cert':ca.public_bytes(serialization.Encoding.PEM).decode(),
        'ssh_key':ssh.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption()).decode(),
        'ssh_public':ssh.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH).decode()})
    write(CONFIG,{'enabled':False,'provisioned':False,'host':'185.125.100.186','ssh_user':'freedom-phone',
        'local_port':17868,'remote_port':18868,'public_url':'https://aionpc.ru:8444',
        'fingerprint':None,'created':time.time(),'last_seen':None})

def issue_identity(material):
    now=dt.datetime.now(dt.timezone.utc)
    ca=x509.load_pem_x509_certificate(material['ca_cert'].encode())
    ca_key=serialization.load_pem_private_key(material['ca_key'].encode(),None)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Freedom GPT owner iPhone')]))
        .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=True,
            data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),critical=True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
        .sign(ca_key,hashes.SHA256()))
    password=secrets.token_urlsafe(32)
    # Apple profile importers vary between OS versions. This PKCS#12 format
    # favors compatibility; the one-time download also requires verified HTTPS.
    encryption=(serialization.PrivateFormat.PKCS12.encryption_builder().kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC).hmac_hash(hashes.SHA1()).build(password.encode()))
    bundle=pkcs12.serialize_key_and_certificates(b'Freedom GPT iPhone',key,cert,None,encryption)
    profile_id='ru.aionpc.freedom.phone.'+uuid.uuid4().hex
    profile={'PayloadType':'Configuration','PayloadVersion':1,'PayloadIdentifier':profile_id,
        'PayloadUUID':str(uuid.uuid4()),'PayloadDisplayName':'Freedom GPT — личный доступ',
        'PayloadDescription':'Личный ключ доступа к вашему агенту на ПК. Не содержит настроек VPN и не меняет интернет на iPhone.',
        'PayloadOrganization':'Freedom GPT','PayloadRemovalDisallowed':False,
        'PayloadContent':[{'PayloadType':'com.apple.security.pkcs12','PayloadVersion':1,
            'PayloadIdentifier':profile_id+'.identity','PayloadUUID':str(uuid.uuid4()),
            'PayloadDisplayName':'Freedom GPT — ключ вашего iPhone','PayloadContent':bundle,
            'Password':password,'PayloadCertificateFileName':'Freedom-GPT-iPhone.p12'}]}
    return {'key':pem_key(key),'cert':cert.public_bytes(serialization.Encoding.PEM).decode(),
        'fingerprint':cert.fingerprint(hashes.SHA1()).hex(),'profile':base64.b64encode(plistlib.dumps(profile)).decode(),
        'expires':cert.not_valid_after_utc.isoformat()}

def owned_process():
    import psutil
    record=read(PROCESS,{})
    try:
        p=psutil.Process(record['pid'])
        if abs(p.create_time()-record['created'])<1 and any(pathlib.Path(x).name=='phone_access.py' for x in p.cmdline()):return p
    except (KeyError,psutil.Error):pass
    return None

def ensure_started():
    if not CONFIG.is_file():return False
    if owned_process():return True
    with (ROOT/'logs/phone-controller.log').open('ab') as stream:
        from ui_lifecycle import detached_process
        proc=detached_process([sys.executable,'-B','-s',str(SCRIPT),'--serve'],cwd=ROOT,env=os.environ.copy(),
            stdout=stream,stderr=stream)
    import psutil
    write(PROCESS,{'pid':proc.pid,'created':psutil.Process(proc.pid).create_time()})
    return True

class PhoneController:
    def __init__(self):
        self.material=load_secrets();self.csrf=secrets.token_urlsafe(32)
        self.enrollment=None;self.ssh=None;self.client=None;self.websockets=set()
        self.relay_state='connecting';self.error=None;self.last_seen=0
        self.settings=read(CONFIG,{})

    def cfg(self):return read(CONFIG,{})
    def local_allowed(self,request):
        port=self.cfg()['local_port']
        return (request.host in {f'127.0.0.1:{port}',f'localhost:{port}'}
            and not request.headers.get('X-Freedom-Relay')
            and request.remote in {'127.0.0.1','::1'}
            and (not request.headers.get('Origin') or request.headers['Origin'] in {f'http://127.0.0.1:{port}',f'http://localhost:{port}'}))

    def relay_allowed(self,request):
        return hmac.compare_digest(request.headers.get('X-Freedom-Relay',''),self.material['relay_secret'])

    def device_allowed(self,request):
        cfg=self.cfg();fingerprint=cfg.get('fingerprint') or ''
        return (cfg.get('enabled') and self.relay_allowed(request) and bool(fingerprint)
            and request.headers.get('X-Freedom-Client-Verified')=='SUCCESS'
            and hmac.compare_digest(request.headers.get('X-Freedom-Client-Fingerprint','').lower(),fingerprint.lower()))

    @web.middleware
    async def security(self,request,handler):
        try:
            if request.path.startswith('/local'):
                if not self.local_allowed(request):raise web.HTTPForbidden(text='Управление доступно только на вашем ПК.')
                if request.method not in {'GET','HEAD'} and not hmac.compare_digest(request.headers.get('X-Phone-Token',''),self.csrf):
                    raise web.HTTPForbidden(text='Обновите страницу подключения телефона.')
            elif not self.relay_allowed(request):raise web.HTTPForbidden(text='Доступ закрыт.')
            response=await handler(request)
        except web.HTTPException as exc:response=exc
        if not response.prepared:
            response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
                'X-Frame-Options':'DENY','X-Robots-Tag':'noindex, nofollow, noarchive'})
        return response

    async def local_page(self,request):
        return web.FileResponse(ROOT/'scripts/phone-control.html')

    async def status(self,request):
        cfg=self.cfg();ready=False
        try:
            async with self.client.get(f"http://127.0.0.1:{bootstrap.config()['ui_port']}/api/health",timeout=ClientTimeout(total=2)) as r:
                ready=r.status==200 and (await r.json()).get('gateway_ready',False)
        except Exception:pass
        return web.json_response({'csrf':self.csrf,'enabled':bool(cfg.get('enabled')),'provisioned':bool(cfg.get('provisioned')),
            'public_url':cfg['public_url']+'/', 'relay':self.relay_state,'app_ready':ready,
            'has_device':bool(cfg.get('fingerprint')),'last_seen':cfg.get('last_seen'),
            'enrollment_available':bool(self.enrollment and self.enrollment['expires']>time.time() and not self.enrollment['used']),
            'enrollment_url':cfg['public_url']+'/enroll/'+self.enrollment['token'] if self.enrollment and self.enrollment['expires']>time.time() and not self.enrollment['used'] else None,
            'enrollment_expires':self.enrollment['expires'] if self.enrollment else None,'error':self.error})

    async def close_sessions(self):
        for socket in list(self.websockets):
            with contextlib.suppress(Exception):await socket.close(code=1008,message=b'Phone access changed')

    async def action(self,request):
        data=await request.json();action=data.get('action');cfg=self.cfg()
        if action=='toggle':
            if not isinstance(data.get('enabled'),bool):raise web.HTTPBadRequest(text='Некорректное значение.')
            if not cfg.get('provisioned'):raise web.HTTPConflict(text='Сервер ещё не подготовлен.')
            cfg['enabled']=data['enabled'];write(CONFIG,cfg)
            if not cfg['enabled']:
                self.enrollment=None;await self.close_sessions()
                if self.ssh and self.ssh.returncode is None:self.ssh.terminate()
        elif action=='pair':
            if not cfg.get('enabled') or not cfg.get('provisioned'):raise web.HTTPConflict(text='Сначала включите личный доступ.')
            await self.close_sessions()
            identity=issue_identity(self.material)
            self.material['device']=identity;save_secrets(self.material)
            cfg.update(fingerprint=identity['fingerprint'],last_seen=None,certificate_expires=identity['expires']);write(CONFIG,cfg)
            token=secrets.token_urlsafe(32)
            self.enrollment={'token':token,'expires':time.time()+15*60,'used':False}
        elif action=='revoke':
            cfg.update(fingerprint=None,last_seen=None);write(CONFIG,cfg);self.enrollment=None
            self.material.pop('device',None);save_secrets(self.material);await self.close_sessions()
        else:raise web.HTTPBadRequest(text='Неизвестное действие.')
        return await self.status(request)

    async def qr(self,request):
        if not self.enrollment or self.enrollment['expires']<=time.time() or self.enrollment['used']:raise web.HTTPNotFound()
        import qrcode,qrcode.image.svg
        url=self.cfg()['public_url']+'/enroll/'+self.enrollment['token']
        qr=qrcode.QRCode(box_size=8,border=4,error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url);qr.make(fit=True)
        output=io.BytesIO();qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(output)
        return web.Response(body=output.getvalue(),content_type='image/svg+xml')

    async def serve_enrollment(self,request):
        item=self.enrollment;token=request.match_info['token'];cfg=self.cfg()
        if (not cfg.get('enabled') or not item or item['expires']<=time.time() or item['used']
            or not hmac.compare_digest(item['token'],token)):
            raise web.HTTPGone(text='Ссылка истекла или уже использована. Создайте новый QR-код на своём ПК.')
        if request.path.endswith('/profile'):
            if request.method=='HEAD':return web.Response(content_type='application/x-apple-aspen-config')
            item['used']=True
            return web.Response(body=base64.b64decode(self.material['device']['profile']),content_type='application/x-apple-aspen-config',
                headers={'Content-Disposition':'attachment; filename="Freedom-GPT-iPhone.mobileconfig"'})
        html=(ROOT/'scripts/phone-enroll.html').read_text(encoding='utf-8')
        return web.Response(text=html.replace('__PROFILE_URL__',request.path+'/profile').replace('__PUBLIC_URL__',cfg['public_url']+'/'),content_type='text/html')

    async def proxy(self,request):
        if not self.device_allowed(request):raise web.HTTPForbidden(text='Личный доступ закрыт. Подключите свой iPhone через QR-код на ПК.')
        cfg=self.cfg();origin=request.headers.get('Origin')
        if origin and origin!=cfg['public_url']:raise web.HTTPForbidden(text='Недопустимый источник запроса.')
        if request.method not in {'GET','HEAD','OPTIONS'} and origin!=cfg['public_url']:
            raise web.HTTPForbidden(text='Для изменений нужен защищённый сеанс браузера.')
        # The agent-only key endpoint is never made available over the phone bridge.
        if request.path.startswith(('/preview-control','/local','/enroll')):raise web.HTTPForbidden()
        port=bootstrap.config()['ui_port'];url=f'http://127.0.0.1:{port}'+request.raw_path
        remove={'host','origin','connection','upgrade','keep-alive','proxy-authenticate','proxy-authorization','te','trailers',
            'transfer-encoding','x-freedom-relay','x-freedom-client-verified','x-freedom-client-fingerprint','x-forwarded-for','x-forwarded-host','x-forwarded-proto'}
        headers={k:v for k,v in request.headers.items() if k.lower() not in remove}
        headers['Host']=f'127.0.0.1:{port}';headers['Origin']=f'http://127.0.0.1:{port}'
        if time.time()-self.last_seen>15:
            self.last_seen=time.time();cfg['last_seen']=self.last_seen;write(CONFIG,cfg)
        if request.headers.get('Upgrade','').lower()=='websocket':
            # Each hop negotiates its own framing. Forwarding the browser's
            # permessage-deflate offer into an uncompressed aiohttp client
            # causes RSV/compression failures and repeated browser reconnects.
            ws_headers={k:v for k,v in headers.items() if not k.lower().startswith('sec-websocket-')}
            try:up=await self.client.ws_connect(url,headers=ws_headers,heartbeat=20,compress=0,max_msg_size=16*1024*1024)
            except Exception:raise web.HTTPServiceUnavailable(text='Агент пока недоступен. Откройте Freedom GPT на ПК.')
            down=web.WebSocketResponse(heartbeat=20,compress=False,max_msg_size=16*1024*1024)
            await down.prepare(request);self.websockets.add(down)
            async def pump(source,target):
                async for message in source:
                    if not self.device_allowed(request):break
                    if message.type==WSMsgType.TEXT:await target.send_str(message.data)
                    elif message.type==WSMsgType.BINARY:await target.send_bytes(message.data)
                    elif message.type in {WSMsgType.CLOSE,WSMsgType.CLOSED,WSMsgType.ERROR}:break
            tasks=[asyncio.create_task(pump(up,down)),asyncio.create_task(pump(down,up))]
            try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                await up.close();await down.close();self.websockets.discard(down)
            return down
        try:
            async with self.client.request(request.method,url,headers=headers,data=request.content,
                    allow_redirects=False,timeout=ClientTimeout(total=None,sock_connect=5,sock_read=600)) as upstream:
                result_headers={k:v for k,v in upstream.headers.items() if k.lower() not in {'connection','keep-alive','transfer-encoding','content-length','content-encoding'}}
                if 'Content-Security-Policy' in result_headers:
                    result_headers['Content-Security-Policy']=phone_content_security_policy(result_headers['Content-Security-Policy'],cfg['public_url'])
                result_headers.update({'X-Robots-Tag':'noindex, nofollow, noarchive',
                    'Cache-Control':'private, max-age=31536000, immutable' if request.path.startswith('/assets/') else 'no-store'})
                response=web.StreamResponse(status=upstream.status,headers=result_headers);await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(65536):
                    if not self.device_allowed(request):break
                    await response.write(chunk)
                await response.write_eof();return response
        except (ConnectionError,asyncio.TimeoutError):raise web.HTTPServiceUnavailable(text='Связь с агентом потеряна. Повторите подключение.')
        except Exception:
            log.warning('Agent connection unavailable')
            raise web.HTTPServiceUnavailable(text='Freedom GPT пока недоступен. Проверьте, что программа открыта на ПК.')

    async def tunnel(self):
        cfg=self.cfg();folder=FOLDER/'ssh';folder.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':
            account=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).strip().split(',')[-1].strip('"')
            subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r',f'*{account}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        key_path=folder/'tunnel.key';key_path.write_text(self.material['ssh_key'],encoding='ascii')
        if os.name!='nt':key_path.chmod(0o600)
        known=FOLDER/'known_hosts'
        while True:
            cfg=self.cfg()
            if not cfg.get('enabled') or not cfg.get('provisioned'):
                self.relay_state='disabled';await asyncio.sleep(1);continue
            self.relay_state='connecting'
            args=['C:/Windows/System32/OpenSSH/ssh.exe' if os.name=='nt' else 'ssh','-N','-T','-i',str(key_path),
                '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={known.as_posix()}',
                '-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','-o','ConnectTimeout=12',
                '-R',f"127.0.0.1:{cfg['remote_port']}:127.0.0.1:{cfg['local_port']}",f"{cfg['ssh_user']}@{cfg['host']}"]
            try:
                self.ssh=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:await asyncio.wait_for(self.ssh.wait(),timeout=3)
                except asyncio.TimeoutError:
                    self.relay_state='connected';self.error=None
                    await self.ssh.wait()
                error=await self.ssh.stderr.read()
                if self.cfg().get('enabled'):
                    self.error='Туннель переподключается. Проверьте интернет на ПК.'
                    log.warning('Tunnel disconnected (exit=%s)',self.ssh.returncode)
            except asyncio.CancelledError:
                if self.ssh and self.ssh.returncode is None:
                    self.ssh.terminate();await self.ssh.wait()
                raise
            except Exception:
                self.error='Не удалось установить личное соединение с сервером.';log.exception('Tunnel startup failed')
            self.relay_state='connecting';await asyncio.sleep(5)

    async def start(self,app):
        self.client=ClientSession(auto_decompress=True);app['tunnel']=asyncio.create_task(self.tunnel())
    async def stop(self,app):
        app['tunnel'].cancel()
        with contextlib.suppress(asyncio.CancelledError):await app['tunnel']
        await self.close_sessions();await self.client.close()
    def app(self):
        app=web.Application(middlewares=[self.security],client_max_size=55*1024**2)
        app.router.add_get('/local/',self.local_page);app.router.add_get('/local/status',self.status)
        app.router.add_post('/local/action',self.action);app.router.add_get('/local/qr.svg',self.qr)
        app.router.add_get('/enroll/{token}',self.serve_enrollment);app.router.add_get('/enroll/{token}/profile',self.serve_enrollment)
        app.router.add_route('*','/{tail:.*}',self.proxy)
        app.on_startup.append(self.start);app.on_cleanup.append(self.stop);return app

def main():
    if '--serve' in sys.argv:
        logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
        controller=PhoneController()
        web.run_app(controller.app(),host='127.0.0.1',port=controller.cfg()['local_port'],access_log=None,print=None)
    else:
        if not ensure_started():raise RuntimeError('Личный доступ ещё не настроен.')
        if '--open' in sys.argv:
            from platform_support import open_browser
            open_browser(ROOT,f"http://127.0.0.1:{read(CONFIG,{})['local_port']}/local/")

if __name__=='__main__':main()
