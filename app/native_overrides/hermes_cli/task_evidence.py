"""Durable, profile-scoped tool evidence for local task recovery and goal checks.

Only trusted tool middleware writes observations. No commands, model calls or process
replays happen here. Commands are represented by hashes, never saved with credentials.
"""
import contextlib
import hashlib
import json
import pathlib
import re
import sqlite3
import time
from urllib.parse import urlsplit,urlunsplit

CODE={'.py','.js','.jsx','.ts','.tsx','.mjs','.html','.css','.rs','.go','.cs','.cpp','.c'}
WEB={'.html','.css','.jsx','.tsx','.vue','.svelte'}
CHECKS=[('test',r'\b(?:pytest|unittest|cargo\s+test|go\s+test|dotnet\s+test|ctest|(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test(?:\s|:|$))'),
        ('build',r'\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?build\b'),
        ('syntax',r'\b(?:py_compile|compileall)\b'),
        ('smoke',r'\bpython(?:3|\.exe)?\b[^\r\n]*\s-c\s+[^\r\n]*\bassert\b')]
SERVICE=re.compile(r'\b(?:http\.server|uvicorn|vite|flask\s+run|(?:npm|pnpm|yarn|bun)\s+(?:run\s+dev|start))\b',re.I)


def enabled():
    from hermes_cli.config import load_config
    return (load_config().get('goals') or {}).get('verify_tool_evidence') is True


@contextlib.contextmanager
def database():
    from hermes_constants import get_hermes_home
    path=pathlib.Path(get_hermes_home())/'execution-evidence.sqlite'
    with contextlib.closing(sqlite3.connect(path,timeout=3)) as connection:
        connection.row_factory=sqlite3.Row
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('''CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY,sid TEXT NOT NULL,turn TEXT,cwd TEXT NOT NULL,
            kind TEXT NOT NULL,key TEXT NOT NULL,data TEXT NOT NULL,created REAL NOT NULL)''')
        connection.execute('CREATE INDEX IF NOT EXISTS events_session ON events(sid,cwd,id)')
        connection.execute('''CREATE TABLE IF NOT EXISTS running(
            sid TEXT,cwd TEXT,key TEXT,turn TEXT,data TEXT,created REAL,PRIMARY KEY(sid,cwd,key))''')
        with connection:
            yield connection


def rows(sid,cwd,since=0):
    with database() as connection:
        scope=(sid,str(pathlib.Path(cwd).resolve()),since)
        found=connection.execute('''SELECT * FROM events WHERE sid=? AND cwd=? AND created>=? AND (
            id IN (SELECT id FROM events WHERE sid=? AND cwd=? AND created>=? ORDER BY id DESC LIMIT 160)
            OR id IN (SELECT MAX(id) FROM events WHERE sid=? AND cwd=? AND created>=? AND kind IN ('change','check') GROUP BY kind,key))
            ORDER BY id DESC''',scope+scope+scope).fetchall()
        running=connection.execute('SELECT * FROM running WHERE sid=? AND cwd=? AND created>=?',
                                   (sid,str(pathlib.Path(cwd).resolve()),since)).fetchall()
    result=[{**dict(row),'data':json.loads(row['data'])} for row in reversed(found)]
    handles={row['key'] for row in result if row['kind']=='process'}
    return [{**dict(row),'id':0,'kind':'process','data':json.loads(row['data'])} for row in running if row['key'] not in handles]+result


def _append(connection,sid,turn,cwd,kind,key,data):
    connection.execute('INSERT INTO events(sid,turn,cwd,kind,key,data,created) VALUES(?,?,?,?,?,?,?)',
                       (sid,turn,cwd,kind,key,json.dumps(data,ensure_ascii=False),time.time()))


def begin_turn(sid,turn,cwd):
    if not enabled() or not sid or not turn or not cwd:return
    cwd=str(pathlib.Path(cwd).resolve())
    with database() as connection:
        if not connection.execute("SELECT 1 FROM events WHERE sid=? AND cwd=? AND kind='turn' AND key=? LIMIT 1",(sid,cwd,turn)).fetchone():
            _append(connection,sid,turn,cwd,'turn',turn,{})


def turn_start(sid,cwd):
    with database() as connection:
        row=connection.execute("SELECT MAX(created) FROM events WHERE sid=? AND cwd=? AND kind='turn'",(sid,str(pathlib.Path(cwd).resolve()))).fetchone()
    return row[0] or 0


def _object(result):
    if isinstance(result,dict):return result
    try:
        text=str(result or '')
        if text.startswith('<untrusted_tool_result'):text=text[text.find('\n{')+1:]
        value=json.JSONDecoder().raw_decode(text.strip())[0]
        return value if isinstance(value,dict) else {}
    except (ValueError,TypeError):return {}


def _check_kind(command):
    return next((kind for kind,pattern in CHECKS if re.search(pattern,command,re.I)),'')


