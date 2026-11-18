"""Keep local summarization independent from the main turn's thinking effort."""
from __future__ import annotations

from urllib.parse import urlsplit

from bootstrap import HOME,PRIVATE


def local_compression_settings(engine, previous):
    origin=f"http://127.0.0.1:{int(engine['port'])}/v1"
    if previous:
        endpoint=urlsplit(str(previous.get('base_url') or ''))
        if (previous.get('provider') not in {'direct-local','custom'}
                or endpoint.hostname not in {'127.0.0.1','localhost','::1'}
                or endpoint.port!=int(engine['port'])):
            return None
    updated=dict(previous)
    body=dict(updated.get('extra_body') or {})
    body['chat_template_kwargs']={**(body.get('chat_template_kwargs') or {}),'enable_thinking':False}
    body['reasoning']={'enabled':False,'effort':'none'}
    updated.update(provider='direct-local',model=engine.get('api_alias') or engine['alias'].split(',')[0],
                   base_url=origin,context_length=int(engine['context']),reasoning_effort='none',
                   max_concurrency=1,summary_target_tokens=2000,summary_style='compact',
                   automatic_recovery=True,extra_body=body)
    return updated


def sync_local_compression(engine):
    if not PRIVATE:
        return False
    from hermes_cli.config import read_user_config_raw
    from utils import atomic_roundtrip_yaml_update
    path=HOME/'config.yaml'
    config=read_user_config_raw(path)
    previous=(config.get('auxiliary') or {}).get('compression') or {}
    updated=local_compression_settings(engine,previous)
    if updated is None or updated==previous:
        return False
    atomic_roundtrip_yaml_update(path,'auxiliary.compression',updated)
    return True
