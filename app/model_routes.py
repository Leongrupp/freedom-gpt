"""Portable local-model route identities, independent of a private supervisor."""
import requests
from bootstrap import config

PREFIX = 'freedom-local-gguf-'


def alias(ident):
    return PREFIX + ident


def catalog_id(value):
    return value[len(PREFIX):] if isinstance(value, str) and value.startswith(PREFIX) else None


def route_ready(ident):
    origin = f"http://127.0.0.1:{config()['model_port']}"
    try:
        response = requests.get(origin + '/v1/models', timeout=2)
        return (response.status_code == 200
                and any(row.get('id') == alias(ident) for row in response.json().get('data', []))
                and requests.get(origin + '/health', timeout=2).json().get('status') == 'ok')
    except (requests.RequestException, ValueError):
        return False
