"""Isolated account/download regressions. No real credentials or external writes.

Run with the bundled Python. Every generated file lives under project .tmp.
"""
import asyncio,base64,contextlib,hashlib,importlib,json,os,pathlib,sqlite3,struct,sys,threading,time,types,unittest,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch

ROOT=pathlib.Path(os.environ['FREEDOM_QA_ROOT']).resolve();sys.path[:0]=[str(ROOT),str(ROOT/'runtime/freedom')]
PLUGIN_SOURCE=ROOT/'agent_plugins/freedom-accounts'
if not PLUGIN_SOURCE.is_dir():PLUGIN_SOURCE=ROOT/'runtime/freedom/agent_plugins/freedom-accounts'
import bootstrap,github_access,hf_access,cloud_vault,library as library_module,rewards as rewards_module,account_connections,model_advisor
import requests

QA=ROOT/'.tmp'/('qa-integrations-'+uuid.uuid4().hex[:10]);QA.mkdir(parents=True)
assert QA.resolve().is_relative_to((ROOT/'.tmp').resolve())
GH='ghp_'+'Q'*36;HF='hf_'+'R'*32  # Synthetic fixture tokens, only sent to the loopback emulator.

def gguf(context=65536):
    key=b'qwen.context_length'
    return b'GGUF'+struct.pack('<IQQQ',3,0,1,len(key))+key+struct.pack('<II',4,context)+b'fixture-weights'*1024

PAYLOAD=gguf();SHA=hashlib.sha256(PAYLOAD).hexdigest()
class State:
    lock=threading.RLock();calls=[];mode='normal';files={};delay=None

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def do_PUT(self):self.handle_request()
    def reply(self,status,data,headers=None):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def handle_request(self):
        from urllib.parse import urlsplit,unquote
        route=unquote(urlsplit(self.path).path);raw=self.rfile.read(int(self.headers.get('Content-Length',0)));data=json.loads(raw) if raw else None
        with State.lock:State.calls.append({'method':self.command,'path':route,'data':data,'authorized':bool(self.headers.get('Authorization')),'range':self.headers.get('Range')})
        if route=='/gh/user' or route=='/hf/api/whoami-v2':
            if State.delay:State.delay[0].set();State.delay[1].wait(5)
            if State.mode=='unauthorized':return self.reply(401,{'message':'bad credential'})
            if State.mode=='forbidden':return self.reply(403,{'message':'forbidden'})
            if State.mode=='malformed':return self.reply(200,[])
            return self.reply(200,{'login':'fixture-user'} if route=='/gh/user' else {'name':'fixture-user'},{'X-OAuth-Scopes':'repo, read:org'})
        if route=='/gh/user/repos':
            row={'full_name':'fixture-user/demo','html_url':'https://github.com/fixture-user/demo','default_branch':'main','private':True,'description':'fixture'}
            return self.reply(201 if self.command=='POST' else 200,row if self.command=='POST' else [row])
        if route.startswith('/gh/repos/fixture-user/demo'):
            path=route.removeprefix('/gh/repos/fixture-user/demo')
            if not path:return self.reply(200,{'full_name':'fixture-user/demo','default_branch':'main','private':True})
            if path.startswith('/contents/'):
                filename=path[len('/contents/'):]
                if self.command=='PUT':
                    State.files[filename]={'sha':'new-sha','content':data['content']}
                    return self.reply(200,{'content':{'html_url':'https://github.com/fixture-user/demo/blob/main/'+filename,'sha':'new-sha'},'commit':{'sha':'commit-sha'}})
                if State.mode=='folder':return self.reply(200,[{'name':'folder','type':'dir'}])
                if not filename:return self.reply(200,[{'name':'README.md','path':'README.md','type':'file','sha':'old-sha','size':7}])
                if filename not in State.files:return self.reply(404,{'message':'not found'})
                value=State.files[filename]
                return self.reply(200,{'type':'file','path':filename,'encoding':'base64','size':len(base64.b64decode(value['content'])),'sha':value['sha'],'content':value['content'],'html_url':'https://github.com/fixture-user/demo/blob/main/'+filename})
            if path.startswith('/git/ref/heads/'):return self.reply(200,{'object':{'sha':'base-sha'}})
            if path=='/git/refs':return self.reply(201,{'ref':data['ref'],'object':{'sha':data['sha']}})
            if path in ('/pulls','/issues'):return self.reply(201,{'number':1,'html_url':'https://github.com/fixture-user/demo/issues/1','state':'open','title':data['title'],'draft':data.get('draft')})
        if route=='/hf/api/models/fixture/model':
            return self.reply(200,{'sha':'revision','cardData':None if State.mode=='null-card' else {'license':'apache-2.0'},'siblings':[{'rfilename':'model.gguf','size':len(PAYLOAD),'lfs':{'sha256':SHA,'size':len(PAYLOAD)}}]})
        if route=='/download/model.gguf':
            start=int((self.headers.get('Range') or 'bytes=0-').split('=')[1].split('-')[0]);body=PAYLOAD[start:]
            if State.mode=='ignore-range':start=0;body=PAYLOAD
            if State.mode=='corrupt':body=b'!'*len(body)
            self.send_response(200 if State.mode=='ignore-range' else 206)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Content-Range',f'bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}');self.end_headers();self.wfile.write(body);return
        self.reply(404,{'message':'fixture route missing'})

