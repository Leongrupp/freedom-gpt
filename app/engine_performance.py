"""Measured, reversible local inference profiles. Never interrupt an agent turn."""
import asyncio
import contextlib
import hashlib
import json
import os
import pathlib
import statistics
import subprocess
import sys
import threading
import time

import psutil
import requests
from aiohttp import web

import bootstrap
from bootstrap import ROOT, STACK, config, read, write
from platform_support import PROCESS_FLAGS, file_lock, native_binary

PROFILE = ROOT / 'data/performance-profiles.json'
RECOVERY = ROOT / 'data/performance-recovery.json'
FIELDS = ('threads', 'threads_batch', 'batch_size', 'ubatch_size', 'priority', 'cpu_poll', 'draft_tokens')
PROMPTS = [
    'Write a Python function that merges overlapping intervals. Include type hints, a clear docstring, and explain the algorithm.',
    'Объясни подробно, как устроены кэширование, индексы базы данных и очередь фоновых заданий в интернет-магазине.',
    ('Project requirements: preserve data, validate input, keep an audit log, use a queue, handle retries safely.\n' * 90)
    + 'Write a detailed implementation plan with Python code for this project.',
]


class Cancelled(Exception):
    pass


class Performance:
    def __init__(self, library, bridge, videos, image_status):
        self.library, self.bridge = library, bridge
        self.videos, self.image_status = videos, image_status
        self.phase, self.message, self.progress = 'ready', '', 0
        self.pending = None
        self.cancel = threading.Event()
        self.task = None
        self.app = None

    def engine(self):
        if bootstrap.PRIVATE:
            import managed_models
            owner = managed_models.owned_supervisor()
            if not owner:
                raise ValueError('Не найден управляемый сервер модели.')
            children = [p for p in owner.children() if p.name().lower() in {'llama-server.exe', 'llama-server'}]
            if not children:
                raise ValueError('Дождитесь загрузки локальной модели.')
            return pathlib.Path(children[0].exe())
        return native_binary(ROOT, 'llama', read(STACK / 'server-settings.json', {}).get('backend'))

    def identity(self, cfg):
        path = pathlib.Path(cfg['model'])
        engine = self.engine()
        device = read(ROOT / 'data/hardware.json', {})
        data = {k: cfg.get(k) for k in ('model', 'context', 'ngl', 'backend', 'kv_cache', 'mtp', 'mmproj', 'catalog_id')}
        data.update(model_stat=[path.stat().st_size, path.stat().st_mtime_ns],
                    engine=[str(engine), engine.stat().st_size, engine.stat().st_mtime_ns],
                    device=[device.get('cpu'), device.get('ram_gb'), [(g.get('name'), g.get('driver')) for g in device.get('gpus', [])]])
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:24]

    def status(self):
        cfg = read(STACK / 'server-settings.json', {})
        available = bool(cfg.get('model') and not config().get('external_url'))
        key = cfg.get('performance_key')
        saved = read(PROFILE, {}).get(key, {}) if key else {}
        active = cfg.get('performance_mode') == 'turbo'
        return dict(available=available, active=active, mode='turbo' if active else 'balanced',
                    operation='context' if isinstance(self.pending,dict) else 'performance',
                    phase=self.phase, pending=self.pending, message=self.message, progress=self.progress,
                    measured=saved.get('measurement'), context=cfg.get('context'),
                    settings={k: cfg[k] for k in FIELDS if k in cfg},
                    recovery=bool(read(RECOVERY, {})))

    def request(self, enabled):
        if not self.status()['available']:
            raise ValueError('Турбо доступен для локальной модели под управлением Freedom GPT.')
        if self.phase == 'waiting' and not enabled:
            self.pending, self.phase, self.message = None, 'ready', ''
            return self.status()
        if self.phase in {'calibrating', 'applying', 'restoring'}:
            if enabled:
                return self.status()
            self.cancel.set()
            self.message = 'Останавливаем замер и возвращаем прежние настройки.'
            return self.status()
        self.pending = 'turbo' if enabled else 'balanced'
        self.phase, self.progress, self.message = 'waiting', 0, ''
        self.cancel.clear()
        return self.status()

    async def idle(self):
        if self.app.get('prompt_admissions') or self.app.get('update_applying') or self.videos.busy():
            return False
        if (self.library.activation or {}).get('state') == 'loading':
            return False
        if any(v.get('active') for v in self.bridge.live.values()):
            return False
        if any(v.get('running') or v.get('pending') for v in self.bridge.snapshots.values()):
            return False
        image = self.image_status()
        if image.get('generating') or image.get('busy'):
            return False
        try:
            import library
            if library.image_job_active():
                return False
            listed = await self.bridge.rpc('session.list', scope='live', limit=200)
            if any(s.get('running') or s.get('pending') for s in listed.get('sessions', [])):
                return False
            slots = await asyncio.to_thread(self.slots)
            return bool(slots) and all(not s.get('is_processing', True) for s in slots)
        except Exception:
            # Restore an interrupted calibration even if its failed candidate
            # never reached /health. Ownership is checked again by restart().
            return bool(read(RECOVERY, {}))

    def slots(self):
        response = requests.get(f"http://127.0.0.1:{config()['model_port']}/slots", timeout=3)
        response.raise_for_status()
        slots = response.json()
        if not isinstance(slots, list):
            raise ValueError('Не удалось проверить занятость модели.')
        return slots

    def restart(self, cfg):
        """Keep the same model, aliases, context and agent configuration."""
        marker = STACK / '.tmp/current-server-log.txt'
        prior_log = marker.read_text(encoding='utf-8-sig').strip() if marker.is_file() else ''
        try:
            slots = self.slots()
        except requests.RequestException:
            slots = []  # A failed candidate must still be stoppable for rollback.
        if any(s.get('is_processing') for s in slots):
            raise ValueError('Модель занята другим клиентом. Переключение отложено.')
        if bootstrap.PRIVATE:
            import managed_models
            owner = managed_models.owned_supervisor()
            python = owner.exe() if owner else None
            managed_models.stop()
            write(STACK / 'server-settings.json', cfg)
            process = managed_models.start(python)
            self.wait_ready(process, cfg, prior_log)
        else:
            self.library.stop_model()
            write(STACK / 'server-settings.json', cfg)
            (STACK / '.tmp/stop-server').unlink(missing_ok=True)
            with (ROOT / 'logs/model-supervisor.log').open('ab') as log:
                process = subprocess.Popen([sys.executable, '-B', '-s', str(ROOT / 'engine_supervisor.py')],
                    cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=log, creationflags=PROCESS_FLAGS)
            write(STACK / '.tmp/supervisor-process.json', {'pid': process.pid, 'created': psutil.Process(process.pid).create_time()})
            self.wait_ready(process, cfg, prior_log)
        if any(s.get('n_ctx') != cfg['context'] for s in self.slots()):
            raise ValueError('Движок изменил окно контекста. Возвращаем прежние настройки.')

    def wait_ready(self, process, cfg, prior_log):
        expected = cfg.get('api_alias') or cfg['alias'].split(',')[0]
        deadline = time.monotonic() + 90
        origin = f"http://127.0.0.1:{cfg['port']}"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError('Сервер модели завершился. Возвращаем прежние настройки.')
            try:
                response = requests.get(origin + '/v1/models', timeout=2)
                if response.status_code == 200 and any(row.get('id') == expected for row in response.json().get('data', [])):
                    if requests.get(origin + '/health', timeout=2).json().get('status') == 'ok':
                        return
            except (requests.RequestException, ValueError):
                pass
            try:
                path = pathlib.Path((STACK / '.tmp/current-server-log.txt').read_text(encoding='utf-8-sig').strip()).resolve()
                if str(path) != prior_log and path.is_relative_to((STACK / 'logs').resolve()):
                    with path.open('rb') as stream:
                        stream.seek(0, 2); stream.seek(max(0, stream.tell() - 6000))
                        tail = stream.read().decode('utf8', 'replace').lower()
                    if 'cuda error: out of memory' in tail or 'failed to load model' in tail:
                        raise ValueError('Профилю не хватило памяти. Возвращаем прежние настройки.')
            except OSError:
                pass
            time.sleep(.5)
        raise ValueError('Двигатель не запустился за время ожидания. Возвращаем прежние настройки.')

    def check_cancel(self):
        if self.cancel.is_set():
            raise Cancelled()

    def measure(self, label):
        rows = []
        for i, prompt in enumerate(PROMPTS):
            self.check_cancel()
            if any(s.get('is_processing') for s in self.slots()):
                raise ValueError('Модель занята другим клиентом. Замер отменён.')
            self.message = f'{label} · {i + 1}/{len(PROMPTS)}'
            # Fixed seed and deterministic sampling make the comparison reproducible.
            # This endpoint runs no tools and never enters the user's chat history.
            response = requests.post(f"http://127.0.0.1:{config()['model_port']}/v1/chat/completions", json={
                'model': read(STACK / 'server-settings.json', {})['alias'],
                'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 160,
                'temperature': 0, 'seed': 8241, 'stream': False, 'cache_prompt': False,
                'chat_template_kwargs': {'enable_thinking': False},
            }, timeout=(5, 120))
            response.raise_for_status()
            result = response.json()
            timings = result.get('timings') or {}
            speed = timings.get('predicted_per_second')
            if not speed or (result.get('usage') or {}).get('completion_tokens', 0) < 120:
                raise ValueError('Недостаточно данных для достоверного замера скорости.')
            rows.append({'case': i, 'tok_s': speed, 'timings': timings,
                         'output_sha256': hashlib.sha256(json.dumps(result.get('choices'), sort_keys=True).encode()).hexdigest()})
        return {'tok_s': statistics.median(r['tok_s'] for r in rows), 'cases': rows}

    def candidates(self, baseline):
        device = read(ROOT / 'data/hardware.json', {})
        cores = max(1, min(16, int(device.get('physical_cores') or psutil.cpu_count(logical=False) or 4)))
        full_gpu = baseline.get('ngl') == 'all' and baseline.get('backend') == 'cuda'
        first = dict(baseline, threads=min(2, cores) if full_gpu else cores, threads_batch=cores,
                     batch_size=512, ubatch_size=256, priority=1, cpu_poll=0)
        second = dict(first, threads=min(4, cores) if full_gpu else cores, batch_size=1024, ubatch_size=512)
        if baseline.get('mtp'):
            first['draft_tokens'], second['draft_tokens'] = 3, 2
        return [first, second]

    def work(self, target):
        current = read(STACK / 'server-settings.json', {})
        recovery = read(RECOVERY, {})
        key = recovery.get('key') or self.identity(current)
        profiles = read(PROFILE, {})
        profile = profiles.get(key, {})
        if not profile and target == 'balanced' and current.get('performance_mode') == 'turbo':
            previous = profiles.get(current.get('performance_key'), {})
            if all((previous.get('balanced') or {}).get(k) == current.get(k) for k in ('model','context','ngl','kv_cache','mtp')):
                profile = previous
        balanced = profile.get('balanced') or current
        previous_activation = self.library.activation
        with self.library.transition, file_lock(STACK / '.tmp/private-model-switch.lock'):
            self.library.activation = {'id': self.library.active_id(), 'state': 'loading'}
            try:
                if recovery:
                    # A presentation-server crash during calibration must not make
                    # an unmeasured candidate a permanent default.
                    old = recovery['engine']
                    if old.get('model') == current.get('model'):
                        self.phase = 'restoring'
                        self.restart(old)
                        if recovery.get('application'):write(ROOT/'data/settings.json',recovery['application'])
                        if 'context_preferences' in recovery:write(ROOT/'data/context-preferences.json',recovery['context_preferences'])
                        item=self.library.model(old.get('catalog_id'))
                        if item:self.library.record_context(item,old)
                    write(RECOVERY, {})
                    return
                write(RECOVERY, {'engine': current, 'key': key, 'created': time.time()})
                if target == 'balanced':
                    self.phase = 'applying'
                    if current.get('performance_mode') != 'turbo':
                        write(RECOVERY, {})
                        return
                    self.restart(dict(balanced, performance_key=key, performance_mode='balanced'))
                elif profile.get('turbo'):
                    self.phase = 'applying'
                    self.restart(dict(profile['turbo'], performance_key=key, performance_mode='turbo'))
                else:
                    self.phase = 'calibrating'
                    self.progress = 5
                    initial_baseline = self.measure('Обычный режим')
                    results = []
                    for i, candidate in enumerate(self.candidates(balanced)):
                        self.check_cancel()
                        self.progress = 20 + i * 25
                        try:
                            self.restart(dict(candidate, performance_key=key, performance_mode='calibrating'))
                            result = self.measure(f'Профиль {i + 1}')
                            results.append({'engine': candidate, 'measurement': result})
                        except Cancelled:
                            raise
                        except Exception as exc:
                            results.append({'engine': candidate, 'error': str(exc)[:300]})
                            self.restart(balanced)
                    self.check_cancel()
                    best = max((r for r in results if r.get('measurement')), key=lambda r: r['measurement']['tok_s'], default=None)
                    self.progress = 75
                    # Repeat the baseline after tuning to account for warm GPU clocks.
                    self.restart(balanced)
                    repeated_baseline = self.measure('Повторный замер обычного режима')
                    # Use the faster control run, so clock/temperature drift never
                    # inflates the gain by comparing against a slower baseline.
                    baseline = max([initial_baseline, repeated_baseline], key=lambda row: row['tok_s'])
                    measurement = {'baseline_tok_s': baseline['tok_s'], 'turbo_tok_s': None,
                                   'gain_percent': 0, 'created': time.time(), 'cases': 3, 'context': balanced['context']}
                    turbo, confirmed = None, None
                    if best and best['measurement']['tok_s'] >= baseline['tok_s'] * 1.05:
                        self.check_cancel()
                        self.restart(best['engine'])
                        confirmed = self.measure('Подтверждаем ускорение')
                        if confirmed['tok_s'] >= baseline['tok_s'] * 1.05:
                            turbo = best['engine']
                            measurement.update(turbo_tok_s=confirmed['tok_s'],
                                               gain_percent=round((confirmed['tok_s'] / baseline['tok_s'] - 1) * 100, 1))
                    self.check_cancel()
                    final = dict(turbo or balanced, performance_key=key, performance_mode='turbo' if turbo else 'balanced')
                    self.restart(final)
                    profiles[key] = {'balanced': balanced, 'turbo': turbo, 'measurement': measurement}
                    write(PROFILE, profiles)
                    out = ROOT / 'output/performance'; out.mkdir(parents=True, exist_ok=True)
                    write(out / (key + '.json'), {'measurement': measurement, 'baseline': baseline,
                          'initial_baseline': initial_baseline, 'repeated_baseline': repeated_baseline,
                          'confirmation': confirmed, 'candidates': results})
                    self.message = '' if turbo else 'Текущие настройки уже быстрые: подтверждённого ускорения нет.'
                self.check_cancel()
                write(RECOVERY, {})
                self.progress = 100
            except Exception:
                self.phase = 'restoring'
                self.restart(recovery.get('engine') or current)
                write(RECOVERY, {})
                raise
            finally:
                self.library.activation = previous_activation

    async def loop(self):
        while True:
            if self.pending is not None or read(RECOVERY, {}):
                self.app['performance_busy'] = True
                self.bridge.performance_hold = True
                try:
                    if await self.idle():
                        target = self.pending or 'balanced'
                        if isinstance(target,dict):
                            await asyncio.to_thread(self.context_modes.apply,target)
                            await self.context_modes.after_apply(target)
                        else:await asyncio.to_thread(self.work, target)
                        self.phase, self.pending = 'ready', None
                    else:
                        self.phase = 'waiting'
                except Cancelled:
                    self.phase, self.pending, self.message = 'ready', None, ''
                except Exception as exc:
                    self.phase, self.pending, self.message = 'error', None, str(exc)[:400]
                finally:
                    self.app['performance_busy'] = False
                    self.bridge.performance_hold = False
            await asyncio.sleep(2)

    def start(self, app):
        self.app = app
        self.task = asyncio.create_task(self.loop())

    async def close(self):
        self.cancel.set()
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    def register(self, app):
        async def get(request):
            return web.json_response(self.status())
        async def set_mode(request):
            data = await request.json()
            if not isinstance(data.get('enabled'), bool):
                raise ValueError('Укажите enabled: true или false.')
            return web.json_response(self.request(data['enabled']))
        app.router.add_get('/api/performance', get)
        app.router.add_post('/api/performance', set_mode)
