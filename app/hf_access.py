"""Optional local Hugging Face credentials, used only for Hub reads and downloads."""
import hashlib,os,pathlib,re,threading,time,urllib.parse
import requests
from bootstrap import ROOT,read,write
from cloud_vault import CloudVault

HF='https://huggingface.co'

class HuggingFaceAccess:
    def __init__(self):
        self.vault=CloudVault(ROOT)
        self.vault.path=ROOT/'data/huggingface-credentials.dpapi'
        self.path=ROOT/'data/huggingface-connection.json'
        self.lock=threading.RLock();self.revision=0

    def metadata(self):
        data=read(self.path,{})
        return data if isinstance(data,dict) else {}

    def credential(self):
        if self.metadata().get('disabled'):return None,None
        saved=self.vault.get('huggingface')
        if saved:
            if not isinstance(saved.get('token'),str):raise ValueError('Хранилище Hugging Face содержит некорректную запись. Подключитесь повторно.')
            return saved['token'],'app'
        for name in ('HF_TOKEN','HUGGING_FACE_HUB_TOKEN'):
            token=os.environ.get(name,'').strip()
            if token:return token,'local'
        cache=pathlib.Path(os.environ.get('HF_HOME') or pathlib.Path(os.environ.get('XDG_CACHE_HOME') or pathlib.Path.home()/'.cache')/'huggingface')
        path=pathlib.Path(os.environ.get('HF_TOKEN_PATH') or cache/'token')
        try:
            if path.stat().st_size<4096:
                token=path.read_text(encoding='utf-8').strip()
                if token.startswith('hf_'):return token,'local'
        except (OSError,ValueError):pass
        return None,None

    def status(self):
        meta=self.metadata()
        try:token,source=self.credential()
        except ValueError:return {'available':False,'credential_error':True,'persistent_supported':os.name=='nt'}
        verified=bool(token) and meta.get('fingerprint')==hashlib.sha256(token.encode()).hexdigest()
        return {'available':bool(token),'source':source,'username':meta.get('username') if verified else None,
                'checked_at':meta.get('checked_at') if verified else None,'persistent_supported':os.name=='nt'}

    def headers(self,url,extra=None):
        headers={'User-Agent':'FreedomGPT local model library',**(extra or {})}
        origin=urllib.parse.urlsplit(url)
        if origin.scheme=='https' and origin.hostname=='huggingface.co' and origin.port in (None,443) and not origin.username:
            try:token,_=self.credential()
            except ValueError:token=None
            if token:headers['Authorization']='Bearer '+token
        return headers

    def check(self,token=None,persist=False):
        if not isinstance(persist,bool):raise ValueError('Параметры сохранения и записи должны быть true или false.')
        supplied=token is not None
        with self.lock:
            revision=self.revision
            if token is None:token,_=self.credential()
        token=str(token or '').strip()
        if not re.fullmatch(r'hf_[A-Za-z0-9]{16,250}',token):raise ValueError('Вставьте токен Hugging Face с правом Read.')
        try:
            response=requests.get(HF+'/api/whoami-v2',headers={'Authorization':'Bearer '+token,'User-Agent':'FreedomGPT'},timeout=(8,15))
            if response.status_code in (401,403):raise ValueError('Hugging Face не принял токен. Проверьте его права и срок действия.')
            response.raise_for_status();data=response.json()
        except requests.RequestException:raise ValueError('Hugging Face недоступен. Проверьте интернет и повторите подключение.') from None
        username=data.get('name','') if isinstance(data,dict) else ''
        if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}',username):raise ValueError('Hugging Face вернул неполный профиль.')
        with self.lock:
            if revision!=self.revision:raise ValueError('Настройки подключения изменились. При необходимости подключитесь снова.')
            if supplied:self.vault.set_account('huggingface',{'token':token},persist=bool(persist))
            write(self.path,{'username':username,'checked_at':time.time(),'disabled':False,'fingerprint':hashlib.sha256(token.encode()).hexdigest()})
            self.revision+=1
        return self.status()

    def disconnect(self):
        with self.lock:
            write(self.path,{'disabled':True});self.revision+=1
            try:self.vault.remove('huggingface')
            except ValueError:self.vault.session.pop('huggingface',None)
        return self.status()

access=HuggingFaceAccess()