SERVER=ThreadingHTTPServer(('127.0.0.1',0),Handler);THREAD=threading.Thread(target=SERVER.serve_forever,daemon=True);THREAD.start()
ORIGIN='http://127.0.0.1:'+str(SERVER.server_port)
REAL_REQUEST=requests.sessions.Session.request
def routed(self,method,url,**kwargs):
    from urllib.parse import urlsplit
    parsed=urlsplit(url)
    if parsed.hostname=='api.github.com':url=ORIGIN+'/gh'+parsed.path+('?' + parsed.query if parsed.query else '')
    elif parsed.hostname=='huggingface.co':url=ORIGIN+'/hf'+parsed.path+('?' + parsed.query if parsed.query else '')
    elif not url.startswith(ORIGIN+'/'):raise AssertionError('External traffic is forbidden in this test suite')
    return REAL_REQUEST(self,method,url,**kwargs)

class Base(unittest.TestCase):
    def setUp(self):
        self.root=QA/(self._testMethodName+'-'+uuid.uuid4().hex[:6]);self.root.mkdir()
        with State.lock:State.calls=[];State.mode='normal';State.files={};State.delay=None
        self.enterContext(patch.object(requests.sessions.Session,'request',routed))
        self.enterContext(patch.dict(os.environ,{'HF_TOKEN':'','HUGGING_FACE_HUB_TOKEN':'','HF_HOME':str(self.root/'hf-cache'),'HF_TOKEN_PATH':str(self.root/'hf-cache/token')}))
        for module in (github_access,hf_access,library_module):self.enterContext(patch.object(module,'ROOT',self.root))
        self.enterContext(patch.object(github_access,'HOME',self.root/'home'));self.enterContext(patch.object(github_access,'STACK',self.root/'stack'))
        self.enterContext(patch.object(github_access,'workspace_root',lambda:self.root/'projects'))
        self.enterContext(patch.object(library_module,'STACK',self.root/'stack'))
        self.gh=github_access.GitHubAccess();self.hf=hf_access.HuggingFaceAccess()
        self.enterContext(patch.object(library_module,'hf_access',self.hf))
    def connected(self,write=True,persist=False):return self.gh.check(GH,persist=persist,allow_write=write)
    def lib(self):
        value=library_module.Library();self.addCleanup(value.pool.shutdown,wait=True);return value

