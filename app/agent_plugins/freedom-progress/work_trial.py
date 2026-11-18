"""Explicit, bounded code experiments using Hermes' existing checkpoint store.

Run via the normal terminal tool: begin / status / rollback / keep.
Rollback never executes automatically merely because a check failed.
"""
import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import time
import uuid
import sys

SOURCE={'.py','.js','.jsx','.ts','.tsx','.mjs','.css','.html','.json','.toml','.yaml','.yml','.md'}


def safe_path(cwd,relative):
    root=pathlib.Path(cwd).absolute()
    if not root.is_relative_to(pathlib.Path(os.environ.get('FREEDOM_ROOT',cwd))/'workspaces') or root==pathlib.Path(os.environ.get('FREEDOM_ROOT',cwd))/'workspaces':
        raise ValueError('Select a project inside Freedom GPT workspaces')
    rel=pathlib.Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not re.fullmatch(r'[\w ./\\-]+',str(relative)):
        raise ValueError('Use a plain project-relative path without pathspec expressions')
    path=root/rel
    if path.suffix.lower() not in SOURCE or any(p.startswith('.') for p in rel.parts):
        raise ValueError('Trials support ordinary source files, not hidden/configuration directories')
    for parent in [path,*path.parents]:
        if parent.is_symlink() or getattr(parent,'is_junction',lambda:False)():
            raise ValueError('Links/junctions are not supported in a reversible trial')
        if parent==root.parent:break
    if path.exists() and (not path.is_file() or path.stat().st_size>2*1024*1024):raise ValueError('Trial file is not a small regular source file')
    return path


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


@contextlib.contextmanager
def database():
    from hermes_constants import get_hermes_home
    with contextlib.closing(sqlite3.connect(pathlib.Path(get_hermes_home())/'work-trials.sqlite',timeout=5)) as db:
        db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE IF NOT EXISTS trials(id TEXT PRIMARY KEY,sid TEXT,cwd TEXT,state TEXT,body TEXT,created REAL)')
        with db:yield db


def manager():
    from tools.checkpoint_manager import CheckpointManager
    return CheckpointManager(enabled=True,max_snapshots=30,max_total_size_mb=500,max_file_size_mb=2)


def begin(sid,cwd,files):
    if not sid or not 1<=len(files)<=8:raise ValueError('Select 1–8 source files and the current session ID')
    with database() as db:
        if db.execute("SELECT 1 FROM trials WHERE cwd=? AND state='active'",(cwd,)).fetchone():raise ValueError('Finish the active trial in this project first')
    paths={str(pathlib.Path(name)):safe_path(cwd,name) for name in files}
    before={name:file_hash(path) for name,path in paths.items()}
    mgr=manager()
    if not mgr.ensure_checkpoint(cwd,reason='Freedom reversible experiment'):raise ValueError('Checkpoint failed; do not begin the risky change')
    snapshots=mgr.list_checkpoints(cwd)
    if not snapshots:raise ValueError('Checkpoint unavailable')
    commit=snapshots[0]['hash']
    # Confirm selected existing files are really included, not excluded by snapshot policy.
    from tools.checkpoint_manager import _run_git,_store_path
    for name,digest in before.items():
        if digest is not None:
            ok,_,_=_run_git(['cat-file','-e',commit+':'+pathlib.Path(name).as_posix()],_store_path(),cwd)
            if not ok:raise ValueError('Selected file is excluded from the native snapshot: '+name)
    ident=uuid.uuid4().hex
    with database() as db:
        if db.execute("SELECT 1 FROM trials WHERE cwd=? AND state='active'",(cwd,)).fetchone():raise ValueError('Finish the active trial in this project first')
        db.execute('INSERT INTO trials VALUES(?,?,?,?,?,?)',(ident,sid,cwd,'active',json.dumps({'commit':commit,'before':before,'written':{}},ensure_ascii=False),time.time()))
    return {'trial':ident,'state':'active','files':list(paths),'checkpoint':commit}


