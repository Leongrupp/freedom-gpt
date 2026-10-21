"""Read the local project memory used by the installed provider, without model calls."""
import importlib.util
import json
import pathlib
import re


def store_for(portable,snapshot,sid):
    source=portable.HOME/'plugins/coding-continuity/project_store.py'
    spec=importlib.util.spec_from_file_location('freedom_project_store_view',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    candidate=(snapshot.get('info') or {}).get('cwd')
    session=re.sub(r'[^A-Za-z0-9_.-]','_',snapshot.get('stored_session_id') or sid)
    binding=portable.HOME/'continuity'/session/'project.json'
    if binding.is_file():candidate=json.loads(binding.read_text(encoding='utf-8-sig'))['project']
    return module.ProjectStore(candidate) if candidate else None
