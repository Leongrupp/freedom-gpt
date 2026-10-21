"""Personal workspace goal controls. The native owner judges and schedules every continuation.

Never use session.automation here: that RPC transfers continuation ownership to its viewer.
Drafts are local UI data; running goals remain canonical native session state.
"""
import asyncio
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time
import uuid

from aiohttp import web
import psutil
from workspace_features import EXECUTION_NOTE, LEARNING_NOTE


class GoalWorkspace:
    def __init__(self, db, bridge, workspace, video_busy):
        self.db, self.bridge, self.workspace, self.video_busy = db, bridge, workspace, video_busy
        self.locks = {}
        with db() as conn:
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS workspace_goal_drafts(
              session_id TEXT PRIMARY KEY,fields TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated REAL);
            CREATE TABLE IF NOT EXISTS workspace_goal_starts(
              input_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,message TEXT NOT NULL,
              display TEXT NOT NULL,receipt TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS workspace_goal_history(
              id TEXT PRIMARY KEY,session_id TEXT NOT NULL,goal_created REAL NOT NULL,
              title TEXT NOT NULL,fields TEXT NOT NULL,snapshot TEXT NOT NULL,completed REAL NOT NULL,
              reopen_count INTEGER NOT NULL DEFAULT 0,last_reopened REAL);
            CREATE INDEX IF NOT EXISTS goal_history_session ON workspace_goal_history(session_id,completed);
            ''')

    def draft(self, sid):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM workspace_goal_drafts WHERE session_id=?', (sid,)).fetchone()
        return {'fields': json.loads(row['fields']), 'revision': row['revision'], 'updated': row['updated']} if row else None

    @staticmethod
    def goal_fields(goal):
        contract = goal.get('contract') or {}
        return {'objective': re.sub(r'^Задание владельца (?:--|—|-)\s*', '', goal.get('title') or ''),
                'verification': contract.get('verification') or '',
                'constraints': contract.get('constraints') or ''}

    def archive_goal(self, sid, goal):
        """Archive each completed attempt once; never clear a different/new user draft."""
        if not goal or goal.get('status') != 'done' or not goal.get('created_at'):
            return
        identifier = hashlib.sha256((sid+':'+str(goal['created_at'])).encode()).hexdigest()[:32]
        fields = self.goal_fields(goal)
        with self.db() as conn:
            inserted = conn.execute('''INSERT OR IGNORE INTO workspace_goal_history
                (id,session_id,goal_created,title,fields,snapshot,completed) VALUES(?,?,?,?,?,?,?)''',
                (identifier, sid, goal['created_at'], fields['objective'], json.dumps(fields, ensure_ascii=False),
                 json.dumps(goal, ensure_ascii=False), time.time())).rowcount
            if inserted:
                draft = conn.execute('SELECT fields,revision FROM workspace_goal_drafts WHERE session_id=?', (sid,)).fetchone()
                normalize = lambda data: {key: ' '.join(str(data.get(key) or '').split()) for key in fields}
                if draft and normalize(json.loads(draft['fields'])) == normalize(fields):
                    conn.execute('UPDATE workspace_goal_drafts SET fields=?,revision=revision+1,updated=? WHERE session_id=? AND revision=?',
                                 (json.dumps({'objective':'','verification':'','constraints':''}), time.time(), sid, draft['revision']))

    def history(self, sid):
        with self.db() as conn:
            rows = conn.execute('SELECT * FROM workspace_goal_history WHERE session_id=? ORDER BY completed DESC,id', (sid,)).fetchall()
        return [{'id': row['id'], 'title': row['title'], 'fields': json.loads(row['fields']),
                 'goal': json.loads(row['snapshot']), 'completed': row['completed'],
                 'reopen_count': row['reopen_count'], 'last_reopened': row['last_reopened']} for row in rows]

    @staticmethod
    def command(fields):
        line = lambda value: ' '.join(value.splitlines())
        command = '/goal -- Задание владельца — '+line(fields['objective'])
        for key in ('verification', 'constraints'):
            if fields[key]:
                command += '\n'+key+': '+line(fields[key])
        return command+('\nboundaries: Сохраняй прогресс и оставшиеся шаги в памяти проекта. '
                        'При внешнем препятствии или необходимости решения владельца остановись и объясни причину. '
                        'Готовность подтверждай фактическим результатом; не повторяй одинаковые неудачные действия.')

    def engine_status(self):
        root = pathlib.Path(self.workspace.root)
        home = pathlib.Path(self.workspace.portable.HOME)
        try:
            record = json.loads((home/'gateway.pid').read_text(encoding='utf-8-sig'))
            process = psutil.Process(record['pid'])
            modified = max((root/name).stat().st_mtime for name in
                           ('runtime/hermes/hermes_cli/goals.py', 'runtime/hermes/gateway/run_goals.py',
                            'runtime/hermes/hermes_cli/goal_command.py'))
            with sqlite3.connect('file:'+(home/'state.db').as_posix()+'?mode=ro', uri=True) as conn:
                pending = conn.execute("SELECT COUNT(*) FROM session_admissions WHERE status IN ('queued','started','unknown')").fetchone()[0]
            return {'ready': process.create_time() >= modified, 'pending': pending}
        except (OSError, ValueError, KeyError, sqlite3.Error, psutil.Error):
            return {'ready': False, 'pending': None}

    async def apply_engine(self, request):
        status = await asyncio.to_thread(self.engine_status)
        if status['ready']:
            return
        if status['pending'] != 0:
            raise web.HTTPConflict(text='Агент занят. Применить обновление можно после завершения всех текущих заданий и очередей.')
        root = pathlib.Path(self.workspace.root)
        home = pathlib.Path(self.workspace.portable.HOME)
        env = os.environ.copy()
        env.update(HERMES_HOME=str(home), PYTHONPATH=os.pathsep.join([
            str(root/'runtime/hermes'), str(root/'runtime/python/Lib/site-packages'), str(root/'runtime/freedom'), str(root)]),
            TEMP=str(root/'.tmp'), TMP=str(root/'.tmp'), TMPDIR=str(root/'.tmp'), PYTHONDONTWRITEBYTECODE='1',
            PYTHONNOUSERSITE='1', PYTHONIOENCODING='utf-8', TERMINAL_MAX_FOREGROUND_TIMEOUT='60',
            UV_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        # Official graceful restart only, never --force or a PID kill. Refuse if work is present.
        request.app['update_applying'] = True
        try:
            with (root/'logs/goal-engine-activation.log').open('ab') as log:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, '-s', '-m', 'hermes_cli.main', 'gateway', 'restart',
                    cwd=root/'runtime/hermes', env=env, stdout=log, stderr=log,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    await asyncio.wait_for(proc.wait(), 35)
                except asyncio.TimeoutError:
                    raise web.HTTPConflict(text='Применение ещё продолжается. Обновите состояние через несколько секунд.')
            if proc.returncode != 0:
                raise web.HTTPConflict(text='Обновление движка не применено. Подробности в локальном журнале.')
            for _ in range(50):
                if self.bridge.ready.is_set() and (await asyncio.to_thread(self.engine_status))['ready']:
                    return
                await asyncio.sleep(.1)
            raise web.HTTPConflict(text='Движок переподключается. Обновите состояние цели.')
        finally:
            request.app['update_applying'] = False

    async def snapshot(self, sid):
        result = await self.bridge.rpc('session.control.read', session_id=sid)
        control = result.get('control') or {}
        self.archive_goal(sid, control.get('goal'))
        with self.db() as conn:
            unresolved = conn.execute('SELECT input_id FROM workspace_goal_starts WHERE session_id=? AND receipt IS NULL', (sid,)).fetchone()
        return {'goal': control.get('goal'), 'revision': control.get('revision', ''),
                'draft': self.draft(sid), 'start_uncertain': bool(unresolved),
                'history': self.history(sid),
                'engine': await asyncio.to_thread(self.engine_status)}

    async def read(self, request):
        sid = request.match_info['sid']
        await self.bridge.resume(sid)
        return web.json_response(await self.snapshot(sid))

    @staticmethod
    def fields(data):
        fields = data.get('fields')
        if not isinstance(fields, dict):
            raise web.HTTPBadRequest(text='Некорректное описание цели.')
        result = {key: str(fields.get(key) or '').strip() for key in ('objective', 'verification', 'constraints')}
        if not result['objective'] or sum(map(len, result.values())) > 1900:
            raise web.HTTPBadRequest(text='Опишите цель: не более 1900 символов вместе с критериями и ограничениями.')
        return result

    async def enqueue(self, sid, dispatch, snapshot):
        if dispatch.get('type') != 'send' or not dispatch.get('message'):
            raise web.HTTPConflict(text='Движок не подтвердил запуск цели. Обновите её состояние.')
        input_id = 'goal_' + uuid.uuid4().hex
        message = dispatch['message']
        display = '[Цель] ' + ((snapshot.get('goal') or {}).get('title') or 'Продолжить')
        notes = EXECUTION_NOTE
        if self.workspace.preferences(sid).get('learning', True):
            notes += '\n' + LEARNING_NOTE
        notes += ('\nРаботай по сохранённой цели и критериям готовности. После значимого шага сохраняй '
                  'в памяти проекта факты, принятые решения, изменённые файлы и оставшиеся шаги. '
                  'В итогах шага приводи проверенные результаты и препятствия. Не объявляй цель выполненной без доказательств.')
        api_text = message+'\n\n[Выполнение и память]\n'+notes
        # Store the exact wire payload. An explicit recovery reuses this input id;
        # the owner returns its original receipt instead of admitting a second task.
        with self.db() as conn:
            conn.execute('INSERT INTO workspace_goal_starts VALUES(?,?,?,?,NULL,?)',
                         (input_id, sid, api_text, display, time.time()))
        receipt = await self.bridge.rpc('prompt.submit', session_id=sid, input_id=input_id, text=display,
                                       api_text=api_text, queued=True)
        if not receipt.get('admission_id'):
            raise web.HTTPConflict(text='Запуск не подтверждён. Обновите состояние цели перед продолжением.')
        with self.db() as conn:
            conn.execute('UPDATE workspace_goal_starts SET receipt=? WHERE input_id=?',
                         (json.dumps(receipt), input_id))
            conn.execute('INSERT OR IGNORE INTO chats(id,updated) VALUES(?,?)', (sid, time.time()))
            conn.execute('UPDATE chats SET updated=? WHERE id=?', (time.time(), sid))
        self.workspace.admitted(sid, input_id, receipt, self.workspace.selected_model(sid))

    async def change(self, request):
        try:
            return await self._change(request)
        except web.HTTPException as exc:
            return web.json_response({'error': exc.text}, status=exc.status)

    async def _change(self, request):
        sid = request.match_info['sid']
        data = await request.json()
        async with self.locks.setdefault(sid, asyncio.Lock()):
            session = await self.bridge.resume(sid)
            before = await self.snapshot(sid)
            action = data.get('action')
            goal = before['goal']
            if action == 'apply_engine':
                await self.apply_engine(request)
            elif action == 'recover':
                # User-initiated acknowledgement recovery only. Keep the goal paused
                # until they explicitly resume; an already accepted step may finish.
                if goal and goal['status'] == 'active':
                    await self.bridge.rpc('session.control', session_id=sid, action='goal.pause')
                with self.db() as conn:
                    pending = conn.execute('SELECT * FROM workspace_goal_starts WHERE session_id=? AND receipt IS NULL', (sid,)).fetchone()
                if pending:
                    receipt = await self.bridge.rpc('prompt.submit', session_id=sid, input_id=pending['input_id'],
                                                   text=pending['display'], api_text=pending['message'], queued=True)
                    if not receipt.get('admission_id'):
                        raise web.HTTPConflict(text='Движок пока не подтвердил исходный запрос.')
                    with self.db() as conn:
                        conn.execute('UPDATE workspace_goal_starts SET receipt=? WHERE input_id=?',
                                     (json.dumps(receipt), pending['input_id']))
                    self.workspace.admitted(sid, pending['input_id'], receipt, self.workspace.selected_model(sid))
            elif action == 'save':
                fields = self.fields(data)
                if goal and goal['status'] == 'active':
                    raise web.HTTPConflict(text='Сначала поставьте цель на паузу, затем измените описание.')
                revision = (before['draft'] or {}).get('revision', 0)
                if data.get('draft_revision', 0) != revision:
                    raise web.HTTPConflict(text='Описание изменилось в другом окне. Откройте цель заново.')
                with self.db() as conn:
                    conn.execute('''INSERT INTO workspace_goal_drafts VALUES(?,?,?,?)
                        ON CONFLICT(session_id) DO UPDATE SET fields=excluded.fields,revision=excluded.revision,updated=excluded.updated''',
                        (sid, json.dumps(fields, ensure_ascii=False), revision+1, time.time()))
            elif action in {'activate', 'resume', 'pause', 'repeat'}:
                if data.get('revision') != before['revision']:
                    raise web.HTTPConflict(text='Состояние цели изменилось. Обновите окно цели.')
                if action == 'pause':
                    if goal and goal['status'] == 'active':
                        await self.bridge.rpc('session.control', session_id=sid, action='goal.pause')
                else:
                    if not before['engine']['ready']:
                        raise web.HTTPConflict(text='Сначала примените обновление движка. Текущие задания не будут прерваны.')
                    info = session.get('info') or {}
                    endpoint = (info.get('launch_request') or {}).get('base_url')
                    if (info.get('provider') not in {'custom', 'direct-local'}
                            or info.get('model') != self.workspace.selected_model(sid)
                            or (endpoint and endpoint.rstrip('/') != self.workspace.portable.model_url().rstrip('/'))):
                        raise web.HTTPConflict(text='Для цели откройте чат текущей локальной модели.')
                    if self.video_busy():
                        raise web.HTTPConflict(text='Дождитесь завершения генерации видео.')
                    if before['start_uncertain']:
                        raise web.HTTPConflict(text='Предыдущий запуск не подтверждён. Проверьте очередь и журнал; повторный запуск заблокирован.')
                    if session.get('running') or session.get('pending'):
                        raise web.HTTPConflict(text='Дождитесь текущего задания и очереди, затем включите цель.')
                    if action == 'repeat' and goal and goal['status'] in {'active', 'paused'}:
                        raise web.HTTPConflict(text='В этом чате уже есть незавершённая цель. Сначала продолжите её.')
                    if goal and goal['status'] == 'active':
                        return web.json_response(before)
                    repeated = None
                    if action in {'activate', 'repeat'}:
                        if action == 'repeat':
                            repeated = next((item for item in before['history'] if item['id'] == data.get('history_id')), None)
                            if not repeated:
                                raise web.HTTPNotFound(text='Цель не найдена в истории этого чата.')
                            fields = repeated['fields']
                        else:
                            draft = before['draft']
                            if not draft or data.get('draft_revision') != draft['revision']:
                                raise web.HTTPConflict(text='Сначала сохраните актуальное описание цели.')
                            fields = draft['fields']
                        dispatch = await self.bridge.rpc('slash.exec', session_id=sid, command=self.command(fields))
                        if repeated and dispatch.get('message'):
                            dispatch['message'] += ('\n\nПользователь проверил прежний результат и не принял его. '
                                'Предыдущая отметка о достижении этой цели отозвана пользователем. '
                                'Повторно проверь реальное состояние проекта по всем критериям, найди незавершённое '
                                'и исправь его. Не полагайся только на свой прежний отчёт. Сохраняй контекст этого чата.')
                    else:
                        if not goal or goal['status'] != 'paused':
                            raise web.HTTPConflict(text='Нет цели на паузе для продолжения.')
                        result = await self.bridge.rpc('session.control', session_id=sid, action='goal.resume')
                        dispatch = result.get('dispatch') or {}
                    after = await self.snapshot(sid)
                    if not after['goal'] or after['goal']['status'] != 'active':
                        raise web.HTTPConflict(text='Не удалось включить цель. Откройте её состояние заново.')
                    try:
                        await self.enqueue(sid, dispatch, after)
                        if repeated:
                            with self.db() as conn:
                                conn.execute('UPDATE workspace_goal_history SET reopen_count=reopen_count+1,last_reopened=? WHERE id=? AND session_id=?',
                                             (time.time(), repeated['id'], sid))
                    except Exception:
                        # Park the goal after any admission ambiguity. Never repeat the model task.
                        await self.bridge.rpc('session.control', session_id=sid, action='goal.pause')
                        raise
            else:
                raise web.HTTPBadRequest(text='Неизвестное действие с целью.')
            result = await self.snapshot(sid)
            await self.bridge.broadcast({'type': 'goal.changed', 'session_id': sid, 'goal_state': result})
            return web.json_response(result)

    def register(self, app):
        app.router.add_get('/api/sessions/{sid}/goal', self.read)
        app.router.add_post('/api/sessions/{sid}/goal', self.change)
