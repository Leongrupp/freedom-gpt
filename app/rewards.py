"""Local game ledger: durable sources, repeatable results and one-time milestones."""
from __future__ import annotations
import asyncio,contextlib,datetime,hashlib,json,math,pathlib,sqlite3,threading,time,urllib.parse,uuid
from aiohttp import web
from PIL import Image
from rewards_catalog import VERSION,TRACKS,BY_METRIC,MANUAL,BADGES,public_tracks

def digest(value):return hashlib.sha256(str(value).encode('utf-8')).hexdigest()
def level_of(xp):return (math.isqrt(1+int(xp)//25)-1)//2+1

class FreedomRewards:
    def __init__(self,root,portable,db,bridge):
        self.root,self.portable,self._db,self.bridge=root,portable,db,bridge
        self.lock=threading.RLock();self.task=None;self.last_media_scan=0;self.warning=None
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS freedom_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS freedom_counters(metric TEXT PRIMARY KEY,value INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS freedom_events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_key TEXT UNIQUE NOT NULL,
              kind TEXT NOT NULL,metrics TEXT NOT NULL,freedom INTEGER NOT NULL,xp INTEGER NOT NULL,
              label TEXT NOT NULL,label_en TEXT NOT NULL,source TEXT NOT NULL,occurred REAL NOT NULL,recorded REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS freedom_usage(source_key TEXT PRIMARY KEY,input_total INTEGER NOT NULL,output_total INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS freedom_unlocks(badge_id TEXT PRIMARY KEY,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS freedom_days(day TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS freedom_results(id TEXT PRIMARY KEY,source_key TEXT UNIQUE NOT NULL,
              category TEXT NOT NULL,title TEXT NOT NULL,evidence TEXT NOT NULL,session_id TEXT,created REAL NOT NULL);
            ''')
            c.execute('INSERT OR IGNORE INTO freedom_meta VALUES(?,?)',('installation',uuid.uuid4().hex))
            c.execute('INSERT OR IGNORE INTO freedom_meta VALUES(?,?)',('notifications','true'))

    @contextlib.contextmanager
    def db(self):
        c=self._db()
        try:
            with c:yield c
        finally:c.close()

    @contextlib.contextmanager
    def native(self):
        with contextlib.closing(sqlite3.connect('file:'+(self.portable.HOME/'state.db').as_posix()+'?mode=ro',uri=True,timeout=3)) as c:
            c.row_factory=sqlite3.Row;yield c

    @staticmethod
    def add_counter(c,key,value):
        c.execute('INSERT INTO freedom_counters VALUES(?,?) ON CONFLICT(metric) DO UPDATE SET value=value+excluded.value',(key,int(value)))

    def event(self,c,key,metric=None,amount=1,*,freedom=0,xp=0,label='',label_en='',source=None,when=None,active=True,kind=None):
        metrics=metric if isinstance(metric,dict) else {metric:int(amount)} if metric else {}
        now=time.time();when=min(float(when or now),now)
        inserted=c.execute('''INSERT OR IGNORE INTO freedom_events
          (event_key,kind,metrics,freedom,xp,label,label_en,source,occurred,recorded) VALUES(?,?,?,?,?,?,?,?,?,?)''',
          (key,kind or (metric if isinstance(metric,str) else 'usage'),json.dumps(metrics),int(freedom),int(xp),label,label_en,
           json.dumps(source or {},ensure_ascii=False),when,now)).rowcount
        if not inserted:return False
        for name,value in metrics.items():self.add_counter(c,name,value)
        self.add_counter(c,'_freedom',freedom);self.add_counter(c,'_xp',xp)
        if active:
            day=datetime.datetime.fromtimestamp(when).date().isoformat()
            if c.execute('INSERT OR IGNORE INTO freedom_days VALUES(?)',(day,)).rowcount:
                self.event(c,'day:'+day,'days',freedom=BY_METRIC['days']['freedom'],xp=BY_METRIC['days']['xp'],
                           label='Активный день',label_en='Active day',source={'day':day},when=when,active=False)
        return True

    def activity(self,c,metric,key,*,label=None,label_en=None,source=None,when=None,active=True):
        row=BY_METRIC[metric]
        return self.event(c,key,metric,freedom=row['freedom'],xp=row['xp'],label=label or row['counter'],
                          label_en=label_en or row['counter_en'],source=source,when=when,active=active)

    def unlock(self,c):
        days=[datetime.date.fromisoformat(r[0]) for r in c.execute('SELECT day FROM freedom_days ORDER BY day')]
        longest=run=0;prior=None
        for day in days:
            run=run+1 if prior and day-prior==datetime.timedelta(days=1) else 1
            longest=max(longest,run);prior=day
        c.execute('INSERT INTO freedom_counters VALUES(?,?) ON CONFLICT(metric) DO UPDATE SET value=MAX(value,excluded.value)',('streak',longest))
        values={r[0]:r[1] for r in c.execute('SELECT * FROM freedom_counters')};new=[]
        for badge in BADGES:
            if values.get(badge['metric'],0)<badge['threshold']:continue
            if not c.execute('INSERT OR IGNORE INTO freedom_unlocks VALUES(?,?)',(badge['id'],time.time())).rowcount:continue
            self.event(c,'badge:'+badge['id'],freedom=badge['freedom'],xp=badge['xp'],label=badge['name'],label_en=badge['name_en'],
                       source={'badge_id':badge['id']},active=False,kind='achievement')
            new.append(badge)
        return new

    def known(self):
        with self.db() as c:return {r[0] for r in c.execute("SELECT event_key FROM freedom_events WHERE kind<>'usage'")}

    def file_key(self,path,metric):
        path=path.resolve()
        for folder,prefix in ((self.root,'app'),(self.portable.STACK/'creative-kit','creative'),(self.portable.workspace_root(),'projects')):
            if path.is_relative_to(folder.resolve()):return metric+':'+digest(prefix+'/'+path.relative_to(folder.resolve()).as_posix().casefold())
        raise ValueError('Outside workspace')

    def valid_media(self,path,kind):
        path=pathlib.Path(path).resolve()
        roots=[self.portable.workspace_root(),self.root/'output',self.portable.STACK/'creative-kit/output']
        if not any(path.is_relative_to(root.resolve()) for root in roots) or not path.is_file():return False
        if kind=='images':
            if path.stat().st_size>80*1024**2:return False
            with Image.open(path) as image:
                if image.width*image.height>40_000_000:return False
                image.verify()
        else:
            if path.stat().st_size<1000:return False
            with path.open('rb') as f:
                if f.read(4)!=b'\x1aE\xdf\xa3':return False
        return True

    def media_sources(self,known):
        if time.monotonic()-self.last_media_scan<20:return []
        result=[]
        for folder in dict.fromkeys([self.root/'output/images',self.portable.STACK/'creative-kit/output/images']):
            for report in folder.glob('*/generation.json'):
                try:
                    if report.stat().st_size>128*1024:continue
                    data=json.loads(report.read_text(encoding='utf-8-sig'));path=pathlib.Path(data.get('image',''))
                    if data.get('success') is not True:continue
                    key=self.file_key(path,'images')
                    if key not in known and self.valid_media(path,'images'):result.append(('images',key,report.stat().st_mtime,{'file':str(path),'kind':'generation_report'}))
                except (OSError,ValueError,TypeError,Image.DecompressionBombError):continue
        for report in (self.root/'data/video-jobs').glob('*.json'):
            try:
                if report.stat().st_size>128*1024:continue
                data=json.loads(report.read_text(encoding='utf-8-sig'));path=pathlib.Path(data.get('output',''))
                if data.get('state')!='complete':continue
                key=self.file_key(path,'videos')
                if key not in known and self.valid_media(path,'videos'):result.append(('videos',key,data.get('updated_at') or report.stat().st_mtime,{'file':str(path),'job_id':data.get('id'),'kind':'completed_job'}))
            except (OSError,ValueError,TypeError):continue
        with self.db() as c:
            cloud=[dict(r) for r in c.execute("SELECT id,path,finished FROM cloud_images WHERE state='completed'")]
        for row in cloud:
            try:
                path=pathlib.Path(row['path']);key=self.file_key(path,'images')
                if key not in known and self.valid_media(path,'images'):result.append(('images',key,row['finished'],{'file':str(path),'job_id':row['id'],'kind':'cloud_completed'}))
            except (OSError,ValueError,TypeError):continue
        self.last_media_scan=time.monotonic();return result

    def sync(self):
        with self.lock:
            try:
                with self.native() as c:
                    usages=[dict(r) for r in c.execute('''SELECT session_id,model,billing_provider,billing_base_url,billing_mode,task,
                      input_tokens,output_tokens,api_call_count,first_seen,last_seen FROM session_model_usage''')]
                    admissions=[dict(r) for r in c.execute('''SELECT a.admission_id,a.target_session_id,s.started_at FROM session_admissions a
                      JOIN sessions s ON s.id=a.target_session_id WHERE a.status='terminal' AND a.outcome='completed' ''')]
                self.warning=None
            except sqlite3.Error:
                usages=[];admissions=[];self.warning='История модели временно недоступна. Сохранённый прогресс остаётся на месте.'
            with self.db() as c:
                timings={r['admission_id']:dict(r) for r in c.execute('SELECT admission_id,finished,created FROM workspace_turns')}
                branches=[dict(r) for r in c.execute('SELECT child_id,parent_id,created FROM chat_branches')]
            media=self.media_sources(self.known())
            with self.db() as c:
                c.execute('BEGIN IMMEDIATE');before=c.execute('SELECT COALESCE(MAX(id),0) FROM freedom_events').fetchone()[0]
                xp_before=(c.execute("SELECT value FROM freedom_counters WHERE metric='_xp'").fetchone() or [0])[0]
                for row in usages:
                    identity=digest(json.dumps([row[k] for k in ('session_id','model','billing_provider','billing_base_url','billing_mode','task')]))
                    old=c.execute('SELECT input_total,output_total FROM freedom_usage WHERE source_key=?',(identity,)).fetchone() or (0,0)
                    incoming=max(int(row['input_tokens'] or 0),old[0]);outgoing=max(int(row['output_tokens'] or 0),old[1])
                    delta_in,delta_out=incoming-old[0],outgoing-old[1]
                    if delta_in or delta_out:
                        self.event(c,'usage:'+identity+':'+str(incoming)+':'+str(outgoing),{'tokens':delta_in+delta_out,'generated_tokens':delta_out},
                                   label='Токены моделей',label_en='Model tokens',when=row['last_seen'],source={'session_id':row['session_id']},kind='usage')
                        c.execute('INSERT INTO freedom_usage VALUES(?,?,?) ON CONFLICT(source_key) DO UPDATE SET input_total=excluded.input_total,output_total=excluded.output_total',(identity,incoming,outgoing))
                    if row['api_call_count'] and row['model']:
                        self.activity(c,'models','model:'+digest(row['model']),when=row['first_seen'],active=False)
                for row in admissions:
                    when=timings.get(row['admission_id'],{});when=when.get('finished') or when.get('created') or row['started_at']
                    self.activity(c,'turns','turn:'+row['admission_id'],when=when,source={'admission_id':row['admission_id'],'session_id':row['target_session_id']})
                for row in branches:self.activity(c,'branches','branch:'+row['child_id'],when=row['created'],active=False,source={'session_id':row['child_id']})
                for metric,key,when,source in media:self.activity(c,metric,key,when=when,source=source)
                new=self.unlock(c);after=c.execute('SELECT COALESCE(MAX(id),0) FROM freedom_events').fetchone()[0]
                xp_after=(c.execute("SELECT value FROM freedom_counters WHERE metric='_xp'").fetchone() or [0])[0]
                c.execute('INSERT INTO freedom_meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_sync',str(time.time())))
            return {'changed':before!=after,'unlocks':new,'level_up':level_of(xp_after)>level_of(xp_before)}

    def snapshot(self):
        with self.db() as c:
            counters={r[0]:r[1] for r in c.execute('SELECT * FROM freedom_counters')}
            unlocked={r[0]:r[1] for r in c.execute('SELECT * FROM freedom_unlocks')}
            meta={r[0]:r[1] for r in c.execute('SELECT * FROM freedom_meta')}
            history=[dict(r) for r in c.execute('''SELECT id,kind,freedom,xp,label,label_en,occurred,recorded
              FROM freedom_events WHERE freedom<>0 OR xp<>0 ORDER BY id DESC LIMIT 40''')]
            results=[dict(r) for r in c.execute('SELECT * FROM freedom_results ORDER BY created DESC LIMIT 30')]
            last=c.execute('SELECT MAX(day) FROM freedom_days').fetchone()[0]
        xp=counters.get('_xp',0);n=(math.isqrt(1+xp//25)-1)//2;level=n+1
        floor,ceiling=100*n*(n+1),100*(n+1)*(n+2)
        ranks=[(50,'Пионер Freedom','Freedom pioneer'),(25,'Легенда','Legend'),(15,'Визионер','Visionary'),(10,'Архитектор','Architect'),(6,'Мастер','Master'),(3,'Создатель','Creator'),(1,'Искра Freedom','Freedom spark')]
        rank=next(r for r in ranks if level>=r[0]);streak=0
        if last:
            day=datetime.date.fromisoformat(last);today=datetime.date.today()
            if today-day in (datetime.timedelta(0),datetime.timedelta(days=1)):
                with self.db() as c:
                    days={r[0] for r in c.execute('SELECT day FROM freedom_days')}
                while day.isoformat() in days:streak+=1;day-=datetime.timedelta(days=1)
        return {'catalog_version':VERSION,'profile':{'level':level,'rank':rank[1],'rank_en':rank[2],
                'freedom':counters.get('_freedom',0),'xp':xp,'level_xp':xp-floor,'level_target':ceiling-floor,'next_level_xp':ceiling,
                'streak':streak,'unlocked':len(unlocked),'total_badges':len(BADGES)},
                'counters':{k:v for k,v in counters.items() if not k.startswith('_')},'tracks':public_tracks(),
                'badges':[{**badge,'earned_at':unlocked.get(badge['id'])} for badge in BADGES],
                'history':history,'results':results,'notifications':meta.get('notifications')=='true',
                'last_sync':float(meta.get('last_sync','0')),'warning':self.warning,'local_game_points':True}

    def candidates(self,sid=None):
        with self.native() as c:
            rows=[dict(r) for r in c.execute('''SELECT a.admission_id,a.target_session_id,s.title,s.started_at FROM session_admissions a
              JOIN sessions s ON s.id=a.target_session_id WHERE a.status='terminal' AND a.outcome='completed'
              ORDER BY a.seq DESC LIMIT 100''')]
        with self.db() as c:
            names={r[0]:r[1] for r in c.execute('SELECT id,title FROM chats')}
            claimed={r[0] for r in c.execute('SELECT source_key FROM freedom_results')}
            details={r[0]:r[1] for r in c.execute('SELECT admission_id,COALESCE(finished,created) FROM workspace_turns')}
        rows=[{**row,'title':names.get(row['target_session_id']) or row['title'] or 'Чат',
               'finished_at':details.get(row['admission_id']) or row['started_at']} for row in rows
              if 'turn:'+row['admission_id'] not in claimed]
        if sid:rows.sort(key=lambda r:r['target_session_id']!=sid)
        return rows[:50]

    def claim(self,data):
        if data.get('confirmed') is not True:raise ValueError('Подтвердите, что результат проверен и готов.')
        metric=str(data.get('category',''));title=str(data.get('title','')).strip()
        if metric not in MANUAL or not 3<=len(title)<=140:raise ValueError('Выберите направление и название результата от 3 до 140 символов.')
        source_type=data.get('source_type');sid=''
        if source_type=='turn':
            admission=str(data.get('admission_id',''))
            with self.native() as c:row=c.execute("SELECT target_session_id FROM session_admissions WHERE admission_id=? AND status='terminal' AND outcome='completed'",(admission,)).fetchone()
            if not row:raise ValueError('Выберите завершённый ответ агента.')
            sid=row[0];source_key='turn:'+admission;evidence='Ответ агента'
        elif source_type=='evidence':
            value=str(data.get('evidence','')).strip()
            if not 1<=len(value)<=1500 or any(ord(ch)<32 for ch in value):raise ValueError('Укажите файл, папку проекта или адрес результата.')
            uri=urllib.parse.urlsplit(value)
            if uri.scheme in ('http','https'):
                if not uri.hostname or uri.username or uri.password:raise ValueError('Укажите обычную ссылку без логина и пароля.')
                # Query strings and fragments are never retained in the game journal.
                evidence=urllib.parse.urlunsplit((uri.scheme,uri.netloc.lower(),uri.path.rstrip('/'),'',''))
                source_key='result:'+digest(evidence)
            else:
                path=pathlib.Path(value).resolve()
                roots=[self.portable.workspace_root(),self.root/'output']+([self.portable.HOME/'skills'] if metric=='learning' else [])
                if not path.exists() or not any(path.is_relative_to(p.resolve()) for p in roots):raise ValueError('Файл или папка должны существовать в рабочем пространстве.')
                forbidden=[self.root/p for p in ('runtime','data','logs','archive','.cache','.tmp')]+[self.portable.STACK/'models']
                if any(path.is_relative_to(p.resolve()) for p in forbidden):raise ValueError('Выберите результат проекта, а не служебные файлы или веса модели.')
                evidence=str(path);source_key='result:'+digest(self.file_key(path,'result'))
        else:raise ValueError('Укажите источник результата.')
        with self.lock,self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM freedom_results WHERE source_key=?',(source_key,)).fetchone():
                return {'duplicate':True,'error':'Этот результат уже засчитан. Для следующего результата укажите другой источник.'}
            ident=uuid.uuid4().hex;now=time.time()
            before={r[0]:r[1] for r in c.execute("SELECT metric,value FROM freedom_counters WHERE metric IN ('_freedom','_xp')")}
            c.execute('INSERT INTO freedom_results VALUES(?,?,?,?,?,?,?)',(ident,source_key,metric,title,evidence,sid,now))
            self.activity(c,metric,'result:'+ident,label=title,label_en=title,source={'result_id':ident,'confirmation':'user'},when=now)
            new=self.unlock(c)
            after={r[0]:r[1] for r in c.execute("SELECT metric,value FROM freedom_counters WHERE metric IN ('_freedom','_xp')")}
        return {'duplicate':False,'freedom':after.get('_freedom',0)-before.get('_freedom',0),
                'xp':after.get('_xp',0)-before.get('_xp',0),'unlocks':new,
                'level_up':level_of(after.get('_xp',0))>level_of(before.get('_xp',0))}

    async def announce(self,result):
        if not result.get('changed',True):return
        snapshot=self.snapshot()
        await self.bridge.broadcast({'type':'rewards.changed','profile':snapshot['profile'],'notify':snapshot['notifications'],
            'unlocks':[{k:b[k] for k in ('id','name','name_en','freedom','xp')} for b in result.get('unlocks',[])][:4],
            'level_up':result.get('level_up',False)})

    async def start(self):
        async def loop():
            first=True
            while True:
                try:
                    result=await asyncio.to_thread(self.sync)
                    if not first:await self.announce(result)
                    first=False
                except asyncio.CancelledError:raise
                except Exception:self.warning='Не удалось обновить награды. Попробуем снова; сохранённый прогресс не изменён.'
                await asyncio.sleep(12)
        self.task=asyncio.create_task(loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.task

    def register(self,app):
        async def status(request):return web.json_response(self.snapshot())
        async def candidates(request):return web.json_response({'candidates':await asyncio.to_thread(self.candidates,request.query.get('sid'))})
        async def claim(request):
            result=await asyncio.to_thread(self.claim,await request.json())
            if not result['duplicate']:await self.announce(result)
            return web.json_response(result,status=409 if result['duplicate'] else 200)
        async def settings(request):
            data=await request.json()
            if not isinstance(data.get('notifications'),bool):raise ValueError('Укажите состояние уведомлений.')
            with self.db() as c:c.execute('UPDATE freedom_meta SET value=? WHERE key=?',('true' if data['notifications'] else 'false','notifications'))
            return web.json_response({'notifications':data['notifications']})
        async def exported(request):
            with self.db() as c:
                events=[dict(r) for r in c.execute('SELECT * FROM freedom_events ORDER BY id')]
                installation=c.execute("SELECT value FROM freedom_meta WHERE key='installation'").fetchone()[0]
            payload={'format':'freedom-local-game-progress','version':VERSION,'installation':installation,'exported_at':time.time(),
                     'local_game_points':True,'snapshot':self.snapshot(),'ledger':events}
            return web.Response(body=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8'),content_type='application/json',
                headers={'Content-Disposition':'attachment; filename="Freedom-progress.json"'})
        app.router.add_get('/api/rewards',status);app.router.add_get('/api/rewards/candidates',candidates)
        app.router.add_post('/api/rewards/results',claim);app.router.add_post('/api/rewards/settings',settings)
        app.router.add_get('/api/rewards/export',exported)