class Accounts(Base):
    def test_optional_start_has_no_external_request(self):
        self.assertFalse(self.gh.status()['available']);self.assertEqual(State.calls,[])
    def test_invalid_token_never_sent(self):
        with self.assertRaises(ValueError):self.gh.check('wrong')
        self.assertEqual(State.calls,[])
    def test_connect_identity_and_no_secret_output(self):
        state=self.connected();self.assertEqual(state['username'],'fixture-user');self.assertNotIn(GH,json.dumps(state));self.assertTrue(state['allow_write'])
    def test_session_only_does_not_survive_restart(self):
        self.connected();self.assertFalse(github_access.GitHubAccess().status()['available'])
    def test_dpapi_persistence_and_no_plaintext(self):
        if os.name!='nt':self.skipTest('Windows DPAPI test')
        self.connected(persist=True);self.assertNotIn(GH.encode(),self.gh.vault.path.read_bytes());self.assertTrue(github_access.GitHubAccess().status()['available'])
    def test_disconnect_clears_both_kinds(self):
        self.connected(persist=os.name=='nt');self.gh.disconnect();self.assertFalse(self.gh.status()['available']);self.assertFalse(github_access.GitHubAccess().status()['available'])
    def test_bad_login_preserves_working_account(self):
        self.connected();State.mode='unauthorized'
        with self.assertRaises(ValueError):self.gh.check('ghp_'+'X'*36)
        self.assertTrue(self.gh.status()['available']);self.assertEqual(self.gh.credential(),GH)
    def test_all_mutations_blocked_by_read_only(self):
        self.connected(write=False);before=len(State.calls)
        for action in ('create_repository','write_file','create_branch','create_pull_request','create_issue'):
            with self.assertRaises(ValueError):self.gh.operate({'action':action,'name':'demo','repository':'fixture-user/demo'})
        self.assertEqual(len(State.calls),before)
    def test_private_repository_is_default(self):
        self.connected();self.gh.operate({'action':'create_repository','name':'demo'});self.assertTrue(State.calls[-1]['data']['private'])
    def test_repo_list_and_metadata(self):
        self.connected();self.assertEqual(len(self.gh.operate({'action':'list_repositories'})['repositories']),1)
        self.assertEqual(self.gh.operate({'action':'repository','repository':'https://github.com/fixture-user/demo.git'})['default_branch'],'main')
    def test_write_then_read_file(self):
        self.connected();result=self.gh.operate({'action':'write_file','repository':'fixture-user/demo','path':'docs/hi.txt','content':'Привет','message':'Create greeting'})
        self.assertEqual(result['sha'],'new-sha');self.assertEqual(self.gh.operate({'action':'read_file','repository':'fixture-user/demo','path':'docs/hi.txt'})['text'],'Привет')
    def test_stale_sha_blocks_write(self):
        self.connected();State.files['hi.txt']={'sha':'old-sha','content':base64.b64encode(b'old').decode()}
        with self.assertRaises(ValueError):self.gh.operate({'action':'write_file','repository':'fixture-user/demo','path':'hi.txt','content':'new','message':'Update greeting','expected_sha':'stale'})
        self.assertFalse(any(row['method']=='PUT' for row in State.calls))
    def test_folder_cannot_be_overwritten(self):
        self.connected();State.mode='folder'
        with self.assertRaises(ValueError):self.gh.operate({'action':'write_file','repository':'fixture-user/demo','path':'folder','content':'hi','message':'Update folder'})
        self.assertFalse(any(row['method']=='PUT' for row in State.calls))
    def test_secrets_and_traversal_are_blocked(self):
        self.connected()
        for path,text in [('../secret','hi'),('.env','hello'),('secret.txt',GH),('id_rsa','hello')]:
            with self.assertRaises(ValueError):self.gh.operate({'action':'write_file','repository':'fixture-user/demo','path':path,'content':text,'message':'Create file'})
        self.assertFalse(any(row['method']=='PUT' for row in State.calls))
    def test_branch_pr_and_issue(self):
        self.connected();self.assertEqual(self.gh.operate({'action':'create_branch','repository':'fixture-user/demo','branch':'feature/demo'})['ref'],'refs/heads/feature/demo')
        self.assertTrue(self.gh.operate({'action':'create_pull_request','repository':'fixture-user/demo','head':'feature/demo','title':'Review changes'})['draft'])
        self.assertEqual(self.gh.operate({'action':'create_issue','repository':'fixture-user/demo','title':'Review issue'})['number'],1)
    def test_cli_import_only_after_explicit_call(self):
        with patch.object(self.gh,'cli',return_value='fixture-gh'),patch.object(github_access.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=GH+'\n')) as process:
            self.gh.status();process.assert_not_called();self.gh.use_cli();self.assertTrue(self.gh.status()['available']);self.assertEqual(process.call_count,1)
    def test_disconnect_wins_over_late_login(self):
        entered,released=threading.Event(),threading.Event();State.delay=(entered,released);errors=[]
        def login():
            try:self.gh.check(GH)
            except ValueError as error:errors.append(str(error))
        worker=threading.Thread(target=login);worker.start();self.assertTrue(entered.wait(3));self.gh.disconnect();released.set();worker.join(5)
        self.assertFalse(self.gh.status()['available'])
    def test_reconnect_after_unreadable_vault_preserves_original(self):
        self.gh.vault.path.parent.mkdir(parents=True,exist_ok=True);self.gh.vault.path.write_bytes(b'inaccessible-original')
        self.connected();self.assertTrue(self.gh.status()['available']);self.assertTrue(any(p.read_bytes()==b'inaccessible-original' for p in (self.root/'archive').rglob('*.dpapi')))
    def test_malformed_profile_has_friendly_error(self):
        State.mode='malformed'
        with self.assertRaises(ValueError):self.connected()
    def test_hf_connect_and_disconnect(self):
        self.hf.check(HF);self.assertEqual(self.hf.status()['username'],'fixture-user');self.hf.disconnect();self.assertFalse(self.hf.status()['available'])
    def test_hf_does_not_send_credentials_to_other_hosts(self):
        self.hf.check(HF)
        for url in ('http://huggingface.co/model','https://evil.example/model','https://huggingface.co.evil.example/model','https://huggingface.co:444/model','https://name@huggingface.co/model'):
            self.assertNotIn('Authorization',self.hf.headers(url))
        self.assertIn('Authorization',self.hf.headers('https://huggingface.co/model'))
    def test_hf_bad_token_retains_existing(self):
        self.hf.check(HF);State.mode='unauthorized'
        with self.assertRaises(ValueError):self.hf.check('hf_'+'Z'*32)
        self.assertTrue(self.hf.status()['available'])
    def test_hf_disconnect_wins_over_late_login(self):
        entered,released=threading.Event(),threading.Event();State.delay=(entered,released)
        def login():
            try:self.hf.check(HF)
            except ValueError:pass
        worker=threading.Thread(target=login);worker.start();self.assertTrue(entered.wait(3));self.hf.disconnect();released.set();worker.join(5);self.assertFalse(self.hf.status()['available'])
    def test_hf_unreadable_vault_can_reconnect(self):
        self.hf.vault.path.parent.mkdir(parents=True,exist_ok=True);self.hf.vault.path.write_bytes(b'old-hf-vault');self.hf.check(HF)
        self.assertTrue(self.hf.status()['available']);self.assertTrue(any(p.read_bytes()==b'old-hf-vault' for p in (self.root/'archive').rglob('*.dpapi')))
    def test_corrupt_vault_disconnect_still_disables_access(self):
        for access in (self.gh,self.hf):
            access.vault.path.parent.mkdir(parents=True,exist_ok=True);access.vault.path.write_bytes(b'original-vault');access.disconnect();self.assertFalse(access.status()['available']);self.assertEqual(access.vault.path.read_bytes(),b'original-vault')
    def test_corrupt_metadata_has_no_internal_exception(self):
        for access in (self.gh,self.hf):
            access.path.parent.mkdir(parents=True,exist_ok=True);access.path.write_text('[]');self.assertFalse(access.status()['available'])
    def test_boolean_connection_options_are_strict(self):
        for value in ('false','true',1,0,None,[],{}):
            for key in ('persist','allow_write'):
                with self.assertRaises(ValueError):cloud_vault.account_options({key:value},write_access=True)
        self.assertFalse(cloud_vault.account_options({})['persist'])
    def test_empty_connect_cannot_reuse_and_change_existing_access(self):
        with self.assertRaises(ValueError):cloud_vault.account_options({},write_access=True,token_required=True)
    def test_other_provider_remains_connected(self):
        self.connected();self.hf.check(HF);self.gh.disconnect();self.assertTrue(self.hf.status()['available'])
    def test_recovery_failure_restores_original_vault(self):
        self.gh.vault.path.parent.mkdir(parents=True,exist_ok=True);self.gh.vault.path.write_bytes(b'original')
        with patch.object(cloud_vault.CloudVault,'crypt',side_effect=ValueError('fixture storage failure')):
            with self.assertRaises(ValueError):self.connected(persist=True)
        self.assertEqual(self.gh.vault.path.read_bytes(),b'original')
    def test_network_mutation_is_never_retried(self):
        self.connected()
        with patch.object(github_access.requests,'request',side_effect=requests.Timeout('fixture timeout')) as request:
            with self.assertRaisesRegex(ValueError,'сначала'):self.gh.operate({'action':'create_repository','name':'demo'})
        self.assertEqual(request.call_count,1)
    def test_local_project_file_can_be_committed(self):
        self.connected();source=self.root/'projects/demo/code.py';source.parent.mkdir(parents=True);source.write_text('print(42)')
        result=self.gh.operate({'action':'write_file','repository':'fixture-user/demo','local_path':str(source),'path':'code.py','message':'Add code'})
        self.assertEqual(result['commit'],'commit-sha')
    def test_internal_app_data_is_not_committed(self):
        self.connected();source=self.root/'data/key.txt';source.parent.mkdir(parents=True,exist_ok=True);source.write_text('fixture')
        with self.assertRaises(ValueError):self.gh.operate({'action':'write_file','repository':'fixture-user/demo','local_path':str(source),'path':'code.txt','message':'Add code'})
    def test_string_draft_flag_rejected(self):
        self.connected()
        with self.assertRaises(ValueError):self.gh.operate({'action':'create_pull_request','repository':'fixture-user/demo','head':'feature','title':'Review changes','draft':'false'})