def note_write(sid,cwd,path):
    with database() as db:
        row=db.execute("SELECT * FROM trials WHERE sid=? AND cwd=? AND state='active'",(sid,cwd)).fetchone()
        if not row:return
        body=json.loads(row['body'])
        for name in body['before']:
            target=safe_path(cwd,name)
            if target==pathlib.Path(path).absolute():body['written'][name]=file_hash(target)
        db.execute('UPDATE trials SET body=? WHERE id=?',(json.dumps(body),row['id']))


def finish(sid,cwd,ident,action):
    if action not in {'status','keep','rollback'}:raise ValueError('Unknown trial action')
    with database() as db:
        row=db.execute('SELECT * FROM trials WHERE id=? AND sid=? AND cwd=?',(ident,sid,cwd)).fetchone()
        if not row:raise ValueError('Trial does not belong to this session/project')
        body=json.loads(row['body'])
        if action=='status':return {'trial':ident,'state':row['state'],**body}
        if row['state']!='active':raise ValueError('Trial is already closed')
        restored=[]
        if action=='rollback':
            selected=[]
            for name,before in body['before'].items():
                path=safe_path(cwd,name);now=file_hash(path)
                if now==before:continue
                if name not in body['written'] or now!=body['written'][name]:
                    raise ValueError('File changed outside this agent trial; rollback refused: '+name)
                if before is not None and now is None:raise ValueError('Deleted source needs manual recovery: '+name)
                selected.append((name,path,before))
            mgr=manager()
            for name,path,before in selected:
                if before is None:
                    # Preserve a newly created file rather than deleting it.
                    from hermes_constants import get_hermes_home
                    target=pathlib.Path(get_hermes_home())/'trial-recovery'/ident/name
                    target.parent.mkdir(parents=True,exist_ok=True);os.replace(path,target)
                else:
                    result=mgr.restore(cwd,body['commit'],file_path=name,safe=True)
                    if not result.get('success'):raise ValueError('Native rollback failed: '+str(result.get('error')))
                    if file_hash(path)!=before:raise ValueError('Restored bytes differ; inspect the checkpoint before continuing')
                restored.append(name)
        db.execute('UPDATE trials SET state=? WHERE id=?',('rolled_back' if action=='rollback' else 'kept',ident))
        return {'trial':ident,'state':'rolled_back' if action=='rollback' else 'kept','restored':restored,'recheck_required':True}


def main():
    # This is a short-lived CLI process. Snapshots must use installed Git, never
    # start a dependency installer in the middle of an agent experiment.
    os.environ['HERMES_DISABLE_LAZY_INSTALLS']='1'
    # The terminal deliberately strips Hermes' PYTHONPATH. Resolve only this
    # installation's source, keeping the inherited, profile-bound HERMES_HOME.
    plugin_dir=pathlib.Path(__file__).resolve().parent
    runtime_file=plugin_dir/'runtime.json'
    if runtime_file.is_file():
        app=(plugin_dir/json.loads(runtime_file.read_text(encoding='utf8'))['app_relative']).resolve()
    else:app=plugin_dir.parents[1]
    source=app/'runtime/hermes'
    if not (source/'hermes_constants.py').is_file():raise RuntimeError('Hermes installation is unavailable')
    sys.path.insert(0,str(source))
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['begin','status','rollback','keep'])
    parser.add_argument('--sid',required=True);parser.add_argument('--cwd',required=True);parser.add_argument('--trial')
    parser.add_argument('--files',nargs='+',default=[]);args=parser.parse_args()
    try:
        from gateway.session_context import get_session_env
        bound=get_session_env('HERMES_SESSION_ID','')
        if bound and bound!=args.sid:raise ValueError('Session mismatch')
        result=begin(args.sid,str(pathlib.Path(args.cwd).absolute()),args.files) if args.action=='begin' else finish(args.sid,str(pathlib.Path(args.cwd).absolute()),args.trial,args.action)
        print(json.dumps(result,ensure_ascii=True))
    except (OSError,ValueError,sqlite3.Error) as exc:
        print(json.dumps({'success':False,'error':str(exc)},ensure_ascii=True));raise SystemExit(1)

if __name__=='__main__':main()