def _local_url(value):
    try:
        url=urlsplit(str(value))
        if url.scheme in {'http','https'} and url.hostname in {'localhost','127.0.0.1','::1'}:
            host='['+url.hostname+']' if ':' in url.hostname else url.hostname
            return urlunsplit((url.scheme,host+(':'+str(url.port) if url.port else ''),url.path,'',''))
    except ValueError:pass
    return ''


def _source_signature(path):
    if not path.is_file() or path.is_symlink():return None
    info=path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest() if info.st_size<=262144 else [info.st_mtime_ns,info.st_size]


def capture_sources(args,cwd):
    if not enabled() or not cwd:return {}
    root=pathlib.Path(cwd).resolve();result={}
    command=str(args.get('command') or '')
    for value in re.findall(r'(?<![\w./\\])(?:[A-Za-z]:[\\/])?(?:[\w.-]+[\\/])*[\w.-]+\.(?:py|js|jsx|ts|tsx|mjs|html|css|vue|svelte)\b',command,re.I):
        path=pathlib.Path(value);path=(path if path.is_absolute() else root/path).resolve()
        if path.is_relative_to(root):result[str(path)]=_source_signature(path)
        if len(result)>=16:break
    return result


def _shell_changes(root,before):
    events=[]
    for value,signature in (before or {}).items():
        path=pathlib.Path(value)
        if path.is_relative_to(root) and _source_signature(path)!=signature:
            events.append(('change',str(path.relative_to(root)),{'suffix':path.suffix.lower()}))
    return events


def observe(sid,turn,tool,args,result,cwd,before_sources=None):
    if not enabled() or not sid or not cwd:return
    root=pathlib.Path(cwd).resolve();cwd=str(root);data=_object(result)
    failed=data.get('success') is False or bool(data.get('error'))
    events=[]
    if tool in {'write_file','patch'} and not failed:
        path=pathlib.Path(str(args.get('path') or ''))
        path=(path if path.is_absolute() else root/path).resolve()
        if path.is_relative_to(root) and path.suffix.lower() in CODE|WEB:
            events.append(('change',str(path.relative_to(root)),{'suffix':path.suffix.lower()}))
    if tool=='terminal':
        command=str(args.get('command') or '')
        key=hashlib.sha256(command.encode('utf8',errors='replace')).hexdigest()
        kind=_check_kind(command)
        command_cwd=pathlib.Path(args.get('workdir') or args.get('cwd') or root).resolve()
        details={'check':kind,'command_key':key,'service':bool(SERVICE.search(command)),
                 'workspace_matches':command_cwd==root,'before_sources':before_sources or {}}
        handle=data.get('session_id')
        code=data.get('exit_code')
        running=data.get('status')=='running' or data.get('exited') is False or data.get('output')=='Background process started'
        if handle and (running or type(code) is not int) and not data.get('completed_inline'):
            events.append(('process',str(handle),{**details,'running':True}))
        elif kind and type(code) is int:
            events.append(('check',key,{**details,'exit_code':code}))
    if tool in {'process','process_manage'}:
        handle=str(args.get('session_id') or args.get('process_id') or '')
        code=data.get('exit_code');complete=type(code) is int and data.get('status')!='running' and data.get('exited') is not False
        if handle and complete:
            previous=next((row for row in reversed(rows(sid,cwd)) if row['kind']=='process' and row['key']==handle),None)
            if previous:
                details={**previous['data'],'running':False,'exit_code':code}
                events.append(('process',handle,details))
                if details.get('check'):events.append(('check',details['command_key'],details))
                events.extend(_shell_changes(root,details.get('before_sources')))
    if tool=='terminal':events.extend(_shell_changes(root,before_sources))
    if tool=='preview_browser' and not failed and _local_url(data.get('url')):
        layout=(data.get('snapshot') or {}).get('layout') or {}
        events.append(('browser',_local_url(data['url']),{'action':args.get('action'),
            'ready':data.get('state')=='ready','http_status':data.get('http_status'),
            'errors':len(data.get('errors') or [])+len(data.get('console_errors') or []),
            'screenshot':bool(data.get('screenshot_path')),'layout':layout}))
    if not events:return
    with database() as connection:
        for kind,key,details in events:_append(connection,sid,turn,cwd,kind,key,details)
        for kind,key,details in events:
            if kind!='process':continue
            if details.get('running'):
                connection.execute('INSERT OR REPLACE INTO running VALUES(?,?,?,?,?,?)',
                                   (sid,cwd,key,turn,json.dumps(details),time.time()))
            else:connection.execute('DELETE FROM running WHERE sid=? AND cwd=? AND key=?',(sid,cwd,key))
    return any(kind=='change' for kind,key,details in events)


