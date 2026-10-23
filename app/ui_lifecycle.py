"""Private UI process ownership, bounded crash recovery and exit diagnostics."""
import json
import os
import pathlib
import subprocess
import sys
import time
from contextlib import contextmanager

import psutil

SCRIPT = pathlib.Path(__file__).resolve()
ROOT = pathlib.Path(os.environ.get('FREEDOM_ROOT') or SCRIPT.parents[2])
RECORD = ROOT / '.tmp/ui-supervisor.json'
STOP = ROOT / '.tmp/ui-stop-request.json'


def detached_process(args, **kwargs):
    if os.name == 'nt':
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        try:
            return subprocess.Popen(args, creationflags=flags, **kwargs)
        except OSError as exc:
            if getattr(exc, 'winerror', None) != 5:
                raise
            return subprocess.Popen(args, creationflags=flags & ~subprocess.CREATE_BREAKAWAY_FROM_JOB,
                                    **kwargs)
    return subprocess.Popen(args, start_new_session=True, **kwargs)


def owned_process(record, filename):
    try:
        process = psutil.Process(record['pid'])
        if abs(process.create_time() - record['created']) >= 1:
            return None
        if not any(pathlib.Path(arg).resolve() == ROOT / filename
                   for arg in process.cmdline()[1:] if not arg.startswith('-')):
            return None
        return process
    except (KeyError, OSError, psutil.Error, ValueError):
        return None


def stop_requested(started):
    try:
        return float(json.loads(STOP.read_text())['requested_at']) >= started
    except (OSError, ValueError, KeyError, TypeError):
        return False


def request_stop():
    from bootstrap import write
    write(STOP, {'requested_at': time.time()})


@contextmanager
def startup_lock(name):
    from platform_support import file_lock
    deadline = time.monotonic() + 10
    while True:
        try:
            handle = file_lock(ROOT / '.tmp' / name)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Another UI startup is still running')
            time.sleep(.05)
    try:
        yield
    finally:
        handle.close()


def current_ui(port):
    """Recover stale metadata only from a listener belonging to this installation."""
    from bootstrap import read, write
    record = read(ROOT / '.tmp/server-process.json', {})
    if owned_process(record, 'server.py'):
        return record
    try:
        for connection in psutil.net_connections(kind='inet'):
            if (connection.status != psutil.CONN_LISTEN or not connection.pid
                    or not connection.laddr or connection.laddr.port != port
                    or connection.laddr.ip not in {'127.0.0.1', '::1'}):
                continue
            process = psutil.Process(connection.pid)
            candidate = {'pid': process.pid, 'created': process.create_time()}
            if owned_process(candidate, 'server.py'):
                write(ROOT / '.tmp/server-process.json', candidate)
                return candidate
    except (OSError, psutil.Error):
        pass
    return None


def spawn_ui():
    with startup_lock('ui-spawn.lock'):
        return _spawn_ui()


def _spawn_ui():
    from bootstrap import write, config
    record = current_ui(config()['ui_port'])
    if record:
        return record
    with (ROOT / 'logs/launcher.log').open('ab') as log:
        child = detached_process([sys.executable, '-B', '-s', str(ROOT / 'server.py')],
            cwd=ROOT, env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, close_fds=True)
    record = {'pid': child.pid, 'created': psutil.Process(child.pid).create_time()}
    write(ROOT / '.tmp/server-process.json', record)
    return record


def ensure_supervisor(server, port):
    with startup_lock('ui-watch-start.lock'):
        return _ensure_supervisor(server, port)


def _ensure_supervisor(server, port):
    from bootstrap import read, write
    prior = read(RECORD, {})
    process = owned_process(prior, SCRIPT)
    if process and STOP.exists():
        # An explicit Stop may still be finishing. It owns the old monitor only.
        try:
            process.wait(timeout=8)
        except psutil.TimeoutExpired:
            return
        process = None
    STOP.unlink(missing_ok=True)
    if process:
        return
    with (ROOT / 'logs/ui-supervisor-stdio.log').open('ab') as log:
        child = detached_process([sys.executable, '-B', '-s', str(SCRIPT),
            '--watch', str(server['pid']), str(server['created']), str(port)],
            cwd=ROOT, env={**os.environ, 'FREEDOM_ROOT': str(ROOT)}, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, close_fds=True)
    # Persist its identity before the child imports/bootstrap code. A second
    # launch can now wait for this monitor even while it is still starting.
    born = psutil.Process(child.pid).create_time()
    write(RECORD, {'pid': child.pid, 'created': born, 'started': born})


def watch(record, port):
    import bootstrap
    import hashlib
    import logging
    from logging.handlers import RotatingFileHandler
    import urllib.request
    from platform_support import file_lock

    try:
        lock = file_lock(ROOT / '.tmp/ui-supervisor.lock')
    except OSError:
        return
    logger = logging.getLogger('ui-lifecycle')
    logger.setLevel(logging.INFO)
    logger.addHandler(RotatingFileHandler(ROOT / 'logs/ui-lifecycle.jsonl',
                      maxBytes=1024*1024, backupCount=1, encoding='utf-8'))
    def event(kind, **data):
        logger.info(json.dumps({'at': time.time(), 'kind': kind, **data}))
    # Stop requested during Python startup must also retire this monitor.
    started = psutil.Process().create_time()
    bootstrap.write(RECORD, {'pid': os.getpid(), 'created': psutil.Process().create_time(),
                            'started': started})
    expected = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    attempts = []
    event('watching', ui_pid=record['pid'])
    try:
        while not stop_requested(started):
            process = owned_process(record, 'server.py')
            if process:
                try:
                    code = process.wait(timeout=1)
                except psutil.TimeoutExpired:
                    continue
                except psutil.NoSuchProcess:
                    code = None
            else:
                code = None
            if stop_requested(started):
                break
            memory = psutil.virtual_memory()
            event('ui_exited', ui_pid=record['pid'], exit_code=code,
                  available_memory=memory.available)
            if code == 0:
                event('clean_exit')
                return
            now = time.monotonic()
            attempts = [value for value in attempts if now-value < 600]
            if len(attempts) >= 4:
                event('restart_limit_reached')
                return
            delay = (1, 3, 10, 30)[len(attempts)]
            for _ in range(delay * 4):
                if stop_requested(started):
                    return
                time.sleep(.25)
            attempts.append(time.monotonic())
            try:
                # Never start a duplicate or replace somebody else's listener.
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
                    health = json.load(response)
                if health.get('installation') != expected:
                    event('foreign_listener')
                    return
                record = bootstrap.read(ROOT / '.tmp/server-process.json', {})
                if not owned_process(record, 'server.py'):
                    event('unowned_listener')
                    return
                continue
            except (OSError, ValueError):
                pass
            record = spawn_ui()
            event('ui_restarted', ui_pid=record['pid'], attempt=len(attempts))
    finally:
        event('watcher_stopped', requested=stop_requested(started))
        lock.close()


if __name__ == '__main__':
    import bootstrap
    if len(sys.argv) == 5 and sys.argv[1] == '--watch':
        watch({'pid': int(sys.argv[2]), 'created': float(sys.argv[3])}, int(sys.argv[4]))
