"""Owner-selected installed browsers. Never reads or copies personal browser profiles."""
import json,os,pathlib,subprocess
from urllib.parse import urlsplit
PERSONAL={'chrome-personal':('Google Chrome','Chrome','google'),
          'yandex-personal':('Яндекс Браузер','Yandex','yandex'),
          'edge-personal':('Microsoft Edge','MSEdge','bing'),
          'tor-personal':('Tor Browser','Tor Browser','duckduckgo')}
NAMES={**{key:value[0]+' · мой профиль' for key,value in PERSONAL.items()},'builtin':'Встроенный браузер','chrome':'Google Chrome · профиль Freedom','yandex':'Яндекс · профиль Freedom'}
ENGINES={'auto','google','yandex','bing','duckduckgo'}
def candidates(browser):
    browser={'chrome-personal':'chrome','yandex-personal':'yandex','edge-personal':'edge'}.get(browser,browser)
    if browser=='tor-personal':
        return [pathlib.Path(p) for p in ('A:/CodexProjects/tools/torbrowser/app/Browser/firefox.exe','A:/CodexProjects/tools/tor-browser/Browser/firefox.exe')]
    roots=[os.environ.get('PROGRAMFILES','C:/Program Files'),os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'),os.environ.get('LOCALAPPDATA','')]
    relative={'chrome':'Google/Chrome/Application/chrome.exe','yandex':'Yandex/YandexBrowser/Application/browser.exe','edge':'Microsoft/Edge/Application/msedge.exe'}
    return [pathlib.Path(r)/relative[browser] for r in roots if r] if browser in relative else []
class BrowserLaunch:
    def __init__(self,root):self.path=pathlib.Path(root)/'data/browser/selection.json'
    def inventory(self):return [{'id':key,'name':name,'available':key=='builtin' or any(p.is_file() for p in candidates(key)),'visible':key!='builtin'} for key,name in NAMES.items()]
    def read(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
    def open_personal(self,url,browser='chrome-personal'):
        if browser not in PERSONAL:raise ValueError('Выберите установленный браузер из списка.')
        parsed=urlsplit(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Браузер открывает только адрес http/https без пароля в ссылке.')
        exe=next((p for p in candidates(browser) if p.is_file()),None)
        if not exe:raise ValueError(PERSONAL[browser][0]+' не найден; другой браузер автоматически не запускается.')
        # Normal installed Chrome and its own session: no copied profile, CDP,
        # incognito mode, proxy override or automation browser flags.
        subprocess.Popen([str(exe),*(['--new-window'] if browser!='tor-personal' else ['-new-window']),url],cwd=str(exe.parent) if browser=='tor-personal' else None,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return {'browser':browser,'external':True,'url':url,'state':'external','browser_name':PERSONAL[browser][0]+' · ваш профиль'}
    def choice(self,sid):
        saved=self.read();value=saved.get('sessions',{}).get(sid,saved.get('default',{}))
        browser=value.get('browser','builtin');engine=value.get('engine','auto')
        return {'browser':browser if browser in NAMES else 'builtin','engine':engine if engine in ENGINES else 'auto'}
    def select(self,sid,browser,engine):
        if not isinstance(browser,str) or not isinstance(engine,str) or browser not in NAMES or engine not in ENGINES:raise ValueError('Выберите браузер и поисковую систему из списка.')
        if not next(r for r in self.inventory() if r['id']==browser)['available']:raise ValueError(NAMES[browser]+' не найден на этом ПК.')
        saved=self.read();choice={'browser':browser,'engine':engine};saved.setdefault('sessions',{})[sid]=choice;saved['default']=choice
        self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.new');temp.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8');os.replace(temp,self.path)
        return choice
