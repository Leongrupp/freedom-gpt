"""Measure the installed text model's actual rendered request, without inference.

Never sends prompts outside loopback. Failed/unsupported measurements preserve
the native pressure gate and its fail-closed provider-overflow handling.
"""
import hashlib
import json
import logging
import time
import urllib.request
from urllib.parse import urlsplit
from agent.freedom_local_runtime import managed_local_port

log = logging.getLogger(__name__)


def measure_local_request(agent, messages, tools):
    agent._freedom_local_request_fits = False
    try:
        url = urlsplit(str(getattr(agent, 'base_url', '') or ''))
        if url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.port != managed_local_port():
            return None
        if url.username or url.password or time.monotonic() < getattr(agent, '_freedom_token_retry_after', 0):
            return None
        # Images/audio need their encoder's accounting, not the text tokenizer.
        if any(not isinstance(m.get('content'), (str, type(None))) for m in messages):
            return None
        payload = {'messages': messages, 'tools': tools or [], 'add_generation_prompt': True}
        kwargs = getattr(agent, 'extra_body', None)
        if isinstance(kwargs, dict) and isinstance(kwargs.get('chat_template_kwargs'), dict):
            payload['chat_template_kwargs'] = kwargs['chat_template_kwargs']
        raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        signature = hashlib.sha256(raw).hexdigest()
        cache = getattr(agent, '_freedom_token_cache', {})
        count = cache.get(signature)
        origin = f'{url.scheme}://{url.netloc}'
        if count is None:
            # A system HTTP proxy must never receive a local chat transcript.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def post(path, body):
                request = urllib.request.Request(origin + path, data=body,
                    headers={'Content-Type': 'application/json'})
                with opener.open(request, timeout=4) as response:
                    return json.load(response)
            prompt = post('/apply-template', raw).get('prompt')
            if not isinstance(prompt, str):
                return None
            encoded = json.dumps({'content': prompt, 'add_special': True,
                                  'parse_special': True}).encode('utf-8')
            tokens = post('/tokenize', encoded).get('tokens')
            if not isinstance(tokens, list) or not all(isinstance(t, int) for t in tokens):
                return None
            count = len(tokens)
            if len(cache) >= 16:
                cache.pop(next(iter(cache)))
            cache[signature] = count
            agent._freedom_token_cache = cache
        # Leave template/transport margin and space for a useful reply. This is
        # stricter than checking prompt < context; no hard-window bypass.
        limit = int(agent.context_compressor.context_length)
        output = int(getattr(agent, 'max_tokens', None) or 4096)
        reserve = max(4096, min(output, 8192))
        pressure = count + 1024
        agent._freedom_local_request_fits = pressure + reserve <= limit
        agent._freedom_local_prompt_tokens = count
        return pressure
    except Exception as exc:
        agent._freedom_token_retry_after = time.monotonic() + 30
        log.debug('Local tokenizer unavailable (%s); keeping native pressure gate', type(exc).__name__)
        return None
