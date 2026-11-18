"""Read-only project/chat binding metadata for the local spatial workspace."""
import json,pathlib,re,time

def index_projects(workspace,home,sessions,snapshots,external=None):
    workspace=pathlib.Path(workspace).resolve();home=pathlib.Path(home)
    projects={}
    for p in workspace.iterdir():
        try:
            resolved=p.resolve()
            if p.is_dir() and not p.name.startswith('.') and resolved.is_relative_to(workspace):projects[str(resolved).casefold()]={'name':p.name,'path':str(resolved),'exists':True}
        except (OSError,ValueError):continue
    chats=[]
    for row in sessions:
        sid=str(row.get('id') or '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,140}',sid):continue
        cwd=(snapshots.get(sid,{}).get('info') or {}).get('cwd')
        if not cwd:
            try:
                saved=json.loads((home/'continuity'/sid/'project.json').read_text(encoding='utf-8-sig'));cwd=saved.get('project')
            except (OSError,ValueError,AttributeError):pass
        bound=None
        if isinstance(cwd,str):
            try:candidate=pathlib.Path(cwd).resolve()
            except (OSError,ValueError):candidate=home.resolve()
            if candidate.is_relative_to(workspace):
                relative=candidate.relative_to(workspace)
                parent=workspace/relative.parts[0] if relative.parts else workspace
                bound=str(parent);key=bound.casefold()
                projects.setdefault(key,{'name':parent.name,'path':bound,'exists':parent.is_dir()})
        chats.append({k:row.get(k) for k in ['id','title','running','archived','pinned','created','updated','message_count']}|{'project':bound})
    for row in projects.values():row.update(sources=[],read_only=False)
    for chat in chats:
        chat['source']='freedom'
        if chat['project']:
            row=projects.get(chat['project'].casefold())
            if row and 'freedom' not in row['sources']:row['sources'].append('freedom')
    for row in (external or {}).get('projects',[]):
        key=str(row['path']).casefold()
        if key in projects:
            for source in row.get('sources',[]):
                if source not in projects[key]['sources']:projects[key]['sources'].append(source)
        else:projects[key]=row
    return {'projects':sorted(projects.values(),key=lambda p:p['name'].casefold()),'sessions':chats,'external_sessions':(external or {}).get('sessions',[]),'sources':[{'id':'freedom','name':'Freedom','state':'ready','chats':len(chats),'message':'Чаты и задачи локального агента.'},*(external or {}).get('sources',[])],'workspace':str(workspace),'updated':time.time()}
