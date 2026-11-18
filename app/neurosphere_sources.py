"""Read local project/chat METADATA; never attach to or mutate another agent.

Codex: read-only SQLite and workspace hints. Claude Code: session indexes, with
bounded header reads when an index is absent. Credentials and message bodies
are neither returned nor imported into Freedom's conversation history.
"""
import datetime
import json
import os
import pathlib
import re
import sqlite3
import time

_cache={}
def clean(value, limit=240):
    text=re.sub(r'[\x00-\x1f]+',' ',str(value or ''))
    text=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9]{15,}|gh[pousr]_[A-Za-z0-9_]{15,})\b','[ключ скрыт]',text)
    return text[:limit]

def local_path(value):
    if not isinstance(value,str) or '\0' in value:return None
    value=value.removeprefix('\\\\?\\')
    if value.startswith(('\\\\','//')):return None  # Do not wake remote shares during a map refresh.
    path=pathlib.Path(value)
    try:return path.resolve() if path.is_absolute() else None
    except (OSError,ValueError):return None

def stamp(value):
    try:
        if isinstance(value,(int,float)):return value/1000 if value>100000000000 else value
        return datetime.datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError):return 0

def read_json(path, limit=8_000_000):
    try:
        if path.stat().st_size>limit:return {}
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}

def discover(workspace, *, profile=None, codex_home=None, claude_home=None, cached=True):
    workspace=pathlib.Path(workspace).resolve()
    profile=pathlib.Path(profile or os.environ.get('USERPROFILE') or pathlib.Path.home())
    codex=pathlib.Path(codex_home or os.environ.get('CODEX_HOME') or profile/'.codex')
    claude=pathlib.Path(claude_home or os.environ.get('CLAUDE_CONFIG_DIR') or profile/'.claude')
    key=(str(workspace),str(codex),str(claude))
    if cached and key in _cache and time.monotonic()-_cache[key][0]<20:return _cache[key][1]
    projects={};chats=[];sources=[]
    def project(path,source,name=None):
        p=local_path(str(path))
        if not p:return None
        # Folder identity is canonical; a Codex/Claude chat about an existing A:
        # project binds to that project rather than duplicating it by app name.
        if p.is_relative_to(workspace):
            relative=p.relative_to(workspace)
            p=workspace/relative.parts[0] if relative.parts else workspace
        identifier=str(p).casefold()
        row=projects.setdefault(identifier,{'name':clean(name or p.name,120),'path':str(p),'exists':p.is_dir(),'read_only':not p.is_relative_to(workspace),'sources':[]})
        if source not in row['sources']:row['sources'].append(source)
        return str(p)
    def chat(source,identifier,title,cwd,updated=0,created=0,archived=False,name=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,140}',str(identifier or '')):return
        bound=project(cwd,source,name) if cwd else None
        chats.append({'id':source+':'+str(identifier),'source':source,'title':clean(title or name or 'Сохранённый чат'),'project':bound,'updated':stamp(updated),'created':stamp(created),'archived':bool(archived),'external':True,'running':False,'live_available':False})
    codex_count=0;codex_error=False
    global_state=read_json(codex/'.codex-global-state.json')
    if not isinstance(global_state,dict):global_state={}
    hints=global_state.get('thread-workspace-root-hints') or {}
    named_roots={}
    try:databases=sorted((p for p in codex.glob('state_*.sqlite') if re.fullmatch(r'state_\d+\.sqlite',p.name)),key=lambda p:int(re.search(r'(\d+)\.sqlite$',p.name)[1]),reverse=True) if codex.is_dir() else []
    except OSError:databases=[];codex_error=True
    if databases:
        try:
            connection=sqlite3.connect(databases[0].resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
            try:
                connection.row_factory=sqlite3.Row;connection.execute('PRAGMA query_only=ON')
                tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if {'projects','project_roots'}<=tables:
                    for row in connection.execute('SELECT p.id,p.name,r.path FROM projects p JOIN project_roots r ON p.id=r.project_id'):
                        path=local_path(row['path'])
                        if path:
                            named_roots[row['id']]=(path,row['name']);project(path,'codex',row['name'])
                columns={r[1] for r in connection.execute('PRAGMA table_info(threads)')}
                selected=[k for k in ('id','title','cwd','updated_at','created_at','archived','project_id') if k in columns]
                if {'id','cwd'}<=columns:
                    for raw in connection.execute('SELECT '+','.join(selected)+' FROM threads ORDER BY updated_at DESC LIMIT 10000'):
                        row=dict(raw);path=local_path(row.get('cwd'));name=None
                        named=named_roots.get(row.get('project_id'))
                        if named:path,name=named
                        elif path:
                            hint=local_path(hints.get(row['id'])) if isinstance(hints,dict) else None
                            if hint and path.is_relative_to(hint) and not path.is_relative_to(workspace):path=hint
                        before=len(chats);chat('codex',row['id'],row.get('title'),path,row.get('updated_at'),row.get('created_at'),row.get('archived',False),name);codex_count+=len(chats)-before
            finally:connection.close()
        except (sqlite3.Error,OSError):codex_error=True
    sources.append({'id':'codex','name':'Codex','state':'unavailable' if codex_error else 'ready' if databases else 'not_found','chats':codex_count,'message':'Не удалось прочитать локальный каталог. Повторим позже.' if codex_error else 'Локальный каталог прочитан; история остаётся в Codex.' if databases else 'Локальная история пока не найдена.'})
    claude_count=0;claude_error=False;seen=set();claude_projects=claude/'projects'
    if claude_projects.is_dir():
        try:
            for folder in claude_projects.iterdir():
                if not folder.is_dir() or folder.is_symlink():continue
                data=read_json(folder/'sessions-index.json')
                entries=data.get('entries',[]) if isinstance(data,dict) else []
                for row in entries if isinstance(entries,list) else []:
                    if not isinstance(row,dict):continue
                    identifier=row.get('sessionId');seen.add(str(identifier));before=len(chats)
                    chat('claude',identifier,row.get('summary') or row.get('customTitle') or 'Чат Claude Code',row.get('projectPath') or data.get('originalPath'),row.get('modified'),row.get('created'))
                    claude_count+=len(chats)-before
                for file in folder.glob('*.jsonl'):
                    if file.stem in seen or file.name.startswith('agent-') or file.is_symlink():continue
                    path=None;identifier=file.stem;title=None
                    # Header metadata only. No recursive message-body or tool-output ingestion.
                    with file.open('rb') as stream:
                        header=stream.read(65536).decode('utf-8',errors='replace')
                    for line in header.splitlines():
                        try:record=json.loads(line)
                        except ValueError:continue
                        if record.get('type')=='custom-title':title=record.get('customTitle')
                        if record.get('cwd'):path=record['cwd'];identifier=record.get('sessionId') or identifier
                    if path:
                        before=len(chats);chat('claude',identifier,title or 'Чат Claude Code',path,file.stat().st_mtime);claude_count+=len(chats)-before
        except OSError:claude_error=True
    sources.append({'id':'claude','name':'Claude Code','state':'unavailable' if claude_error else 'ready' if claude_projects.is_dir() else 'not_found','chats':claude_count,'message':'Не удалось прочитать локальный каталог. Повторим позже.' if claude_error else 'Локальная история прочитана без изменения файлов.' if claude_projects.is_dir() else 'Локальная история пока не найдена. Появится после работы в Claude Code.'})
    result={'projects':list(projects.values()),'sessions':chats,'sources':sources,'updated':time.time()}
    if cached:_cache[key]=(time.monotonic(),result)
    return result
