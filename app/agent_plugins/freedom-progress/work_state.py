"""Structured task/experiment records over the existing profile journal."""
import json
import re
import time
import hashlib
import pathlib
import platform


def environment(cwd):
    """Cheap observed compatibility stamp; never execute project code to inspect it."""
    manifests={}
    for name in ('pyproject.toml','requirements.txt','uv.lock','package.json','package-lock.json','pnpm-lock.yaml','Cargo.toml','Cargo.lock'):
        path=pathlib.Path(cwd)/name
        if path.is_file() and not path.is_symlink() and path.stat().st_size<=4*1024*1024:
            manifests[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'os':platform.system(),'machine':platform.machine(),'python':platform.python_version(),'manifests':manifests}


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):
        raise ValueError('Use a short stable ASCII id')
    return value


class WorkState:
    def __init__(self,journal):
        self.journal=journal
        with journal.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS work_items(sid TEXT,cwd TEXT,task TEXT,item TEXT,body TEXT,updated REAL,
                PRIMARY KEY(sid,cwd,task,item));
              CREATE TABLE IF NOT EXISTS work_hypotheses(sid TEXT,cwd TEXT,task TEXT,item TEXT,body TEXT,updated REAL,
                PRIMARY KEY(sid,cwd,task,item));
              CREATE TABLE IF NOT EXISTS work_skills(cwd TEXT,name TEXT,body TEXT,updated REAL,PRIMARY KEY(cwd,name));
            ''')

    def proofs(self,db,sid,cwd,ids,successful=False):
        if not isinstance(ids,list) or not 1<=len(ids)<=8 or any(type(i) is not int for i in ids):
            raise ValueError('Provide 1–8 real observation IDs from tool receipts')
        rows=[]
        for ident in ids:
            row=db.execute('SELECT * FROM observations WHERE id=? AND sid=? AND cwd=?',(ident,sid,cwd)).fetchone()
            if not row or row['tool']=='project_memory' or row['outcome']=='running':
                raise ValueError('Evidence is absent, belongs to another scope, or has not finished')
            if successful and row['outcome'] not in {'exit_zero','returned'}:
                raise ValueError('A failed check or file edit cannot verify a completed requirement')
            rows.append(dict(row))
        return rows

    def record(self,sid,cwd,payload):
        action=payload.get('action');task=identifier(payload.get('task','main'))
        if action not in {'plan','hypothesis','skill'}:raise ValueError('Use plan, hypothesis or skill')
        with self.journal.db() as db:
            if action=='plan':return self._plan(db,sid,cwd,task,payload)
            if action=='hypothesis':return self._hypothesis(db,sid,cwd,task,payload)
            return self._skill(db,sid,cwd,payload)

    def _plan(self,db,sid,cwd,task,payload):
        items=payload.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=40:raise ValueError('A plan needs 1–40 items')
        existing={row['item']:json.loads(row['body']) for row in db.execute(
            'SELECT * FROM work_items WHERE sid=? AND cwd=? AND task=?',(sid,cwd,task))}
        updates={};changed=db.execute("SELECT MAX(id) FROM observations WHERE sid=? AND cwd=? AND outcome='changed'",(sid,cwd)).fetchone()[0] or 0
        for item in items:
            if not isinstance(item,dict):raise ValueError('Each requirement is an object')
            ident=identifier(item.get('id'));text=item.get('text');status=item.get('status','pending')
            if not isinstance(text,str) or not 1<=len(text)<=700:raise ValueError('Requirement text is required, up to 700 characters')
            if status not in {'pending','working','waiting','done','cancelled'}:raise ValueError('Invalid requirement status')
            deps=item.get('depends_on',[])
            if not isinstance(deps,list) or len(deps)>12:raise ValueError('Invalid dependencies')
            deps=[identifier(x) for x in deps]
            proof=item.get('evidence',[])
            if status=='done':
                rows=self.proofs(db,sid,cwd,proof,successful=True)
                if any(row['id']<=changed for row in rows):raise ValueError('Source changed after this evidence; check the new version')
            updates[ident]={'id':ident,'text':text,'status':status,'depends_on':deps,'evidence':proof if status=='done' else [],
                            'note':str(item.get('note',''))[:500],'source':'agent claim linked to observations'}
        merged={**existing,**updates}
        if len(merged)>80:raise ValueError('This task already has 80 items; update existing IDs')
        for ident,item in merged.items():
            if any(dep not in merged or dep==ident for dep in item['depends_on']):raise ValueError('Missing or self dependency')
            if item['status']=='done' and any(merged[dep]['status']!='done' for dep in item['depends_on']):
                raise ValueError('Finish prerequisite requirements first')
        self._acyclic(merged)
        for ident,item in updates.items():
            db.execute('INSERT OR REPLACE INTO work_items VALUES(?,?,?,?,?,?)',(sid,cwd,task,ident,json.dumps(item,ensure_ascii=False),time.time()))
        return {'saved':True,'task':task,'updated_items':list(updates)}

    @staticmethod
    def _acyclic(items):
        visited=set();active=set()
        def visit(key):
            if key in active:raise ValueError('Cyclic requirement dependencies')
            if key in visited:return
            active.add(key)
            for dep in items[key]['depends_on']:visit(dep)
            active.remove(key);visited.add(key)
        for key in items:visit(key)

    def _hypothesis(self,db,sid,cwd,task,payload):
        ident=identifier(payload.get('id'));status=payload.get('status','open')
        if status not in {'open','supported','refuted','inconclusive'}:raise ValueError('Invalid hypothesis status')
        fields={name:str(payload.get(name,'')).strip()[:800] for name in ('claim','prediction','falsifier','result')}
        if not all(fields[name] for name in ('claim','prediction','falsifier')):
            raise ValueError('Specify the claim, expected observation, and what would disprove it')
        ids=payload.get('evidence',[])
        if status!='open':self.proofs(db,sid,cwd,ids)
        body={**fields,'id':ident,'status':status,'evidence':ids,'source':'agent interpretation of observations'}
        db.execute('INSERT OR REPLACE INTO work_hypotheses VALUES(?,?,?,?,?,?)',(sid,cwd,task,ident,json.dumps(body,ensure_ascii=False),time.time()))
        return {'saved':True,'hypothesis':ident,'status':status}

    def _skill(self,db,sid,cwd,payload):
        name=identifier(payload.get('name'));conditions=payload.get('conditions')
        if not isinstance(conditions,dict) or not conditions or len(conditions)>12:raise ValueError('List the observed applicability conditions')
        if any(not isinstance(k,str) or not isinstance(v,str) or len(k)>100 or len(v)>300 for k,v in conditions.items()):
            raise ValueError('Conditions must be short key/value strings')
        rows=self.proofs(db,sid,cwd,payload.get('evidence'),successful=True)
        last_change=db.execute("SELECT MAX(id) FROM observations WHERE sid=? AND cwd=? AND outcome='changed'",(sid,cwd)).fetchone()[0] or 0
        if any(row['id']<=last_change for row in rows):raise ValueError('Check the current source before recording skill applicability')
        body={'name':name,'conditions':conditions,'limitations':str(payload.get('limitations',''))[:800],
              'evidence':payload['evidence'],'source_sid':sid,'environment':environment(cwd),
              'source':'agent-recorded applicability; matching fingerprints do not prove every dependency is installed'}
        db.execute('INSERT OR REPLACE INTO work_skills VALUES(?,?,?,?)',(cwd,name,json.dumps(body,ensure_ascii=False),time.time()))
        return {'saved':True,'skill':name,'conditions':conditions}

    def summary(self,sid,cwd):
        with self.journal.db() as db:
            latest=db.execute('SELECT task FROM work_items WHERE sid=? AND cwd=? ORDER BY updated DESC LIMIT 1',(sid,cwd)).fetchone()
            rows=db.execute('SELECT * FROM work_items WHERE sid=? AND cwd=? AND task=? ORDER BY updated DESC',(sid,cwd,latest[0])).fetchall() if latest else []
            last_change=db.execute("SELECT MAX(id) FROM observations WHERE sid=? AND cwd=? AND outcome='changed'",(sid,cwd)).fetchone()[0] or 0
            correction=db.execute('SELECT MAX(created) FROM corrections WHERE sid=? AND cwd=?',(sid,cwd)).fetchone()[0] or 0
            hypotheses=db.execute('SELECT body FROM work_hypotheses WHERE sid=? AND cwd=? ORDER BY updated DESC LIMIT 4',(sid,cwd)).fetchall()
        if not rows:return {'items':[],'hypotheses':[json.loads(x[0]) for x in hypotheses]}
        task=rows[0]['task'];items=[]
        for row in rows:
            if row['task']!=task:continue
            body=json.loads(row['body'])
            if body['status']=='done' and (min(body['evidence'],default=0)<=last_change or row['updated']<correction):
                body['status']='needs_recheck'
            items.append(body)
        ready={x['id'] for x in items if x['status']=='done'}
        next_items=[x['id'] for x in items if x['status'] in {'pending','working','needs_recheck'} and all(dep in ready for dep in x['depends_on'])]
        return {'task':task,'items':items,'next_items':next_items,'hypotheses':[json.loads(x[0]) for x in hypotheses]}

    def skill(self,cwd,name):
        with self.journal.db() as db:row=db.execute('SELECT body FROM work_skills WHERE cwd=? AND name=?',(cwd,name)).fetchone()
        if not row:return None
        body=json.loads(row[0]);current=environment(cwd);saved=body.get('environment')
        body['status']='environment_unchanged' if saved==current else 'needs_recheck'
        body['current_environment']=current
        body['message']='Проверь заявленные зависимости перед применением. Изменение системы или файлов зависимостей требует повторной проверки навыка.'
        return body
