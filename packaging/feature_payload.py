"""Allowlisted 1.5 agent features. Never copy a personal profile or data directory."""
import hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];APP=ROOT/'app'
MODULES=('account_connections.py','artifact_workspace.py','chat_branches.py','cloud_api.py','cloud_catalog.py','cloud_vault.py','github_access.py','goal_workspace.py','hf_access.py','model_advisor.py','preview_browser.py','project_memory_view.py','queue_order.py','rewards.py','rewards_catalog.py','workspace_features.py')
def tree(source,target):
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','runtime.json','node_modules','.git'))
def apply(bundle):
    bundle=pathlib.Path(bundle).resolve()
    if not bundle.is_relative_to((ROOT/'build').resolve()):raise ValueError('Feature staging must stay inside this project build folder')
    destination=bundle/'runtime/freedom';destination.mkdir(parents=True,exist_ok=True)
    for name in MODULES:shutil.copy2(APP/name,destination/name)
    for folder in ('agent_plugins','scripts'):tree(APP/folder,destination/folder)
    tree(APP/'builtin_plugins/coding-continuity',bundle/'stack/hermes-runtime/plugins/coding-continuity')
    # ESM imports resolve beside the preview script. Copy only Playwright, no dev dependencies.
    for package in ('playwright','playwright-core'):
        tree(APP/'node_modules'/package,destination/'node_modules'/package)
    manifest=json.loads((APP/'native_overrides/manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        relative=pathlib.PurePosixPath(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or relative.suffix!='.py':raise ValueError('Invalid native source override')
        source=APP/'native_overrides'/relative
        if hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Native source override hash mismatch')
        target=bundle/'runtime/hermes'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    return {'modules':len(MODULES),'native_overrides':len(manifest['files']),'personal_data_included':False}
