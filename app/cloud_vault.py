"""User-bound secret storage. API keys never enter settings, browser storage or history."""
import base64,ctypes,json,os,pathlib,threading,uuid

def account_options(data,*,write_access=False,token_required=False):
    if not isinstance(data,dict):raise ValueError('Параметры подключения должны быть объектом JSON.')
    for name in ('persist','allow_write'):
        if name in data and not isinstance(data[name],bool):raise ValueError('Параметры сохранения и записи должны быть true или false.')
    if token_required and (not isinstance(data.get('token'),str) or not data['token'].strip()):raise ValueError('Введите токен для подключения аккаунта.')
    return {'persist':data.get('persist',False),**({'allow_write':data.get('allow_write',False)} if write_access else {})}


class CloudVault:
    def __init__(self,root):
        self.path=pathlib.Path(root)/'data/cloud-credentials.dpapi'
        self.lock=threading.RLock()
        self.session={}

    @staticmethod
    def crypt(raw,decode=False):
        if os.name!='nt':raise ValueError('Постоянное хранение ключей в этой ОС пока недоступно. Используйте хранение до закрытия приложения.')
        from ctypes import wintypes
        class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
        buffer=ctypes.create_string_buffer(raw);source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
        api=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
        if decode:
            fn=api.CryptUnprotectData;fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
            ok=fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
        else:
            fn=api.CryptProtectData;fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
            ok=fn(ctypes.byref(source),'Freedom GPT API keys',None,None,None,1,ctypes.byref(target))
        if not ok:raise ValueError('Windows не смогла открыть хранилище ключей. После переноса на другой ПК введите ключи заново.')
        try:return ctypes.string_at(target.data,target.size)
        finally:kernel.LocalFree(target.data)

    def persistent(self):
        if not self.path.exists():return {}
        try:
            data=json.loads(self.crypt(self.path.read_bytes(),True))
            if not isinstance(data,dict) or not all(isinstance(k,str) and isinstance(v,dict) for k,v in data.items()):raise ValueError('Invalid vault shape')
            return data
        except (OSError,ValueError):raise ValueError('Хранилище API-ключей недоступно для этого пользователя Windows. Существующий файл сохранён.')

    def get(self,provider):
        with self.lock:return self.session.get(provider) or self.persistent().get(provider)

    def set(self,provider,value,persist=True):
        with self.lock:
            if not persist:
                self.remove(provider);self.session[provider]=value;return
            data=self.persistent();data[provider]=value
            self.path.parent.mkdir(exist_ok=True,parents=True)
            temporary=self.path.with_name(uuid.uuid4().hex+'.dpapi.new')
            with temporary.open('wb') as stream:
                stream.write(self.crypt(json.dumps(data).encode()));stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path);self.session.pop(provider,None)

    def set_account(self,provider,value,persist=False):
        """Recover a standalone account vault only after the new credential was verified.

        Keep an unreadable encrypted original for the original PC/user. Other API vaults
        are never recovered implicitly, and any failed replacement restores the original.
        """
        with self.lock:
            try:self.persistent()
            except ValueError:
                folder=self.path.parent.parent/'archive'/('account-vault-'+uuid.uuid4().hex)
                folder.mkdir(parents=True,exist_ok=False);backup=folder/self.path.name
                os.replace(self.path,backup)
                try:self.set(provider,value,persist=persist)
                except Exception:
                    if self.path.exists():os.replace(self.path,folder/('replacement-'+self.path.name))
                    os.replace(backup,self.path);raise
                return
            self.set(provider,value,persist=persist)

    def remove(self,provider):
        with self.lock:
            self.session.pop(provider,None);data=self.persistent()
            if provider not in data:return
            data.pop(provider)
            temporary=self.path.with_name(uuid.uuid4().hex+'.dpapi.new')
            temporary.write_bytes(self.crypt(json.dumps(data).encode()));os.replace(temporary,self.path)
