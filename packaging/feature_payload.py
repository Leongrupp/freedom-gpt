"""Allowlisted 1.5 agent features. Never copy a personal profile or data directory."""
import hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];APP=ROOT/'app'
MODULES=('account_connections.py', 'activity_feed.py', 'agent_autonomy.py', 'agent_personality.py', 'arcade_integration.py', 'arshi_policy.py', 'artifact_workspace.py', 'auto_models.py', 'autonomy_profile.py', 'browser_launch.py', 'browser_store.py', 'camera_job.py', 'camera_obs.py', 'camera_studio.py', 'chat_branches.py', 'chat_history.py', 'chat_recovery.py', 'chat_trash.py', 'clone_worker.py', 'cloud_api.py', 'cloud_catalog.py', 'cloud_vault.py', 'compression_profile.py', 'context_modes.py', 'convert_worker.py', 'desktop_actions.py', 'discovery.py', 'engine_performance.py', 'engine_profiles.py', 'fal_video.py', 'file_convert.py', 'file_converter.py', 'github_access.py', 'goal_workspace.py', 'hf_access.py', 'history_lookup.py', 'human_queue.py', 'jarvis_support.py', 'managed_models.py', 'messenger_bridge.py', 'model_advisor.py', 'model_routes.py', 'music.py', 'music_setup.py', 'music_worker.py', 'narration.py', 'neuro_clone.py', 'neuro_development.py', 'neurosphere_index.py', 'neurosphere_sources.py', 'paid_responses.py', 'personal_enhance.py', 'personal_speech.py', 'personal_voice.py', 'phone_access.py', 'platform_support.py', 'preflight.py', 'preview_browser.py', 'private_port.py', 'progress_guard.py', 'project_memory_view.py', 'queue_order.py', 'remote_client.py', 'remote_protocol.py', 'reply_language.py', 'rewards.py', 'rewards_catalog.py', 'self_repair.py', 'speech_numbers.py', 'speech_worker.py', 'startup_support.py', 'system_check.py', 'team_agents.py', 'team_chats.py', 'ui_lifecycle.py', 'video.py', 'voice_clone.py', 'web_research.py', 'window_instance.py', 'workspace_features.py')

def tree(source,target):
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','runtime.json','node_modules','.git'))
def apply(bundle):
    bundle=pathlib.Path(bundle).resolve()
    if not bundle.is_relative_to((ROOT/'build').resolve()):raise ValueError('Feature staging must stay inside this project build folder')
    destination=bundle/'runtime/freedom';destination.mkdir(parents=True,exist_ok=True)
    tree(ROOT/'licenses',bundle/'licenses')
    for name in MODULES:shutil.copy2(APP/name,destination/name)
    for folder in ('agent_plugins','scripts'):tree(APP/folder,destination/folder)
    tree(APP/'builtin_skills/arshi',bundle/'stack/hermes-runtime/skills/arshi')
    tree(APP/'builtin_skills/arshi',destination/'builtin_skills/arshi')
    progress=bundle/'stack/hermes-runtime/plugins/freedom-progress'
    tree(APP/'agent_plugins/freedom-progress',progress)
    (progress/'runtime.json').write_text(json.dumps({'app_relative':'../../../..'}),encoding='utf8')
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
    from phone_dependency import apply as stage_phone_dependency
    stage_phone_dependency(bundle)
    return {'modules':len(MODULES),'native_overrides':len(manifest['files']),'personal_data_included':False}
