"""Optional unlimited-goal recovery; finite goals retain their gate retry limit."""


def continued_gate_repair(state):
    if state.max_turns != 0:
        return False
    from hermes_cli.config import load_config
    return (load_config().get('goals') or {}).get('continue_failed_gates') is True


def gate_retry_exhausted(state, gate):
    return gate.attempts > gate.max_retries and not continued_gate_repair(state)


def gate_retry_limit(state, gate):
    return 'unlimited' if continued_gate_repair(state) else gate.max_retries


def gate_repair_prompt(state, gate, prompt):
    if gate.attempts <= gate.max_retries or not continued_gate_repair(state):
        return prompt
    return prompt + ('\n\nThe same quality gate is still red. The unlimited goal remains active. '
                     'Identify the underlying cause and use a different repair hypothesis or tool; '
                     'do not just repeat the failed approach. Save the verified state and next step '
                     'in project memory. Preserve the verification requirement: never delete, weaken '
                     'or fake the gate to declare success. Continue until the requested result is verified '
                     'or a concrete owner-only dependency is established.')


def transport_reason(exc):
    """Only typed transient failures qualify; never classify from untrusted error prose."""
    name=type(exc).__name__
    status=getattr(exc,'status_code',None)
    transient=name in {'TimeoutError','APITimeoutError','ReadTimeout','ConnectTimeout',
                       'ConnectionError','APIConnectionError','ConnectError','ReadError',
                       'RemoteProtocolError','MemoryError'} or status in {408,425,429,500,502,503,504}
    if name in {'AuthenticationError','PermissionDeniedError','AuxiliaryClientUnavailable'} or status in {400,401,403,404,422}:
        transient=False
    return ('temporary judge error: ' if transient else 'judge error: ')+name


def transport_backoff(state,reason):
    if not reason.startswith('temporary judge error: ') or not continued_gate_repair(state):
        return 0
    # The native goal scheduler owns this persisted wait; no second retry loop.
    return min(900,30*(2**min(5,max(0,state.consecutive_transport_failures-1))))


def recoverable_context_failure(state,failure):
    # Owner-produced typed execution result, never a judge's interpretation of
    # website/tool text. A failed inference is not evidence the goal is impossible.
    return (continued_gate_repair(state) and isinstance(failure,dict)
            and failure.get('failed') is True and failure.get('interrupted') is not True
            and failure.get('failure_reason')=='context_overflow'
            and failure.get('compression_exhausted') is True)
