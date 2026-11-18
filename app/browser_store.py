"""Browser history and Windows user-bound logins, independent of agent memory."""
import hashlib
import pathlib
import sqlite3
import time
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from cloud_vault import CloudVault

def origin(value):
    parsed=urlsplit(str(value or ''))
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Откройте сайт http:// или https://.')
    host=parsed.hostname.lower()
    if ':' in host:host='['+host+']'
    port=parsed.port
    return parsed.scheme+'://'+host+(':'+str(port) if port and port!={'http':80,'https':443}[parsed.scheme] else '')

def history_url(value):
    try:
        base=origin(value);p=urlsplit(value)
        # Challenge links contain short-lived proof tokens rather than reusable pages.
        if p.hostname and (p.hostname.endswith('google.com') and p.path.startswith('/sorry/')
                           or p.hostname.endswith('yandex.ru') and p.path=='/showcaptcha'):
            return None
        private={'password','passwd','pwd','token','access_token','id_token','refresh_token','secret','code','state','session','sessionid','authorization','api_key','key'}
        query=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
                         if k.casefold() not in private and not any(x in k.casefold() for x in ('password','secret','token'))])
        return urlunsplit((p.scheme,urlsplit(base).netloc,p.path,query,''))[:6000]
    except (ValueError,TypeError):return None

class BrowserStore:
    def __init__(self,root):
        self.folder=pathlib.Path(root)/'data/browser';self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'history.sqlite'
        self.vault=CloudVault(root);self.vault.path=self.folder/'logins.dpapi'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS visits(id TEXT PRIMARY KEY,url TEXT NOT NULL,title TEXT NOT NULL,visited REAL NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS visits_time ON visits(visited DESC)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def visit(self,identifier,url,title):
        url=history_url(url)
        if not identifier or not url:return
        with self.connect() as db:
            db.execute('INSERT INTO visits VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title',
                       (str(identifier)[:100],url,str(title or url)[:500],time.time()))
    def history(self,query='',limit=150):
        query=str(query or '')[:200].casefold();pattern='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        with self.connect() as db:
            db.create_function('fold',1,lambda value:value.casefold())
            rows=db.execute("SELECT id,url,title,visited FROM visits WHERE fold(url) LIKE ? ESCAPE '\\' OR fold(title) LIKE ? ESCAPE '\\' ORDER BY visited DESC LIMIT ?",(pattern,pattern,min(200,max(1,int(limit))))).fetchall()
        return [dict(zip(('id','url','title','visited'),row)) for row in rows if history_url(row[1])]
    def clear_history(self):
        with self.connect() as db:db.execute('DELETE FROM visits')
    def logins(self,site):
        site=origin(site)
        return [{'id':key,'origin':row['origin'],'username':row['username'],'updated':row.get('updated')}
                for key,row in self.vault.persistent().items() if row.get('origin')==site]
    def save_login(self,site,username,password):
        site=origin(site)
        if urlsplit(site).scheme!='https' and urlsplit(site).hostname not in {'127.0.0.1','localhost','::1'}:
            raise ValueError('Сохраняйте пароли на сайте с HTTPS.')
        if not isinstance(username,str) or not username.strip() or len(username)>500:raise ValueError('Введите логин до 500 символов.')
        if not isinstance(password,str) or not password or len(password)>4096:raise ValueError('Введите пароль до 4096 символов.')
        username=username.strip();key=hashlib.sha256((site+'\0'+username).encode()).hexdigest()
        self.vault.set(key,{'origin':site,'username':username,'password':password,'updated':time.time()},persist=True)
        return {'id':key,'origin':site,'username':username}
    def login(self,site,key):
        row=self.vault.get(str(key))
        if not row or row.get('origin')!=origin(site):raise ValueError('Для этого сайта нет сохранённого входа.')
        return row
    def remove_login(self,site,key):
        self.login(site,key);self.vault.remove(key)