class Downloads(Base):
    def download_case(self,mode='normal',prefix=b''):
        lib=self.lib();item={'id':'fixture','kind':'chat','name':'Fixture','files':[{'name':'model.gguf','bytes':len(PAYLOAD),'sha256':SHA,'url':ORIGIN+'/download/model.gguf'}]}
        lib.catalog=[item];folder=lib.folder(item);folder.mkdir(parents=True);part=folder/'model.gguf.part'
        if prefix:part.write_bytes(prefix)
        lib.cancel['fixture']=threading.Event();lib.jobs['fixture']={'state':'downloading'};State.mode=mode;lib._download(item)
        return lib,item,folder
    def test_fresh_download_verified(self):
        lib,item,_=self.download_case();self.assertTrue(lib.ready(item));self.assertEqual(lib.jobs['fixture']['state'],'complete')
    def test_resume_download_verified(self):
        lib,item,_=self.download_case(prefix=PAYLOAD[:512]);self.assertTrue(lib.ready(item));self.assertEqual(State.calls[-1]['range'],'bytes=512-')
    def test_oversized_partial_is_preserved_and_recovered(self):
        bad=PAYLOAD+b'extra';lib,item,folder=self.download_case(prefix=bad)
        self.assertTrue(lib.ready(item));preserved=list(folder.glob('*.failed-size-*'));self.assertEqual(len(preserved),1);self.assertEqual(preserved[0].read_bytes(),bad)
        self.assertEqual(State.calls[-1]['range'],'bytes=0-')
    def test_wrong_hash_cannot_launch(self):
        lib,item,folder=self.download_case('corrupt');self.assertFalse(lib.ready(item));self.assertFalse((folder/'model.gguf').exists());self.assertEqual(lib.jobs['fixture']['state'],'error')
        self.assertTrue(list(folder.glob('*.failed-sha256-*')))
        State.mode='normal';lib.jobs['fixture']={};lib._download(item);self.assertTrue(lib.ready(item))
    def test_range_must_match(self):
        lib,item,folder=self.download_case('ignore-range',PAYLOAD[:512]);self.assertEqual((folder/'model.gguf.part').read_bytes(),PAYLOAD[:512]);self.assertFalse(lib.ready(item))
    def test_import_local_and_restart(self):
        source=self.root/'fixture.gguf';source.write_bytes(PAYLOAD);lib=self.lib();item=lib.import_local(source);self.assertTrue(lib.ready(item));again=self.lib();self.assertTrue(again.ready(again.model(item['id'])))
    def test_import_duplicate_has_no_second_copy(self):
        source=self.root/'fixture.gguf';source.write_bytes(PAYLOAD);lib=self.lib();first=lib.import_local(source);second=lib.import_local(source);self.assertEqual(first['id'],second['id']);self.assertEqual(len(lib.catalog),1)
    def test_import_rejects_incompatible_file(self):
        source=self.root/'fixture.gguf';source.write_bytes(gguf(4096));lib=self.lib()
        with self.assertRaises(ValueError):lib.import_local(source)
        self.assertFalse(lib.catalog)
    def test_import_failure_leaves_no_model_in_catalog(self):
        source=self.root/'fixture.gguf';source.write_bytes(PAYLOAD);lib=self.lib()
        with patch.object(library_module.shutil,'copy2',side_effect=OSError('fixture copy failed')):
            with self.assertRaises(OSError):lib.import_local(source)
        self.assertFalse(lib.catalog);self.assertFalse(list((self.root/'stack/models').glob('import-*')))
    def test_hf_null_card_metadata(self):
        State.mode='null-card';lib=self.lib();self.assertEqual(lib.hf_files('fixture/model')['files'][0]['sha256'],SHA)
    def test_concurrent_import_creates_one_copy(self):
        import concurrent.futures
        source=self.root/'fixture.gguf';source.write_bytes(PAYLOAD);lib=self.lib()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:lib.import_local(source),range(2)))
        self.assertEqual(rows[0]['id'],rows[1]['id']);self.assertEqual(len(lib.catalog),1)
    def test_catalog_failure_rolls_back_import(self):
        source=self.root/'fixture.gguf';source.write_bytes(PAYLOAD);lib=self.lib()
        with patch.object(lib,'save_custom',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):lib.import_local(source)
        self.assertFalse(lib.catalog);self.assertFalse(list((self.root/'stack/models').glob('import-*')))
    def test_existing_unverified_file_is_preserved(self):
        lib=self.lib();item={'id':'fixture','kind':'chat','files':[{'name':'model.gguf','bytes':len(PAYLOAD),'sha256':SHA,'url':ORIGIN+'/download/model.gguf'}]};folder=lib.folder(item);folder.mkdir(parents=True);final=folder/'model.gguf';final.write_bytes(b'existing')
        lib.cancel['fixture']=threading.Event();lib.jobs['fixture']={};lib._download(item)
        self.assertEqual(final.read_bytes(),b'existing');self.assertEqual(lib.jobs['fixture']['state'],'error');self.assertEqual(State.calls,[])
    def test_paused_download_remains_resumable(self):
        lib=self.lib();item={'id':'fixture','kind':'chat','files':[{'name':'model.gguf','bytes':len(PAYLOAD),'sha256':SHA,'url':ORIGIN+'/download/model.gguf'}]};folder=lib.folder(item);folder.mkdir(parents=True);part=folder/'model.gguf.part';part.write_bytes(PAYLOAD[:512])
        lib.cancel['fixture']=threading.Event();lib.cancel['fixture'].set();lib.jobs['fixture']={};lib._download(item)
        self.assertEqual(part.read_bytes(),PAYLOAD[:512]);self.assertEqual(lib.jobs['fixture']['state'],'paused')

