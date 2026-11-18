"""Profile-scoped execution journal. Observations and model claims stay separate."""
import contextlib
import hashlib
import json
import pathlib
import re
import sqlite3
import time


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode('utf8',errors='replace')).hexdigest()


def clean(value,limit=1400):
    text=str(value or '')
    text=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{15,})\b','[SECRET]',text)
    text=re.sub(r'(?im)((?:password|passwd|api[_ -]?key|authorization|cookie|secret|пароль|токен)\s*[:=]\s*)[^\n]+',r'\1[SECRET]',text)
    text=re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@',r'\1[SECRET]@',text)
    text=re.sub(r'(?i)([?&](?:token|key|secret|signature|auth)=)[^\s&#]+',r'\1[SECRET]',text)
    return text[:limit].strip()


class Journal:
    def __init__(self,home):
        self.path=pathlib.Path(home)/'reasoning-journal.sqlite'

    @contextlib.contextmanager
    def db(self):
        with contextlib.closing(sqlite3.connect(self.path,timeout=3)) as db:
            db.row_factory=sqlite3.Row
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
              CREATE TABLE IF NOT EXISTS turns(sid TEXT,turn TEXT,cwd TEXT,request TEXT,mode TEXT,
                reviewed INTEGER DEFAULT 0,created REAL,PRIMARY KEY(sid,turn));
              CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,sid TEXT,turn TEXT,cwd TEXT,
                tool TEXT,call_key TEXT,result_key TEXT,outcome TEXT,category TEXT,created REAL);
              CREATE INDEX IF NOT EXISTS observations_scope ON observations(sid,cwd,id);
              CREATE TABLE IF NOT EXISTS checkpoints(id INTEGER PRIMARY KEY,sid TEXT,turn TEXT,cwd TEXT,
                body TEXT,created REAL);
              CREATE TABLE IF NOT EXISTS lessons(cwd TEXT,rule_key TEXT,body TEXT,source_sid TEXT,
                created REAL,PRIMARY KEY(cwd,rule_key));
              CREATE TABLE IF NOT EXISTS corrections(sid TEXT,turn TEXT,cwd TEXT,body TEXT,
                correction_key TEXT,created REAL,PRIMARY KEY(sid,turn,correction_key));
              CREATE TABLE IF NOT EXISTS memory_receipts(sid TEXT,turn TEXT,cwd TEXT,call_key TEXT,boundary TEXT,
                body TEXT,PRIMARY KEY(sid,turn,cwd,call_key,boundary));
            ''')
            with db:yield db

    def begin(self,sid,turn,cwd,request,mode,lesson=''):
        with self.db() as db:
            added=db.execute('INSERT OR IGNORE INTO turns VALUES(?,?,?,?,?,0,?)',
                (sid,turn,cwd,clean(request),mode,time.time())).rowcount
            if added and lesson:
                body=clean(lesson,600)
                db.execute('INSERT OR REPLACE INTO lessons VALUES(?,?,?,?,?)',
                           (cwd,digest(body),body,sid,time.time()))

    def observe(self,sid,turn,cwd,tool,args,result,failed=False,category='',changed=False):
        # Persist hashes, not command arguments, credentials or raw external output.
        code=result.get('exit_code',result.get('returncode'))
        outcome='failed' if failed else ('running' if result.get('status')=='running' or result.get('exited') is False else 'returned')
        if not failed and type(code) is int and code==0 and outcome!='running':outcome='exit_zero'
        if changed:outcome='changed'
        key=digest([tool,{k:v for k,v in args.items() if k not in {'timeout','yield_time_ms','background'}}])
        normalized={k:v for k,v in result.items() if k not in {'duration_ms','duration_seconds','timestamp','created_at','screenshot_path'}}
        with self.db() as db:
            db.execute('INSERT INTO observations(sid,turn,cwd,tool,call_key,result_key,outcome,category,created) VALUES(?,?,?,?,?,?,?,?,?)',
                       (sid,turn,cwd,tool,key,digest(normalized),outcome,category,time.time()))
            # Bound each session journal without deleting checkpoints or owner rules.
            db.execute('DELETE FROM observations WHERE sid=? AND id < COALESCE((SELECT id FROM observations WHERE sid=? ORDER BY id DESC LIMIT 1 OFFSET 1999),0)',(sid,sid))
            rows=db.execute('SELECT * FROM observations WHERE sid=? AND turn=? AND cwd=? ORDER BY id DESC LIMIT 8',(sid,turn,cwd)).fetchall()
        since_change=next((i for i,row in enumerate(rows) if row['outcome']=='changed'),len(rows))
        actionable=[row for row in rows[:since_change] if row['tool'] not in {'project_memory','process','process_manage'}]
        repeat=sum(row['call_key']==key and row['result_key']==digest(normalized) for row in actionable)
        failures=0
        for row in actionable:
            if row['outcome']!='failed' or row['category']!=category:break
            failures+=1
        return repeat>=3 or failures>=3

    def checkpoint(self,sid,turn,cwd,content):
        try:body=json.loads(content)
        except (ValueError,TypeError):return False
        if not isinstance(body,dict) or body.get('freedom_reasoning')!=1:return False
        # A model-written checkpoint never becomes trusted tool evidence.
        allowed=('objective','hypotheses','check','result','next_step','requirements','lesson','wait_condition')
        data={key:clean(json.dumps(body[key],ensure_ascii=False) if isinstance(body[key],(list,dict)) else body[key],1800)
              for key in allowed if key in body}
        data['source']='agent_claim; verify against tool observations'
        if len(data)==1:return False
        with self.db() as db:
            db.execute('INSERT INTO checkpoints(sid,turn,cwd,body,created) VALUES(?,?,?,?,?)',
                       (sid,turn,cwd,json.dumps(data,ensure_ascii=False),time.time()))
        return True

    def snapshot(self,sid,cwd,turn=''):
        with self.db() as db:
            current=db.execute('SELECT * FROM turns WHERE sid=? AND cwd=? ORDER BY created DESC LIMIT 1',(sid,cwd)).fetchone()
            checkpoints=db.execute('SELECT body FROM checkpoints WHERE sid=? AND cwd=? ORDER BY id DESC LIMIT 2',(sid,cwd)).fetchall()
            observations=db.execute('SELECT tool,outcome,category,call_key FROM observations WHERE sid=? AND cwd=? ORDER BY id DESC LIMIT 8',(sid,cwd)).fetchall()
            lessons=db.execute('SELECT body,source_sid FROM lessons WHERE cwd=? ORDER BY created DESC LIMIT 5',(cwd,)).fetchall()
            corrections=db.execute('SELECT body,turn FROM corrections WHERE sid=? AND cwd=? ORDER BY created DESC LIMIT 3',(sid,cwd)).fetchall()
        return {'request':dict(current) if current else None,
                'checkpoints':[json.loads(row['body']) for row in checkpoints],
                'observations':[dict(row) for row in observations],
                'owner_preferences':[dict(row) for row in lessons],
                'owner_corrections':[dict(row) for row in corrections]}

    def current(self,sid,turn):
        with self.db() as db:
            row=db.execute('SELECT * FROM turns WHERE sid=? AND turn=?',(sid,turn)).fetchone()
        return dict(row) if row else None

    def memory_receipt(self,sid,turn,cwd,args,result=None):
        if args.get('action')!='record':return None
        with self.db() as db:
            observed=db.execute("SELECT MAX(id) FROM observations WHERE sid=? AND turn=? AND cwd=? AND tool<>'project_memory'",(sid,turn,cwd)).fetchone()[0] or 0
            correction=db.execute('SELECT MAX(created) FROM corrections WHERE sid=? AND turn=? AND cwd=?',(sid,turn,cwd)).fetchone()[0] or 0
            key=(sid,turn,cwd,digest(args),str((observed,correction)))
            if result is not None:
                if result.get('saved') and not result.get('already_saved'):
                    body={k:result[k] for k in ('saved','id','project','source','freedom_work') if k in result}
                    db.execute('INSERT OR IGNORE INTO memory_receipts VALUES(?,?,?,?,?,?)',(*key,json.dumps(body,ensure_ascii=False)))
                return None
            row=db.execute('SELECT body FROM memory_receipts WHERE sid=? AND turn=? AND cwd=? AND call_key=? AND boundary=?',key).fetchone()
        if row:return {**json.loads(row[0]),'already_saved':True,
            'notice':'Эта же запись уже сохранена. Нового результата нет. Не сохраняй её снова; дай пользователю итог или выполни другой незавершённый пункт.'}

    def repeated_final_memory(self,sid,turn,cwd):
        with self.db() as db:
            current=db.execute('SELECT reviewed FROM turns WHERE sid=? AND turn=?',(sid,turn)).fetchone()
            if not current or not current[0]:return False
            rows=db.execute('SELECT tool,call_key,created FROM observations WHERE sid=? AND turn=? AND cwd=? ORDER BY id DESC LIMIT 3',(sid,turn,cwd)).fetchall()
            correction=db.execute('SELECT MAX(created) FROM corrections WHERE sid=? AND turn=? AND cwd=?',(sid,turn,cwd)).fetchone()[0] or 0
        return (len(rows)==3 and all(x['tool']=='project_memory' and x['call_key']==rows[0]['call_key'] for x in rows)
                and rows[-1]['created']>correction)

    def correction(self,sid,turn,cwd,text):
        body=clean(text)
        with self.db() as db:
            added=db.execute('INSERT OR IGNORE INTO corrections VALUES(?,?,?,?,?,?)',
                (sid,turn,cwd,body,digest(body),time.time())).rowcount
            if added:
                # A new steer supersedes the earlier review and fast-conversation route.
                db.execute("UPDATE turns SET reviewed=0,mode='task' WHERE sid=? AND turn=?",(sid,turn))

    def review(self,sid,cwd):
        with self.db() as db:
            row=db.execute('SELECT * FROM turns WHERE sid=? AND cwd=? ORDER BY created DESC LIMIT 1',(sid,cwd)).fetchone()
            if not row or row['reviewed'] or row['mode']=='conversation':return None
            calls=db.execute("SELECT COUNT(*) FROM observations WHERE sid=? AND turn=? AND tool<>'project_memory'",(sid,row['turn'])).fetchone()[0]
            if calls==0:return None
            db.execute('UPDATE turns SET reviewed=1 WHERE sid=? AND turn=?',(sid,row['turn']))
            return row['request']
