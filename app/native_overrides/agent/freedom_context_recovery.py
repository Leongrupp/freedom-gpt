"""Bounded recovery for the installed local model's confirmed context pressure.

The normal compressor still owns checkpoints, leases, transcript publication and
tool-call alignment. This policy only reduces its protected window and permits
one probe after the ineffective-compaction breaker, for a distinct transcript.
"""
from contextlib import contextmanager
import hashlib
import logging
from urllib.parse import urlsplit
from agent.freedom_local_runtime import managed_local_port

log = logging.getLogger(__name__)


def automatic_timeout_recovery(agent):
    """The private local route opts into same-turn fallback on its FIRST stall.

    The native owner still controls checkpoints, cancellation and commit fences;
    this selects its existing recovery ladder, never replays a user task.
    """
    from agent.auxiliary_task_config import _get_auxiliary_task_config
    url = urlsplit(str(getattr(agent, 'base_url', '') or ''))
    if url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.port != managed_local_port():
        return False
    return _get_auxiliary_task_config('compression').get('automatic_recovery') is True


def allow_deterministic_fallback(compressor, telemetry):
    """Opt-in recovery overrides abort only for the owner's pinned stall fallback.

    Auth, truncated output and other terminal failures are rejected by the caller
    first. A normal failed summary still honors abort_on_summary_failure.
    """
    return not compressor.abort_on_summary_failure or (
        telemetry.get('failure_class') == 'stall_deterministic_fallback'
        and automatic_timeout_recovery(compressor)
    )


def local_context_pressure(agent, tokens, *, trigger=None, overflow_reason=None):
    try:
        url = urlsplit(str(getattr(agent, 'base_url', '') or ''))
        if url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.port != managed_local_port():
            return False
        limit = int(agent.context_compressor.context_length)
        return limit > 0 and (overflow_reason == 'context_overflow' or (
            trigger in {'gateway_hygiene', 'turn_start_threshold', 'pre_api', 'post_tool'}
            and int(tokens or 0) >= int(limit * .85)))
    except (AttributeError, TypeError, ValueError):
        return False


@contextmanager
def recovery_policy(agent, messages, *, force=False, tokens=None, trigger=None, overflow_reason=None):
    compressor = getattr(agent, 'context_compressor', None)
    required = ('_compression_block_reason', 'protect_first_n', 'protect_last_n',
                'min_tail_user_messages', '_tail_token_budget', 'tail_token_budget')
    if compressor is None or not all(hasattr(compressor, key) for key in required) or not local_context_pressure(agent, tokens, trigger=trigger, overflow_reason=overflow_reason):
        yield force
        return
    reason = compressor._compression_block_reason() or ''
    # A failed summary/provider cooldown is a real failure; do not clear it on
    # every user message. Locks and checkpoint guards remain inside the owner.
    if not force and reason.startswith('cooldown:'):
        yield force
        return
    tail = messages[-1] if messages else {}
    identity = repr((len(messages), tail.get('message_uid'), tail.get('_row_id'),
                     tail.get('content'), tail.get('tool_call_id')))
    signature = hashlib.sha256(identity.encode('utf-8', errors='replace')).hexdigest()
    if not force and getattr(compressor, '_freedom_recovery_signature', None) == signature:
        yield False
        return
    compressor._freedom_recovery_signature = signature
    saved = {key: getattr(compressor, key) for key in
             ('protect_first_n', 'protect_last_n', 'min_tail_user_messages', '_tail_token_budget')}
    try:
        compressor.protect_first_n = 0
        over_window=int(tokens or 0)>int(compressor.context_length)
        compressor.protect_last_n = min(3 if over_window else 4, compressor.protect_last_n)
        compressor.min_tail_user_messages = 1
        compressor.tail_token_budget = min(1024 if over_window else 2048, compressor.tail_token_budget)
        probe = force or reason == 'ineffective' or reason.startswith('structural_backoff:')
        log.info('Local context recovery: bounded compaction probe (session=%s pressure=%s reason=%s)',
                 getattr(agent, 'session_id', ''), tokens, reason or 'high_watermark')
        yield probe
    finally:
        for key, value in saved.items():
            setattr(compressor, key, value)
