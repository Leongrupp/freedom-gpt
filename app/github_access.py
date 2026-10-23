"""Optional app-bound GitHub access. External credentials never enter agent arguments."""
import base64,hashlib,os,pathlib,re,shutil,subprocess,threading,time,urllib.parse
import requests
from bootstrap import ROOT,HOME,STACK,workspace_root,read,write
from cloud_vault import CloudVault
from platform_support import PROCESS_FLAGS

TOKEN_RE=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,255}|github_pat_[A-Za-z0-9_]{20,255})')

class GitHubAccess:
    def __init__(self):
        self.vault=CloudVault(ROOT);self.vault.path=ROOT/'data/github-credentials.dpapi'
        self.path=ROOT/'data/github-connection.json';self.lock=threading.RLock();self.revision=0

    def cli(self):
        for path in (ROOT/'runtime/github/bin/gh.exe',ROOT/'runtime/github/bin/gh'):
            if path.is_file():return str(path)
        return shutil.which('gh')

    def metadata(self):
        data=read(self.path,{})
        return data if isinstance(data,dict) else {}

    def credential(self):
        if self.metadata().get('disabled'):return None
        saved=self.vault.get('github')
        if saved and not isinstance(saved.get('token'),str):raise ValueError('Хранилище GitHub содержит некорректную запись. Подключитесь повторно.')
        return saved['token'] if saved else None

    def status(self):
        meta=self.metadata()
        try:token=self.credential()
        except ValueError:return {'available':False,'credential_error':True,'persistent_supported':os.name=='nt','cli_available':bool(self.cli())}
        verified=bool(token) and meta.get('fingerprint')==hashlib.sha256(token.encode()).hexdigest()
        return {'available':bool(token),'username':meta.get('username') if verified else None,
                'checked_at':meta.get('checked_at') if verified else None,'source':meta.get('source') if verified else None,
                'allow_write':meta.get('allow_write') is True if verified else False,'persistent_supported':os.name=='nt',
                'cli_available':bool(self.cli()),'scopes':meta.get('scopes',[]) if verified else []}

    def request(self,method,path,*,token=None,data=None,params=None,missing=False):
        token=token or self.credential()
        if not token:raise ValueError('Подключите GitHub в настройках аккаунтов.')
        if method!='GET' and self.metadata().get('allow_write') is not True:raise ValueError('Запись в GitHub отключена. Владелец может включить её в настройках аккаунтов.')
        if not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path:raise ValueError('Некорректный путь GitHub API.')
        try:
            response=requests.request(method,'https://api.github.com'+path,json=data,params=params,
                headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'FreedomGPT',
                         'X-GitHub-Api-Version':'2026-03-10'},timeout=(8,30),allow_redirects=False)
            if response.status_code==404 and missing:return None,response
            if response.status_code==401:raise ValueError('GitHub не принял токен. Проверьте срок действия и подключитесь снова.')
            if response.status_code==403:raise ValueError('GitHub отклонил доступ. Проверьте права токена, разрешение организации и лимит запросов.')
            if response.status_code==404:raise ValueError('Репозиторий или файл не найден либо недоступен этому токену.')
            if response.status_code in (409,422):raise ValueError('GitHub не принял изменение: проверьте имя, ветку, защиту ветки и актуальную версию файла.')
            if not 200<=response.status_code<300:raise ValueError('GitHub временно недоступен или вернул неподдерживаемый ответ.')
            return response.json() if response.content else {},response
        except requests.RequestException:
            if method!='GET':raise ValueError('Ответ GitHub не получен. Изменение могло примениться; сначала проверьте репозиторий.') from None
            raise ValueError('Нет связи с GitHub. Проверьте интернет и повторите действие.') from None

    def check(self,token=None,persist=False,allow_write=None,source='token'):
        if not isinstance(persist,bool) or allow_write is not None and not isinstance(allow_write,bool):raise ValueError('Параметры сохранения и записи должны быть true или false.')
        supplied=token is not None
        with self.lock:
            revision=self.revision
            if not supplied:token=self.credential()
        token=str(token or '').strip()
        if not TOKEN_RE.fullmatch(token):raise ValueError('Вставьте действующий personal access token GitHub.')
        profile,response=self.request('GET','/user',token=token);username=profile.get('login','') if isinstance(profile,dict) else ''
        if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}',username):raise ValueError('GitHub вернул неполный профиль.')
        with self.lock:
            if revision!=self.revision:raise ValueError('Настройки подключения изменились. При необходимости подключитесь снова.')
            meta=self.metadata()
            if supplied:self.vault.set_account('github',{'token':token},persist=bool(persist))
            write(self.path,{'username':username,'checked_at':time.time(),'disabled':False,
                'fingerprint':hashlib.sha256(token.encode()).hexdigest(),'source':source if supplied else meta.get('source','token'),
                'allow_write':allow_write if allow_write is not None else meta.get('allow_write') is True,
                'scopes':[s.strip() for s in response.headers.get('X-OAuth-Scopes','').split(',') if s.strip()]})
            self.revision+=1
        return self.status()

    def use_cli(self,persist=False,allow_write=False):
        binary=self.cli()
        if not binary:raise ValueError('GitHub CLI не найден. Подключитесь по personal access token.')
        env=os.environ.copy();env.pop('GH_DEBUG',None)
        try:
            result=subprocess.run([binary,'auth','token','--hostname','github.com'],env=env,capture_output=True,text=True,
                                  encoding='utf-8',timeout=12,creationflags=PROCESS_FLAGS)
        except (OSError,subprocess.TimeoutExpired):raise ValueError('Не удалось прочитать вход GitHub CLI.') from None
        if result.returncode:raise ValueError('В GitHub CLI нет действующего входа. Выполните gh auth login или подключите токен.')
        return self.check(result.stdout.strip(),persist,allow_write,source='cli')

    def settings(self,allow_write):
        if not isinstance(allow_write,bool):raise ValueError('Укажите разрешение на запись в GitHub.')
        with self.lock:
            meta=self.metadata();meta['allow_write']=allow_write;write(self.path,meta)
            self.revision+=1
        return self.status()

    def disconnect(self):
        with self.lock:
            write(self.path,{'disabled':True,'allow_write':False});self.revision+=1
            try:self.vault.remove('github')
            except ValueError:self.vault.session.pop('github',None)
        return self.status()

    @staticmethod
    def repository(value):
        value=str(value or '').strip().removeprefix('https://github.com/').rstrip('/').removesuffix('.git')
        if not re.fullmatch(r'[A-Za-z0-9-]{1,64}/[A-Za-z0-9_.-]{1,100}',value) or value.split('/')[-1] in ('.','..'):raise ValueError('Укажите репозиторий в формате owner/repository.')
        return value

    @staticmethod
    def file_path(value):
        value=str(value or '').replace('\\','/')
        if not value or value.startswith('/') or len(value)>1000 or any(p in ('','.','..','.git') for p in value.split('/')) or any(ord(ch)<32 for ch in value):raise ValueError('Укажите относительный путь файла в репозитории.')
        return value

    @staticmethod
    def brief(row):
        return {k:row.get(k) for k in ('full_name','html_url','private','default_branch','description')}

    def operate(self,args):
        action=args.get('action','status')
        if action=='status':return self.status()
        state=self.status()
        if not state.get('available'):raise ValueError('Подключите GitHub в настройках аккаунтов.')
        writes={'create_repository','write_file','create_branch','create_pull_request','create_issue'}
        if action in writes and not state.get('allow_write'):raise ValueError('Запись в GitHub отключена. Владелец может включить её в настройках аккаунтов.')
        if action=='list_repositories':
            rows,_=self.request('GET','/user/repos',params={'sort':'updated','per_page':min(100,max(1,int(args.get('limit',30))))})
            return {'repositories':[self.brief(r) for r in rows]}
        if action=='create_repository':
            name=str(args.get('name',''))
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',name) or name in ('.','..'):raise ValueError('Укажите корректное имя нового репозитория.')
            private=args.get('private',True)
            if not isinstance(private,bool):raise ValueError('Укажите видимость репозитория.')
            row,_=self.request('POST','/user/repos',data={'name':name,'private':private,'description':str(args.get('description',''))[:350],'auto_init':True})
            return self.brief(row)
        repo=self.repository(args.get('repository'));base='/repos/'+repo
        if action=='repository':return self.brief(self.request('GET',base)[0])
        if action in ('list_files','read_file'):
            path=self.file_path(args['path']) if args.get('path') else ''
            row,_=self.request('GET',base+'/contents/'+urllib.parse.quote(path,safe='/'),params={'ref':args['branch']} if args.get('branch') else None)
            if isinstance(row,list):return {'files':[{k:r.get(k) for k in ('name','path','type','sha','size','html_url')} for r in row][:300]}
            if not isinstance(row,dict) or row.get('type')!='file' or row.get('encoding')!='base64' or row.get('size',0)>256*1024:raise ValueError('Для чтения выберите обычный файл до 256 КБ.')
            raw=base64.b64decode(row.get('content',''));return {'path':row['path'],'sha':row['sha'],'text':raw.decode('utf-8','replace'),'url':row['html_url']}
        if action=='write_file':
            path=self.file_path(args.get('path'));message=str(args.get('message','')).strip()
            if not 3<=len(message)<=500:raise ValueError('Укажите сообщение коммита от 3 до 500 символов.')
            if args.get('local_path'):
                local=pathlib.Path(args['local_path']).resolve()
                if not local.is_file() or not local.is_relative_to(workspace_root()) or local.is_relative_to(HOME.resolve()) or local.is_relative_to(STACK.resolve()):raise ValueError('Выберите файл проекта в рабочем пространстве.')
                forbidden=[ROOT/p for p in ('data','runtime','logs','archive','.tmp','.cache','uploads')]
                if any(local.is_relative_to(p.resolve()) for p in forbidden) or any(p in ('.git','node_modules') for p in local.parts):raise ValueError('Служебные файлы приложения не публикуются этим инструментом.')
                if local.stat().st_size>4*1024**2:raise ValueError('За один коммит файла поддерживается до 4 МБ.')
                raw=local.read_bytes()
            else:
                if not isinstance(args.get('content'),str):raise ValueError('Укажите содержимое или локальный файл.')
                raw=args['content'].encode('utf-8')
                if len(raw)>4*1024**2:raise ValueError('За один коммит файла поддерживается до 4 МБ.')
            filename=path.rsplit('/',1)[-1].lower()
            if filename=='.env' or filename.startswith('.env.') and filename not in ('.env.example','.env.sample') or filename in ('id_rsa','id_ed25519') or filename.endswith('.dpapi') or b'PRIVATE KEY-----' in raw or TOKEN_RE.search(raw.decode('utf-8','ignore')):raise ValueError('Файл содержит закрытый ключ или токен. Подготовьте вариант без секретов.')
            branch=str(args.get('branch') or self.request('GET',base)[0]['default_branch'])
            url=base+'/contents/'+urllib.parse.quote(path,safe='/')
            previous,_=self.request('GET',url,params={'ref':branch},missing=True)
            if previous and (not isinstance(previous,dict) or previous.get('type')!='file'):raise ValueError('Путь занят папкой.')
            sha=previous.get('sha') if previous else None
            if args.get('expected_sha') and args['expected_sha']!=sha:raise ValueError('Файл изменился. Прочитайте актуальную версию перед записью.')
            payload={'message':message,'content':base64.b64encode(raw).decode(),'branch':branch}
            if sha:payload['sha']=sha
            row,_=self.request('PUT',url,data=payload)
            return {'url':row['content']['html_url'],'path':path,'sha':row['content']['sha'],'commit':row['commit']['sha']}
        if action=='create_branch':
            name=str(args.get('branch',''));origin=str(args.get('base') or self.request('GET',base)[0]['default_branch'])
            if not name or len(name)>200 or any(ord(ch)<32 for ch in name):raise ValueError('Укажите имя ветки.')
            row,_=self.request('GET',base+'/git/ref/heads/'+urllib.parse.quote(origin,safe=''))
            created,_=self.request('POST',base+'/git/refs',data={'ref':'refs/heads/'+name,'sha':row['object']['sha']})
            return {'ref':created['ref'],'sha':created['object']['sha']}
        if action in ('create_pull_request','create_issue'):
            title=str(args.get('title','')).strip();body=str(args.get('body',''))
            if not 3<=len(title)<=256 or len(body)>20000:raise ValueError('Укажите заголовок и описание допустимой длины.')
            payload={'title':title,'body':body}
            if action=='create_pull_request':
                if not args.get('head'):raise ValueError('Укажите исходную ветку pull request.')
                if not isinstance(args.get('draft',True),bool):raise ValueError('Параметр draft должен быть true или false.')
                payload.update(head=args['head'],base=args.get('base') or self.request('GET',base)[0]['default_branch'],draft=args.get('draft',True))
            row,_=self.request('POST',base+('/pulls' if action=='create_pull_request' else '/issues'),data=payload)
            return {k:row.get(k) for k in ('number','html_url','state','title','draft')}
        raise ValueError('Неизвестное действие GitHub.')

access=GitHubAccess()
