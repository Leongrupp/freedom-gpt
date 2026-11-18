"""Resolve the port of this installation's owned inference engine."""
import json
import os
from pathlib import Path


def managed_local_port():
    stack = os.environ.get('FREEDOM_STACK')
    if not stack:
        return None
    try:
        cfg = json.loads((Path(stack)/'server-settings.json').read_text(encoding='utf-8-sig'))
        port = int(cfg['port'])
        return port if 0 < port < 65536 else None
    except (OSError, ValueError, TypeError, KeyError):
        return None