class Routes(Base):
    def setUp(self):
        super().setUp();self.enterContext(patch.object(account_connections,'github',self.gh));self.enterContext(patch.object(account_connections,'huggingface',self.hf));self.enterContext(patch.object(model_advisor,'access',self.hf));self.enterContext(patch.object(model_advisor,'ROOT',self.root))
    def exercise(self,steps):
        async def run():
            from aiohttp import web
            from aiohttp.test_utils import TestClient,TestServer
            @web.middleware
            async def errors(request,handler):
                try:return await handler(request)
                except ValueError as error:return web.json_response({'error':str(error)},status=400)
            plugin=self.root/'agent_plugins/freedom-accounts';plugin.mkdir(parents=True)
            for name in ('__init__.py','plugin.yaml'):(plugin/name).write_bytes((PLUGIN_SOURCE/name).read_bytes())
            home=self.root/'home';home.mkdir()
            portable=types.SimpleNamespace(HOME=home,read=bootstrap.read,write=bootstrap.write,config=lambda:{'ui_port':8888})
            accounts=account_connections.AccountConnections(self.root,portable);advisor=model_advisor.ModelAdvisor(self.lib());self.addCleanup(advisor.pool.shutdown,wait=True)
            app=web.Application(middlewares=[errors]);accounts.register(app);advisor.register(app)
            async with TestClient(TestServer(app)) as client:
                rows=[]
                for method,path,body,headers in steps:
                    headers={**headers};headers={key:value.replace('TEST-BROKER-KEY',accounts.key) for key,value in headers.items()}
                    async with client.request(method,path,json=body,headers=headers) as response:
                        try:data=await response.json()
                        except Exception:data={}
                        rows.append((response.status,data))
                return rows
        return asyncio.run(run())
    def test_http_connections_and_status(self):
        rows=self.exercise([('POST','/api/accounts/github/connect',{'token':GH},{}),('GET','/api/accounts',None,{}),('POST','/api/advisor/huggingface/connect',{'token':HF},{})])
        self.assertEqual([row[0] for row in rows],[200,200,200]);self.assertTrue(rows[1][1]['github']['available']);self.assertFalse(rows[1][1]['github']['allow_write'])
    def test_http_rejects_string_flags_and_missing_token(self):
        rows=self.exercise([('POST','/api/accounts/github/connect',{'token':GH,'allow_write':'false'},{}),('POST','/api/accounts/github/cli',{'persist':'false'},{}),('POST','/api/advisor/huggingface/connect',{'token':HF,'persist':'false'},{}),('POST','/api/accounts/github/connect',{},{}),('POST','/api/advisor/huggingface/connect',[],{})])
        self.assertEqual([row[0] for row in rows],[400]*5);self.assertEqual(State.calls,[])
    def test_http_settings_rejects_non_object_and_string_flags(self):
        rows=self.exercise([('POST','/api/accounts/github/settings',[],{}),('POST','/api/accounts/github/settings',{'allow_write':'true'},{})])
        self.assertEqual([row[0] for row in rows],[400,400]);self.assertEqual(State.calls,[])
    def test_agent_broker_key_and_read_only_are_enforced(self):
        rows=self.exercise([('POST','/accounts-control/github',{'action':'status'},{}),('POST','/api/accounts/github/connect',{'token':GH},{}),('POST','/accounts-control/github',{'action':'status'},{'Authorization':'Bearer TEST-BROKER-KEY'}),('POST','/accounts-control/github',{'action':'create_repository','name':'demo'},{'Authorization':'Bearer TEST-BROKER-KEY'})])
        self.assertEqual([row[0] for row in rows],[403,200,200,400]);self.assertFalse(any(row['method']=='POST' and row['path']=='/gh/user/repos' for row in State.calls))
    def test_agent_broker_writes_after_explicit_opt_in(self):
        rows=self.exercise([('POST','/api/accounts/github/connect',{'token':GH,'allow_write':True},{}),('POST','/accounts-control/github',{'action':'write_file','repository':'fixture-user/demo','path':'test.txt','content':'fixture','message':'Add file'},{'Authorization':'Bearer TEST-BROKER-KEY'}),('POST','/api/accounts/github/settings',{'allow_write':False},{}),('POST','/accounts-control/github',{'action':'create_issue','repository':'fixture-user/demo','title':'Fixture issue'},{'Authorization':'Bearer TEST-BROKER-KEY'})])
        self.assertEqual([row[0] for row in rows],[200,200,200,400])

