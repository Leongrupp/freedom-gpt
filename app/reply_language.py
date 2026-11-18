"""Owner-selected reply language, independent from the interface language."""
from __future__ import annotations

import asyncio
import re

from aiohttp import web
from bootstrap import HOME,read,write
from agent_autonomy import VERSION as AUTONOMY_VERSION, input_block as autonomy_block, owner_prompt
import agent_personality

START = '[Freedom: reply language]'
END = '[/Freedom: reply language]'
RULES = {
    'ru': ('Отвечай пользователю по-русски: пояснения, сообщения о ходе работы и итоговый ответ. '
           'Если явно заказан перевод или материал на другом языке, используй указанный язык для этого материала. '
           'Не переводи код, команды, пути, имена файлов, URL и точные цитаты.'),
    'auto': ('Отвечай на языке последнего задания пользователя. Определяй язык по его собственным словам, '
             'а не по приложенным логам, коду, ссылкам или цитатам. Если язык неясен, отвечай по-русски. '
             'Если явно заказан перевод или материал на другом языке, используй указанный язык для этого материала. '
             'Не переводи код, команды, пути, имена файлов и URL.'),
}


class ReplyLanguage:
    def __init__(self, root, db):
        self.path = root / 'data/reply-language.json'
        self.db = db
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS reply_language_inputs '
                         '(input_key TEXT PRIMARY KEY, mode TEXT NOT NULL)')
            columns={row[1] for row in conn.execute('PRAGMA table_info(reply_language_inputs)')}
            if 'autonomy_version' not in columns:
                conn.execute('ALTER TABLE reply_language_inputs ADD COLUMN autonomy_version INTEGER NOT NULL DEFAULT 0')
            if 'personality' not in columns:
                conn.execute("ALTER TABLE reply_language_inputs ADD COLUMN personality TEXT NOT NULL DEFAULT ''")
            tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table,ident,method in [('turns','input_id','prompt.submit'),
                                       ('workspace_notes','input_id','prompt.submit'),
                                       ('workspace_queue_edits','edit_id','prompt.replace_queued')]:
                if table in tables:
                    # Admissions from earlier builds must retain their original
                    # bytes when an old browser repeats an uncertain request.
                    conn.execute('INSERT OR IGNORE INTO reply_language_inputs(input_key,mode) '
                                 f"SELECT ?||session_id||':'||{ident},'legacy' FROM {table}",
                                 (method+':',))

    def status(self):
        mode = read(self.path, {}).get('mode', 'ru')
        return {'mode': mode if mode in RULES else 'ru'}

    def block(self, mode):
        return START + '\n' + RULES[mode] + '\n' + END

    async def sync_owner_prompt(self, mode=None):
        await asyncio.to_thread(self._sync_owner_prompt, mode or self.status()['mode'])

    def _sync_owner_prompt(self, mode):
        from autonomy_profile import sync_goal_autonomy
        sync_goal_autonomy()
        from hermes_cli.config import read_user_config_raw
        from hermes_cli.personality import prompt_text
        from utils import atomic_roundtrip_yaml_update
        config_path = HOME / 'config.yaml'
        cfg = read_user_config_raw(config_path)
        current = prompt_text((cfg.get('agent') or {}).get('system_prompt'))
        # Own only our marked block; preserve the owner's other instructions.
        pattern = r'\n*' + re.escape(START) + r'\n.*?\n' + re.escape(END)
        base = re.sub(pattern, '', current, flags=re.S).rstrip()
        updated = owner_prompt((base + '\n\n' if base else '') + self.block(mode))
        if updated != current:
            atomic_roundtrip_yaml_update(config_path, 'agent.system_prompt', updated)

    def prepare(self, method, params):
        if method not in {'prompt.submit', 'prompt.replace_queued'}:
            return params
        text = params.get('text')
        if not isinstance(text, str):
            return params
        mode = self.status()['mode']
        autonomy_version = AUTONOMY_VERSION
        personality = agent_personality.note()
        ident = params.get('input_id') or params.get('submission_id')
        if ident:
            key = method + ':' + str(params.get('session_id', '')) + ':' + str(ident)
            # A repeated admission must keep its exact original payload even if
            # the language setting changed after the first attempt.
            with self.db() as conn:
                conn.execute('INSERT OR IGNORE INTO reply_language_inputs(input_key,mode,autonomy_version,personality) VALUES(?,?,?,?)', (key, mode, autonomy_version,personality))
                mode,autonomy_version,personality = conn.execute('SELECT mode,autonomy_version,personality FROM reply_language_inputs WHERE input_key=?', (key,)).fetchone()
        if mode == 'legacy':
            return params
        result = dict(params)
        suffix = '\n\n' + self.block(mode)
        if autonomy_version:
            suffix += '\n\n' + autonomy_block(autonomy_version)
        if personality:
            suffix += '\n\n' + personality
        if isinstance(result.get('api_text'), str):
            result['api_text'] += suffix
        elif result.get('attachments') or method == 'prompt.replace_queued':
            # Let the native owner add image annotations to the canonical text.
            result['text'] = text + suffix
        else:
            result['api_text'] = text + suffix
        return result

    def register(self, app, bridge):
        agent_personality.register(app)
        async def status(request):
            return web.json_response(self.status())

        async def change(request):
            value = await request.json()
            mode = value.get('mode')
            if mode not in RULES:
                raise ValueError('Выберите «Всегда по-русски» или «На языке задания».')
            await self.sync_owner_prompt(mode)
            write(self.path, {'mode': mode})
            return web.json_response(self.status())

        app.router.add_get('/api/reply-language', status)
        app.router.add_post('/api/reply-language', change)
