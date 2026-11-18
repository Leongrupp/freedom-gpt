"""Independent conversations created by the installed owner's canonical branch verb."""
import asyncio
import re
import time
import uuid

from aiohttp import web
from hermes_cli.gateway_client import GatewayRPCError


class ChatBranches:
    def __init__(self, db, bridge, workspace, portable):
        self.db, self.bridge, self.workspace, self.portable = db, bridge, workspace, portable
        self.locks = {}
        with db() as conn:
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS chat_branch_requests(
              request_id TEXT PRIMARY KEY,parent_id TEXT NOT NULL,title TEXT NOT NULL,
              parent_title TEXT NOT NULL,revision INTEGER NOT NULL,generation INTEGER NOT NULL,
              child_id TEXT,error TEXT,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_branches(
              child_id TEXT PRIMARY KEY,parent_id TEXT NOT NULL,parent_title TEXT NOT NULL,
              copied_messages INTEGER NOT NULL,created REAL NOT NULL);
            ''')

    def rows(self):
        with self.db() as conn:
            rows = conn.execute('''SELECT b.*,COALESCE(NULLIF(c.title,''),b.parent_title) AS source_title
              FROM chat_branches b LEFT JOIN chats c ON c.id=b.parent_id''').fetchall()
        return {r['child_id']: {'parent_id':r['parent_id'], 'parent_title':r['source_title'],
                'copied_messages':r['copied_messages'], 'created':r['created']} for r in rows}

    @staticmethod
    def refused(message, status=409):
        return web.json_response({'error':message, 'code':'branch_refused'}, status=status)

    async def create(self, request):
        parent = request.match_info['sid']
        data = await request.json()
        identifier = str(data.get('request_id') or '')
        title = str(data.get('title') or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', identifier) or not 1 <= len(title) <= 160:
            return self.refused('Укажите название ветки до 160 символов.', 400)
        async with self.locks.setdefault(parent, asyncio.Lock()):
            return await self._create(parent, identifier, title, request)

    async def _create(self, parent, identifier, title, request=None):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM chat_branch_requests WHERE request_id=?', (identifier,)).fetchone()
        if row:
            row = dict(row)
            if row['parent_id'] != parent or row['title'] != title:
                return self.refused('Этот запрос уже использован для другой ветки.')
            if row['child_id']:
                cloud=getattr(self.workspace,'cloud',None)
                if cloud and cloud.auto:await cloud.auto.clone(parent,row['child_id'],request)
                return web.json_response({'id':row['child_id'], 'branch':self.rows().get(row['child_id'])})
            if row['error']:
                return self.refused(row['error'])
        else:
            snapshot = await self.bridge.resume(parent)
            if snapshot.get('running') or snapshot.get('pending'):
                return self.refused('Дождитесь завершения ответа и очереди исходного чата, затем создайте ветку.')
            with self.db() as conn:
                meta = conn.execute('SELECT title FROM chats WHERE id=?', (parent,)).fetchone()
                parent_title = (meta['title'] if meta else None) or (snapshot.get('info') or {}).get('title') or 'Чат'
                row = {'request_id':identifier, 'parent_id':parent, 'title':title, 'parent_title':parent_title,
                       'revision':snapshot['revision'], 'generation':snapshot['execution_generation'], 'created':time.time()}
                conn.execute('''INSERT INTO chat_branch_requests
                  (request_id,parent_id,title,parent_title,revision,generation,created) VALUES(?,?,?,?,?,?,?)''',
                  tuple(row[k] for k in ('request_id','parent_id','title','parent_title','revision','generation','created')))
        try:
            # Reuse the persisted fences and request id after a lost response. The owner returns
            # its committed receipt before checking the parent's now-advanced revision.
            result = await self.bridge.rpc('session.mutate', session_id=parent, request_id=identifier,
                expected_revision=row['revision'], expected_generation=row['generation'],
                operation='branch', payload={'title':title})
        except GatewayRPCError as exc:
            message = ('Исходный чат изменился. Закройте это окно и создайте ветку ещё раз.'
                       if str(exc) in {'revision_conflict','stale_generation'} else
                       'Не удалось создать ветку. Дождитесь завершения работы исходного чата и повторите.')
            with self.db() as conn:
                conn.execute('UPDATE chat_branch_requests SET error=? WHERE request_id=?', (message,identifier))
            return self.refused(message)
        except Exception:
            return web.json_response({'error':'Ответ о создании ветки не получен. Нажмите «Создать ветку» ещё раз: новый дубликат не создастся.',
                                      'code':'branch_uncertain'}, status=503)
        child = result.get('branched_session_id')
        if not child:
            return web.json_response({'error':'Проверяем результат создания ветки. Повторите тот же запрос.',
                                      'code':'branch_uncertain'}, status=503)
        snapshot = await self.bridge.resume(child)
        info = snapshot.get('info') or {}
        model = info.get('model') or self.portable.model_id()
        cloud = getattr(self.workspace, 'cloud', None)
        endpoint = cloud.proxy_url() if cloud and model.startswith(('freedom-api-','freedom-auto-')) else self.portable.model_url()
        preference = self.workspace.preferences(parent)
        now = time.time()
        with self.db() as conn:
            # All presentation projections commit together; a retry can safely finish them.
            conn.execute('INSERT OR IGNORE INTO chats(id,title,updated) VALUES(?,?,?)', (child,title,now))
            conn.execute('INSERT OR REPLACE INTO routes VALUES(?,?,?)', (child,model,endpoint.rstrip('/')))
            conn.execute('''INSERT OR IGNORE INTO workspace_preferences(session_id,learning,selected_model)
              VALUES(?,?,?)''', (child,int(preference.get('learning',True)),model))
            if not conn.execute('SELECT 1 FROM chat_branches WHERE child_id=?', (child,)).fetchone():
                history_ids = {}
                def history_id(admission):
                    if not admission:
                        return ''
                    if admission not in history_ids:
                        history_ids[admission] = 'branch-history-' + uuid.uuid4().hex
                    return history_ids[admission]
                for timing in conn.execute('SELECT * FROM workspace_turns WHERE session_id=?', (parent,)).fetchall():
                    conn.execute('INSERT INTO workspace_turns VALUES(?,?,?,?,?,?,?,?,?)',
                        (history_id(timing['admission_id']),child,uuid.uuid4().hex,timing['created'],timing['started'],
                         timing['first_output'],timing['finished'],timing['status'],timing['model']))
                for artifact in conn.execute('SELECT * FROM artifacts WHERE session_id=?', (parent,)).fetchall():
                    conn.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?)',
                        (uuid.uuid4().hex,child,artifact['path'],artifact['name'],artifact['mime'],artifact['created']))
                for turn in conn.execute('SELECT * FROM turns WHERE session_id=?', (parent,)).fetchall():
                    conn.execute('INSERT INTO turns VALUES(?,?,?,?,?,?)',
                        (uuid.uuid4().hex,child,turn['text'],turn['file_ids'],history_id(turn['admission_id']),turn['created']))
                for note in conn.execute('SELECT * FROM workspace_notes WHERE session_id=?', (parent,)).fetchall():
                    note_id = uuid.uuid4().hex
                    conn.execute('INSERT INTO workspace_notes VALUES(?,?,?,?,?)',
                        (note_id,child,note['text'],note['created'],history_id(note['admission_id'])))
                    visibility = conn.execute('SELECT hidden FROM workspace_note_visibility WHERE input_id=?', (note['input_id'],)).fetchone()
                    if visibility:
                        conn.execute('INSERT INTO workspace_note_visibility VALUES(?,?)', (note_id,visibility['hidden']))
            conn.execute('INSERT OR IGNORE INTO chat_branches VALUES(?,?,?,?,?)',
                (child,parent,row['parent_title'],result.get('copied_messages',0),now))
            conn.execute('UPDATE chat_branch_requests SET child_id=? WHERE request_id=?', (child,identifier))
        if cloud and cloud.auto:await cloud.auto.clone(parent,child,request)
        return web.json_response({'id':child, 'branch':self.rows()[child]})

    def register(self, app):
        app.router.add_post('/api/sessions/{sid}/branch', self.create)