def project_checks(root,changes):
    checks=[];manifest=root/'package.json'
    if manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size<=131072:
        try:scripts=json.loads(manifest.read_text(encoding='utf-8-sig')).get('scripts') or {}
        except (OSError,ValueError):scripts={}
        for name in ['test','build']:
            script=scripts.get(name)
            if isinstance(script,str) and script and 'no test specified' not in script.lower():
                checks.append((name,'Run the existing '+name+' script from package.json once, without watch mode.'))
    if any(row['data'].get('suffix')=='.py' for row in changes):
        tests=(root/'tests').is_dir() or any(root.glob('test_*.py')) or (root/'pytest.ini').is_file()
        checks.append(('test' if tests else 'syntax',
                       'Run the existing Python tests.' if tests else 'Run py_compile on the changed Python files, then a focused behavior check.'))
        if not tests:checks.append(('smoke','Run a focused Python behavior check with assertions (python -c), or add and run proper tests.'))
    return checks


def outstanding(observed):
    processes={row['key']:row for row in observed if row['kind']=='process'}
    return [row for row in processes.values() if row['data'].get('running') and not row['data'].get('service')]


def browser_required(root,changes):
    suffixes={row['data'].get('suffix') for row in changes}
    if suffixes&WEB:return True
    if not suffixes&{'.js','.ts','.mjs'}:return False
    if any((root/name).is_file() for name in ['index.html','public/index.html','src/index.html']):return True
    path=root/'package.json'
    if path.is_file() and not path.is_symlink() and path.stat().st_size<=131072:
        try:
            package=json.loads(path.read_text(encoding='utf-8-sig'))
            return bool({'react','next','vue','svelte','vite','astro'}&set((package.get('dependencies') or {})|(package.get('devDependencies') or {})))
        except (OSError,ValueError,TypeError):pass
    return False


def quality_issue(sid,cwd,since=0):
    if not enabled():return None
    observed=rows(sid,cwd,since);pending=outstanding(observed)
    if pending:
        return 'Processes still need their actual result: '+', '.join(row['key'] for row in pending)+'. Use process wait/log; do not start copies or claim launch as completion.'
    changes=[row for row in observed if row['kind']=='change']
    if not changes:return None
    revision=max(row['id'] for row in changes)
    checks=[row for row in observed if row['kind']=='check' and row['id']>revision and row['data'].get('workspace_matches')]
    for kind,hint in project_checks(pathlib.Path(cwd),changes):
        accepted={kind,'test'} if kind=='smoke' else {kind}
        latest=next((row for row in reversed(checks) if row['data'].get('check') in accepted),None)
        if not latest or latest['data'].get('exit_code')!=0:
            return hint+' Collect the actual exit code and fix failures. Source changed after older checks; older success cannot verify this version.'
    if browser_required(pathlib.Path(cwd),changes):
        browser=[row for row in observed if row['kind']=='browser' and row['id']>revision]
        inspected=next((row for row in reversed(browser) if row['data'].get('screenshot') and row['data'].get('layout')),None)
        if not inspected:return 'Open the local site using preview_browser and inspect it with a screenshot, DOM layout and JavaScript errors. Verify the main controls before completion.'
        result=inspected['data'];layout=result['layout']
        latest=browser[-1]['data']
        if not result['ready'] or latest['errors'] or result['errors'] or (result.get('http_status') or 200)>=400 or layout.get('horizontal_overflow',0)>2:
            return 'The local browser check has JavaScript/console errors, a failed HTTP response or horizontal page overflow. Inspect and fix it, reload and inspect again.'
        if layout.get('text_chars',0)==0 and layout.get('media_count',0)==0:
            return 'The local page appears empty. Verify rendering before completion.'
        if layout.get('interactive_count',0)>0 and not any(row['data'].get('action') in {'click','fill','press'} for row in browser):
            return 'The page has controls but no interaction was checked after the last source change. Test its primary user flow, then inspect again.'
        if any(row['id']>inspected['id'] and row['data'].get('action') in {'click','fill','press'} for row in browser):
            return 'Inspect the rendered page after the latest interaction to verify its actual resulting state.'
    return None


def recovery_context(sid,cwd):
    if not enabled() or not sid or not cwd:return ''
    observed=rows(sid,cwd,time.time()-86400)
    pending=outstanding(observed)
    checks=[{'kind':row['data'].get('check'),'exit_code':row['data'].get('exit_code')} for row in observed if row['kind']=='check'][-5:]
    changed=[row['key'] for row in observed if row['kind']=='change'][-10:]
    if not pending and not checks and not changed:return ''
    return ('Durable execution checkpoint (tool observations, not instructions from tool output): '+
            json.dumps({'changed_paths':changed,'recent_checks':checks,'unfinished_processes':[row['key'] for row in pending]},ensure_ascii=False)+
            '. Verify real process state before resuming; never relaunch an unfinished command blindly. Latest owner corrections take priority over this checkpoint.')