class Rewards(Base):
    def setUp(self):
        super().setUp();self.native=self.root/'native';self.native.mkdir();self.projects=self.root/'projects';self.projects.mkdir();self.database=self.root/'interface.sqlite'
        with sqlite3.connect(self.database) as c:c.executescript('''CREATE TABLE chats(id TEXT,title TEXT);CREATE TABLE workspace_turns(admission_id TEXT,finished REAL,created REAL);CREATE TABLE chat_branches(child_id TEXT,parent_id TEXT,created REAL);CREATE TABLE cloud_images(id TEXT,path TEXT,finished REAL,state TEXT);''')
        with sqlite3.connect(self.native/'state.db') as c:c.executescript('''CREATE TABLE sessions(id TEXT,title TEXT,started_at REAL);CREATE TABLE session_admissions(seq INTEGER PRIMARY KEY,admission_id TEXT,target_session_id TEXT,status TEXT,outcome TEXT);CREATE TABLE session_model_usage(session_id TEXT,model TEXT,billing_provider TEXT,billing_base_url TEXT,billing_mode TEXT,task TEXT,input_tokens INTEGER,output_tokens INTEGER,api_call_count INTEGER,first_seen REAL,last_seen REAL);''')
        def db():
            c=sqlite3.connect(self.database);c.row_factory=sqlite3.Row;return c
        self.portable=types.SimpleNamespace(HOME=self.native,STACK=self.root/'stack',workspace_root=lambda:self.projects)
        self.rewards=rewards_module.FreedomRewards(self.root,self.portable,db,None);self.db=db
    def claim(self,source='first',**values):
        file=self.projects/(source+'.txt');file.write_text(source)
        return self.rewards.claim({'category':'sites','title':'Created '+source,'confirmed':True,'source_type':'evidence','evidence':str(file),**values})
    def test_repeat_result_has_no_duplicate_credits(self):
        self.assertFalse(self.claim()['duplicate']);before=self.rewards.snapshot()['profile'];self.assertTrue(self.claim()['duplicate']);self.assertEqual(before,self.rewards.snapshot()['profile'])
    def test_each_distinct_site_increments_counter_and_rewards(self):
        self.claim('first');before=self.rewards.snapshot()['profile']['freedom'];self.claim('second');after=self.rewards.snapshot();self.assertEqual(after['counters']['sites'],2);self.assertEqual(after['profile']['freedom']-before,120)
    def test_rewards_survive_restart(self):
        self.claim();again=rewards_module.FreedomRewards(self.root,self.portable,self.db,None);self.assertEqual(self.rewards.snapshot()['profile'],again.snapshot()['profile'])
    def test_race_credits_one_result(self):
        import concurrent.futures
        file=self.projects/'same.txt';file.write_text('fixture');data={'category':'sites','title':'Created site','confirmed':True,'source_type':'evidence','evidence':str(file)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:self.rewards.claim(data),range(2)))
        self.assertEqual(sum(not row['duplicate'] for row in rows),1);self.assertEqual(self.rewards.snapshot()['counters']['sites'],1)
    def test_confirmation_is_required(self):
        with self.assertRaises(ValueError):self.claim(confirmed=False)
        self.assertEqual(self.rewards.snapshot()['profile']['freedom'],0)
    def test_token_high_water_and_completed_turns(self):
        now=time.time()
        with sqlite3.connect(self.native/'state.db') as c:
            c.execute('INSERT INTO sessions VALUES(?,?,?)',('fixture','fixture',now))
            c.execute('INSERT INTO session_model_usage VALUES(?,?,?,?,?,?,?,?,?,?,?)',('fixture','fixture-model','local','http://127.0.0.1:1111/v1','local','chat',900,100,1,now,now))
            c.executemany('INSERT INTO session_admissions VALUES(?,?,?,?,?)',[(1,'ok','fixture','terminal','completed'),(2,'cancel','fixture','terminal','cancelled')])
        self.rewards.sync();first=self.rewards.snapshot();self.rewards.sync();self.assertEqual(first['profile'],self.rewards.snapshot()['profile']);self.assertEqual(first['counters']['tokens'],1000);self.assertEqual(first['counters']['turns'],1)
        with sqlite3.connect(self.native/'state.db') as c:c.execute('UPDATE session_model_usage SET input_tokens=950,output_tokens=125')
        self.rewards.sync();self.assertEqual(self.rewards.snapshot()['counters']['tokens'],1075)
    def test_results_keep_earning_after_last_badge(self):
        with self.rewards.db() as c:self.rewards.add_counter(c,'sites',250);self.rewards.unlock(c)
        before=self.rewards.snapshot()['profile']['freedom'];self.claim('later');after=self.rewards.snapshot();self.assertEqual(after['counters']['sites'],251);self.assertGreaterEqual(after['profile']['freedom']-before,120)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);result=unittest.TextTestRunner(verbosity=2).run(suite)
    out=ROOT/'output/integration-qa-20261021';out.mkdir(parents=True,exist_ok=True)
    (out/'accounts-download-tests.json').write_text(json.dumps({'run':result.testsRun,'failures':[name.id() for name,_ in result.failures],
        'errors':[name.id() for name,_ in result.errors],'skipped':len(result.skipped),'fixtures':str(QA),'external_network_used':False},indent=2)+'\n',encoding='utf-8')
    SERVER.shutdown();SERVER.server_close();sys.exit(not result.wasSuccessful())
