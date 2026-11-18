"""Stage source from the author's working install, never its profile or models."""
import ast
import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = ROOT.parent / 'freedom-gpt'
APP = ROOT / 'app'
VERSION = '1.7.0'


def main():
    backup = ROOT/'archive/release-1.7.0-source-before.zip'
    if not backup.exists():
        with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as z:
            for folder in ('app', 'packaging', 'site', '.github', 'docs'):
                for p in (ROOT/folder).rglob('*'):
                    if not p.is_file() or any(x in p.parts for x in ('node_modules','runtime','dist','data','__pycache__')):
                        continue
                    z.write(p, p.relative_to(ROOT).as_posix())
    core = ('bootstrap.py','server.py','library.py','gguf_info.py','updater.py',
            'apply_update.py','update_protocol.py','launch.py','stop.py',
            'engine_supervisor.py','generate-image-request.py','init-project-memory.py')
    sources = {p.name:p for p in (LIVE/'runtime/freedom').glob('*.py')}
    # Mirror the actual import priority, not stale duplicate modules at the root.
    for p in LIVE.glob('*.py'): sources.setdefault(p.name,p)
    modules = set(core)
    modules.update(('personal_voice.py','personal_speech.py','personal_enhance.py',
                    'file_convert.py','convert_worker.py','speech_worker.py',
                    'clone_worker.py','camera_job.py','music_worker.py','phone_access.py',
                    'voice_clone.py','speech_numbers.py','startup_support.py','window_instance.py'))
    todo = list(modules)
    while todo:
        name = todo.pop()
        if name not in sources: raise ValueError('Missing release source: '+name)
        tree = ast.parse(sources[name].read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            imports = [x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            for imported in imports:
                candidate = imported.split('.')[0]+'.py'
                if candidate in sources and candidate not in modules:
                    modules.add(candidate);todo.append(candidate)
    # Optional worker entry points referenced by path rather than Python imports.
    for name in sorted(modules):
        shutil.copy2(sources[name],APP/name)
    ignore = shutil.ignore_patterns('__pycache__','*.pyc','runtime.json','node_modules','.git')
    for folder in ('src','scripts','agent_plugins','public'):
        shutil.copytree(LIVE/folder,APP/folder,dirs_exist_ok=True,ignore=ignore)
    for name in ('index.html','catalog.json','freedom.ico'):
        shutil.copy2(LIVE/name,APP/name)
    meta=json.loads((LIVE/'version.json').read_text());meta.update(version=VERSION,local_build='release-20261118',ui_revision='agent-1.7.0')
    (APP/'version.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for name in ('package.json','package-lock.json'):
        p=APP/name;d=json.loads(p.read_text());d['version']=VERSION
        if 'packages' in d:d['packages']['']['version']=VERSION
        p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')
    # Preserve the complete prior native override set and refresh changed files.
    manifest=APP/'native_overrides/manifest.json';old=json.loads(manifest.read_text())
    paths={e['path'] for e in old['files']}
    donor=ROOT/'build/FreedomGPT-1.6.0/runtime/hermes'
    native=LIVE/'runtime/hermes'
    for p in native.rglob('*.py'):
        if '__pycache__' in p.parts:continue
        rel=p.relative_to(native);q=donor/rel
        if not q.exists() or p.read_bytes()!=q.read_bytes():paths.add(rel.as_posix())
    entries=[]
    for rel in sorted(paths):
        raw=(native/rel).read_bytes();ast.parse(raw,filename=rel)
        target=APP/'native_overrides'/rel;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw);entries.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    manifest.write_text(json.dumps({'source':'Working runtime, reviewed public delta for '+VERSION,'files':entries},indent=2)+'\n',encoding='utf8')
    # Existing portable packaging stages non-root modules from this explicit list.
    feature=ROOT/'packaging/feature_payload.py';s=feature.read_text(encoding='utf8')
    start=s.index('MODULES=');end=s.index('\ndef tree',start)
    feature.write_text(s[:start]+'MODULES='+repr(tuple(sorted(modules-set(core))))+'\n'+s[end:],encoding='utf8')
    # Installed copies carry a private adapter; releases keep that adapter empty.
    # No personal speech profiles, browser sessions, keys, chats or hardware tuning
    # are copied. Optional native voice/camera backends remain capability-gated.
    report={'version':VERSION,'modules':sorted(modules),'native_overrides':len(entries),
            'personal_data_copied':False,'model_weights_copied':False}
    out=ROOT/'logs/release-1.7.0';out.mkdir(parents=True,exist_ok=True)
    (out/'source-stage.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
