"""Local workspace presentation and controls over the agent's existing authority."""
from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
import pathlib
import re
import shutil
import sqlite3
import time
import uuid
import base64

from aiohttp import ClientSession, ClientTimeout, ClientError, web
from queue_order import QueueOrder, QueueConflict


LEARNING_NOTE = ('Если в ходе этой задачи найден новый проверенный и повторно применимый способ работы, '
                 'сохрани его через skill_manage в отдельный короткий навык. Проверь, нет ли уже такого навыка. '
                 'Не записывай пароли, cookies, токены, личные данные или неподтверждённые выводы. '
                 'Сохраняй требования, решения и следующий шаг проекта в его файлах памяти. '
                 'Навыки описывают процедуры; не утверждай, что изменены веса модели.')


EXECUTION_NOTE = 'Работай без зацикливания. На простой вопрос отвечай прямо, не запускай терминал без необходимости. Для обычной диагностики задавай timeout 10–30 секунд, для обычной команды — не более 45 секунд. Долгие сборки, загрузки и серверы запускай как управляемые фоновые процессы; для конечных задач включай notify_on_complete. Сохрани ID процесса, не запускай копию; проверяй статус и небольшой хвост журнала, не опрашивай постоянно. Отсутствие вывода само по себе не доказывает зависание: учитывай CPU, изменение файлов и журналов. После первой ошибки выясни причину и измени существенный параметр или способ. После двух одинаковых ошибок не повторяй команду, не меняй только оформление и не увеличивай таймаут. Попробуй другой инструмент или выполни независимые части задания; если нужен внешний доступ/ответ владельца, коротко назови препятствие. На Windows используй корректную оболочку, короткие команды и файлы скриптов вместо сложного вложенного экранирования. Не останавливай модель, пользовательские серверы или чужие процессы ради отмены одной операции.'

EXECUTION_NOTE += '\nДля проверки созданного сайта используй встроенный preview_browser: open адрес dev server, затем look со скриншотом и проверка 390×844 и 1280×800. Обычные browser_exec, Chrome, Яндекс, Opera и Tor остаются отдельными инструментами. Если preview_browser отсутствует в старом чате, прочитай навык built-in-preview и используй локальный CLI с последующим vision_analyze. Не называй чтение HTML визуальной проверкой. Итоговые изображения и видео сохраняй в файл и сообщай точный путь: интерфейс покажет превью.'

class WorkspaceFeatures:
    def __init__(self, root, portable, db, bridge):
        self.root, self.portable, self.db, self.bridge = root, portable, db, bridge
        self.queue_order = QueueOrder(root, portable.HOME)
        self.edit_locks = {}
        with db() as conn:
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS workspace_turns(
              admission_id TEXT PRIMARY KEY,session_id TEXT,input_id TEXT,created REAL,
              started REAL,first_output REAL,finished REAL,status TEXT,model TEXT);
            CREATE TABLE IF NOT EXISTS workspace_preferences(
              session_id TEXT PRIMARY KEY,learning INTEGER DEFAULT 1,selected_model TEXT);
            CREATE TABLE IF NOT EXISTS workspace_notes(
              input_id TEXT PRIMARY KEY,session_id TEXT,text TEXT,created REAL,admission_id TEXT);
            CREATE TABLE IF NOT EXISTS workspace_note_visibility(input_id TEXT PRIMARY KEY,hidden INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS workspace_queue_edits(edit_id TEXT PRIMARY KEY,session_id TEXT,
              old_admission_id TEXT,text TEXT,files_json TEXT,params_json TEXT,receipt_json TEXT,created REAL);
            ''')

    def preferences(self, sid):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM workspace_preferences WHERE session_id=?', (sid,)).fetchone()
        return dict(row) if row else {'learning': True, 'selected_model': None}

    def selected_model(self, sid):
        return self.preferences(sid).get('selected_model') or self.portable.model_id()

    def admitted(self, sid, input_id, receipt, model):
        admission = receipt.get('admission_id')
        if not admission:
            return
        now = time.time()
        with self.db() as conn:
            conn.execute('''INSERT INTO workspace_turns(admission_id,session_id,input_id,created,started,status,model)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(admission_id) DO UPDATE SET
              input_id=COALESCE(workspace_turns.input_id,excluded.input_id),model=COALESCE(workspace_turns.model,excluded.model)''',
              (admission,sid,input_id,now,now if receipt.get('status')=='started' else None,receipt.get('status'),model))

    def event(self, sid, kind, frame):
        admission = frame.get('admission_id')
        if not admission or kind not in {'message.start','message.delta','tool.start','message.complete'}:
            return
        now = time.time()
        with self.db() as conn:
            conn.execute('INSERT OR IGNORE INTO workspace_turns(admission_id,session_id,created,status) VALUES(?,?,?,?)',
                         (admission,sid,now,'started'))
            if kind == 'message.start':
                conn.execute("UPDATE workspace_turns SET started=COALESCE(started,?),status='started' WHERE admission_id=?", (now,admission))
            elif kind in {'message.delta','tool.start'}:
                conn.execute('UPDATE workspace_turns SET first_output=COALESCE(first_output,?) WHERE admission_id=?', (now,admission))
            elif kind == 'message.complete':
                conn.execute("UPDATE workspace_turns SET finished=COALESCE(finished,?),status='terminal' WHERE admission_id=?", (now,admission))

    def durable_usage(self, sid):
        path = self.portable.HOME/'state.db'
        with sqlite3.connect('file:'+path.as_posix()+'?mode=ro', uri=True, timeout=3) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''WITH RECURSIVE lineage(id) AS (
              SELECT id FROM sessions WHERE id=? UNION SELECT s.id FROM sessions s JOIN lineage p ON s.parent_session_id=p.id
              JOIN sessions parent ON parent.id=p.id WHERE parent.end_reason IN ('compressed','compression')
            ) SELECT SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens,
              SUM(reasoning_tokens) AS reasoning_tokens,SUM(api_call_count) AS api_calls
              FROM sessions WHERE id IN (SELECT id FROM lineage)''', (sid,)).fetchone()
            total = dict(row) if row else {}
            overall = conn.execute('SELECT SUM(input_tokens)+SUM(output_tokens) FROM sessions').fetchone()[0]
        total = {k:int(v or 0) for k,v in total.items()}
        total['total_tokens'] = total.get('input_tokens',0)+total.get('output_tokens',0)
        total['all_chats_tokens'] = int(overall or 0)
        return total

    async def decorate(self, snapshot):
        sid = snapshot.get('stored_session_id') or snapshot['session_id']
        with self.db() as conn:
            records = [dict(row) for row in conn.execute('SELECT w.*,COALESCE(t.text,n.text) AS text,COALESCE(t.created,n.created) AS submitted_at FROM workspace_turns w LEFT JOIN turns t ON t.admission_id=w.admission_id LEFT JOIN workspace_notes n ON n.admission_id=w.admission_id WHERE w.session_id=? ORDER BY w.created', (sid,))]
            turns = {row['admission_id']:dict(row) for row in conn.execute("SELECT * FROM turns WHERE session_id=? AND admission_id<>''", (sid,))}
            notes = [dict(row) for row in conn.execute('''SELECT n.* FROM workspace_notes n
                LEFT JOIN workspace_note_visibility v ON v.input_id=n.input_id
                WHERE n.session_id=? AND COALESCE(v.hidden,0)=0 ORDER BY n.created DESC LIMIT 50''', (sid,))]
            all_note_texts = {row['text'] for row in conn.execute('SELECT text FROM workspace_notes WHERE session_id=?', (sid,))}
        for record in records:
            if record.get('submitted_at'):
                record['created']=record['submitted_at']
        messages = []
        for original_message in snapshot.get('messages',[]):
            message=dict(original_message)
            text=message.get('content')
            if message.get('role')=='assistant' and isinstance(text,str) and text.startswith(('[PRIOR CONTEXT','[CONTEXT COMPACTION')):
                message['content']='История чата сжата. Полная запись сохранена на диске; агент может восстановить детали из памяти проекта и истории.'
                message['is_checkpoint']=True
            if message.get('role')=='user' and isinstance(text,str):
                if text.startswith('[Freedom GPT: поступила поправка владельца'):continue
                message['content']=text.split('\n\n[Настройки владельца: выполнение и память]')[0].split('<memory-context>',1)[0].rstrip()
                if text.startswith('[OUT-OF-BAND USER MESSAGE'):
                    message['content']=re.sub(r'^\[OUT-OF-BAND USER MESSAGE[^\n]*\]\n','',text).removesuffix('\n[/OUT-OF-BAND USER MESSAGE]')
                    message['is_correction']=True
            messages.append(message)
        used = set()
        current = None
        note_texts=all_note_texts
        for message in messages:
            if message.get('is_checkpoint'):
                current=None
                continue
            if message.get('role') == 'user':
                raw = message.get('content')
                text = raw if isinstance(raw,str) else ''
                record = next((r for r in records if r['admission_id'] not in used and r.get('text') and text.startswith(r['text'])),None)
                # A delivered correction belongs to the current turn; an idle note
                # can become its own turn and must receive its own timing record.
                out_of_band=message.get('is_correction')
                if current is not None and (out_of_band or (text in note_texts and not (record or {}).get('started'))):
                    continue
                if record:
                    used.add(record['admission_id'])
                    message['timestamp']=record['created']
                current = {'started': (record or {}).get('started') or message.get('timestamp'),
                           'first_output': (record or {}).get('first_output'),
                           'finished': (record or {}).get('finished'), 'model': (record or {}).get('model')}
            elif message.get('role')=='assistant' and current and not message.get('tool_calls') and message.get('content') and not message.get('is_checkpoint'):
                finished = current.get('finished') or message.get('timestamp')
                started = current.get('started')
                message['work_timing'] = {**current,'finished':finished,
                  'elapsed_seconds':max(0,finished-started) if finished and started else None,
                  'first_output_seconds':max(0,current['first_output']-started) if current.get('first_output') and started else None}
        pending = []
        for row in snapshot.get('pending',[]):
            if row.get('status') == 'queued' or row.get('steering'):
                local = turns.get(row.get('admission_id'),{})
                pending.append({**row,'text':local.get('text') or row.get('text',''),'created':local.get('created'),'files':json.loads(local.get('file_ids') or '[]')})
        pending_by_id = {row['admission_id']:row for row in pending}
        for note in notes:
            row = pending_by_id.get(note['admission_id'], {})
            note['queued'] = row.get('status') == 'queued' and not row.get('steering')
            note['steering'] = bool(row.get('steering'))
        usage = await asyncio.to_thread(self.durable_usage, sid)
        with contextlib.suppress(Exception):
            live = await self.bridge.rpc('session.stats',session_id=sid)
            for key in ('input_tokens','output_tokens','reasoning_tokens','api_calls'):
                usage[key] = max(usage.get(key,0),int(live.get(key) or 0))
            usage.update({key:live[key] for key in ('context_tokens','context_length','compression_count','last_turn_tokens') if live.get(key) is not None})
        with contextlib.suppress(Exception):
            access = await self.bridge.rpc('config.get',session_id=sid,key='yolo')
            snapshot.setdefault('info',{})['yolo']=access.get('value')=='1'
        usage['total_tokens'] = usage.get('input_tokens',0)+usage.get('output_tokens',0)
        active_admission = next((row.get('admission_id') for row in snapshot.get('pending',[]) if row.get('status')=='started' and not row.get('steering')),None)
        active_record = next((r for r in records if r['admission_id']==active_admission),None)
        if not active_record and snapshot.get('running'):
            user = next((m for m in reversed(messages) if m.get('role')=='user'),{})
            active_record = {'started':user.get('timestamp'),'created':user.get('timestamp')}
        snapshot.update(messages=messages,queue=pending,notes=notes,work_usage=usage,
                        work_active=active_record if snapshot.get('running') else None,
                        work_preferences=self.preferences(sid))
        if getattr(self,'cloud',None):
            model=(snapshot.get('info') or {}).get('model') or ''
            if model.startswith('freedom-api-'):
                target=self.cloud.target(model)
                snapshot['cloud_route']={**(target or {'id':model,'name':model}),'available':bool(target),'stats':self.cloud.calls.get(model,{})}
        return snapshot

    async def access(self, request):
        sid = request.match_info['sid'];data = await request.json()
        if data.get('mode') not in {'full','manual'}:
            raise ValueError('Выберите режим доступа.')
        await self.bridge.resume(sid)
        result = await self.bridge.rpc('config.set',session_id=sid,key='yolo',value='1' if data['mode']=='full' else '0')
        cfg = self.portable.config();cfg['default_access']=data['mode'];self.portable.write(self.root/'data/settings.json',cfg)
        return web.json_response({'mode':data['mode'],'result':result})

    async def usage(self, request):
        sid=request.match_info['sid']
        # The UI only polls sessions it already opened; this read does not re-attach history.
        if sid not in self.bridge.snapshots:
            await self.bridge.resume(sid)
        result=await asyncio.to_thread(self.durable_usage,sid)
        with contextlib.suppress(Exception):
            live=await self.bridge.rpc('session.stats',session_id=sid)
            for key in ('input_tokens','output_tokens','reasoning_tokens','api_calls'):
                result[key]=max(result.get(key,0),int(live.get(key) or 0))
            result.update({key:live[key] for key in ('context_tokens','context_length','compression_count') if live.get(key) is not None})
        result['total_tokens']=result.get('input_tokens',0)+result.get('output_tokens',0)
        return web.json_response(result)

    async def memory_view(self,request):
        from project_memory_view import store_for
        sid=request.match_info['sid'];snapshot=await self.bridge.resume(sid)
        try:store=store_for(self.portable,snapshot,sid)
        except ValueError:return web.json_response({'ready':False,'needs_project':True,'records':0,'documents':0,'items':[]})
        if store is None:return web.json_response({'ready':False,'needs_project':True,'items':[]})
        query=str(request.query.get('query','')).strip()[:1000]
        def read():
            status=store.status()
            rows=store.search(query,8) if query else store.recent(8)
            return {**status,'items':[{k:v for k,v in row.items() if k!='body'}|{'excerpt':(row.get('excerpt') or row['body'])[:1600]} for row in rows]}
        return web.json_response(await asyncio.to_thread(read))

    async def preferences_set(self, request):
        sid = request.match_info['sid'];data = await request.json()
        await self.bridge.resume(sid)
        if type(data.get('learning')) is not bool:
            raise ValueError('Некорректная настройка навыков.')
        with self.db() as conn:
            conn.execute('INSERT INTO workspace_preferences(session_id,learning) VALUES(?,?) ON CONFLICT(session_id) DO UPDATE SET learning=excluded.learning', (sid,int(data['learning'])))
        return web.json_response(self.preferences(sid))

    async def queue_control(self, request):
        sid = request.match_info['sid'];data = await request.json()
        action = data.get('action')
        if action not in {'cancel','steer','up','down','hide_note'}:
            if action!='edit':raise ValueError('Неизвестное действие очереди.')
        if action=='edit':
            async with self.edit_locks.setdefault(sid,asyncio.Lock()):
                return await self.edit_queued(sid,data)
        if action == 'hide_note':
            with self.db() as conn:
                note = conn.execute('SELECT * FROM workspace_notes WHERE session_id=? AND input_id=?', (sid,data.get('input_id'))).fetchone()
                if not note:
                    raise ValueError('Поправка не найдена.')
                conn.execute('INSERT OR REPLACE INTO workspace_note_visibility VALUES(?,1)', (note['input_id'],))
            await self.bridge.broadcast({'type':'queue.changed','session_id':sid})
            return web.json_response({'ok':True})
        snapshot = await self.bridge.resume(sid)
        row = next((p for p in snapshot.get('pending',[]) if p['admission_id']==data.get('admission_id')),None)
        if not row or row.get('status')!='queued':
            raise ValueError('Задание уже выполняется или завершено. Обновите очередь.')
        if action in {'up','down'}:
            try:
                result = await asyncio.to_thread(self.queue_order.move,sid,row['admission_id'],action,
                    data.get('expected_order'),snapshot['authority_epoch'])
            except QueueConflict as exc:
                return web.json_response({'error':str(exc)},status=409)
            await self.bridge.broadcast({'type':'queue.changed','session_id':sid})
            return web.json_response(result)
        # Native cancel may interrupt if claim races this read. Never offer it on running rows.
        result = await self.bridge.rpc('prompt.cancel' if action=='cancel' else 'prompt.steer_queued',
                                       session_id=sid,admission_id=row['admission_id'])
        if action=='steer':
            with self.db() as conn:
                local=conn.execute('SELECT * FROM turns WHERE session_id=? AND admission_id=?',(sid,row['admission_id'])).fetchone()
                input_id=local['input_id'] if local else 'steer-'+row['admission_id']
                conn.execute('INSERT OR IGNORE INTO workspace_notes VALUES(?,?,?,?,?)',
                    (input_id,sid,local['text'] if local else row['text'],time.time(),row['admission_id']))
        if action == 'cancel' and result.get('status') == 'terminal':
            with self.db() as conn:
                conn.execute("UPDATE workspace_turns SET status='cancelled',finished=COALESCE(finished,?) WHERE admission_id=?", (time.time(),row['admission_id']))
                conn.execute('''INSERT OR REPLACE INTO workspace_note_visibility SELECT input_id,1
                    FROM workspace_notes WHERE session_id=? AND admission_id=?''', (sid,row['admission_id']))
        await self.bridge.broadcast({'type':'queue.changed','session_id':sid})
        return web.json_response(result)

    async def edit_queued(self,sid,data):
        text=str(data.get('text') or '').strip()
        edit_id=str(data.get('edit_id') or '')
        old_id=str(data.get('admission_id') or '')
        if not text or len(text)>100000 or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',edit_id):
            raise ValueError('Задание должно содержать от 1 до 100 000 символов.')
        with self.db() as conn:
            prior=conn.execute('SELECT * FROM workspace_queue_edits WHERE edit_id=?',(edit_id,)).fetchone()
        if prior and (prior['session_id']!=sid or prior['old_admission_id']!=old_id or prior['text']!=text):
            raise ValueError('Идентификатор изменения уже использован.')
        if prior and prior['receipt_json']:
            return web.json_response(json.loads(prior['receipt_json']))
        snapshot=await self.bridge.resume(sid)
        row=next((p for p in snapshot.get('pending',[]) if p['admission_id']==old_id),None)
        if prior:
            params=json.loads(prior['params_json']);file_ids=json.loads(prior['files_json'])
        else:
            if not row or row.get('status')!='queued' or 'replace' not in row.get('controls',[]):
                return web.json_response({'error':'Задание уже началось или не поддерживает редактирование. Текст изменений сохранён в форме.'},status=409)
            with self.db() as conn:
                original=conn.execute('SELECT * FROM turns WHERE session_id=? AND admission_id=?',(sid,old_id)).fetchone()
                original_text=original['text'] if original else row['text']
                file_ids=json.loads(original['file_ids']) if original else []
                selected=[]
                for identifier in file_ids:
                    found_file=conn.execute('SELECT * FROM files WHERE id=?',(identifier,)).fetchone()
                    if not found_file:raise ValueError('Вложение не найдено. Исходное задание сохранено в очереди.')
                    selected.append(dict(found_file))
            if data.get('expected_text')!=original_text:
                return web.json_response({'error':'Текст задания уже изменился. Обновите очередь.'},status=409)
            refs=[];attachments=[]
            for item in selected:
                if item['mime'].startswith('image/'):
                    raw=pathlib.Path(item['path']).read_bytes()
                    if item['mime']=='image/bmp':
                        import io
                        from PIL import Image
                        buffer=io.BytesIO()
                        with Image.open(io.BytesIO(raw)) as image:image.save(buffer,format='PNG')
                        raw=buffer.getvalue()
                    staged=await self.bridge.rpc('image.attach_bytes',session_id=sid,content_base64=base64.b64encode(raw).decode(),filename=item['name'])
                    attachments.append({'path':staged['path'],'mime':staged['mime']})
                else:
                    staged=await self.bridge.rpc('file.attach',session_id=sid,path=item['path'],name=item['name'])
                    refs.append(staged['ref_text'])
            wire=text+('\n\nПрикреплённые пользователем файлы:\n'+'\n'.join(refs) if refs else '')
            params={'session_id':sid,'admission_id':old_id,'submission_id':edit_id,'text':wire}
            if attachments:params['attachments']=attachments
            with self.db() as conn:
                conn.execute('INSERT INTO workspace_queue_edits VALUES(?,?,?,?,?,?,?,?)',
                    (edit_id,sid,old_id,text,json.dumps(file_ids),json.dumps(params),'',time.time()))
        # The native owner replaces and retires inside one transaction. An exact retry
        # uses the stored payload and input ID, including the staged media identities.
        # Normalize an intent saved by an older local build before it reached admission.
        params['submission_id']=params.pop('input_id',params.get('submission_id',edit_id))
        params.pop('api_text',None)
        receipt=await self.bridge.rpc('prompt.replace_queued',**params)
        position_kept=False
        if receipt.get('status')=='queued':
            try:
                position_kept=await asyncio.to_thread(self.queue_order.place_replacement,sid,old_id,
                    receipt['admission_id'],data.get('expected_order'),snapshot['authority_epoch'])
            except (OSError,sqlite3.Error,QueueConflict):pass
        result={'ok':True,'edited':True,'receipt':receipt,'position_kept':position_kept}
        now=time.time()
        with self.db() as conn:
            conn.execute('INSERT OR IGNORE INTO turns VALUES(?,?,?,?,?,?)',
                (edit_id,sid,text,json.dumps(file_ids),receipt['admission_id'],now))
            conn.execute("UPDATE workspace_turns SET status='replaced',finished=COALESCE(finished,?) WHERE admission_id=?",(now,old_id))
            conn.execute('UPDATE workspace_queue_edits SET receipt_json=? WHERE edit_id=?',(json.dumps(result),edit_id))
        self.admitted(sid,edit_id,receipt,self.selected_model(sid))
        await self.bridge.broadcast({'type':'queue.changed','session_id':sid})
        return web.json_response(result)

    async def note(self, request):
        sid = request.match_info['sid'];data = await request.json()
        text = str(data.get('text') or '').strip()
        input_id = str(data.get('input_id') or uuid.uuid4().hex)
        if not text or len(text)>10000 or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',input_id):
            raise ValueError('Заметка должна содержать от 1 до 10 000 символов.')
        await self.bridge.resume(sid)
        with self.db() as conn:
            old = conn.execute('SELECT * FROM workspace_notes WHERE input_id=?',(input_id,)).fetchone()
            if old and (old['session_id']!=sid or old['text']!=text):
                raise ValueError('Идентификатор заметки уже использован.')
        receipt = await self.bridge.rpc('prompt.submit',session_id=sid,input_id=input_id,text=text,queued=True)
        with self.db() as conn:
            conn.execute('INSERT OR IGNORE INTO workspace_notes VALUES(?,?,?,?,?)',(input_id,sid,text,time.time(),receipt['admission_id']))
        self.admitted(sid,input_id,receipt,self.selected_model(sid))
        state = 'queued'
        if receipt.get('status')=='queued':
            try:
                receipt = await self.bridge.rpc('prompt.steer_queued',session_id=sid,admission_id=receipt['admission_id'])
                state = 'steering'
            except Exception:
                # The accepted durable note remains a normal queued turn if the steer boundary passed.
                state = 'queued'
        elif receipt.get('status')=='started':
            state = 'started'
            if old:
                current=await self.bridge.resume(sid)
                if any(row.get('admission_id')==receipt['admission_id'] and row.get('steering') for row in current.get('pending',[])):
                    state='steering'
        elif receipt.get('outcome') in {'steering','steered'}:
            state = 'steering'
        return web.json_response({'state':state,'receipt':receipt})

    async def model_options(self, request):
        body={'data':[]}
        try:
            async with ClientSession(timeout=ClientTimeout(total=4)) as http:
                async with http.get(self.portable.model_url()+'/models',allow_redirects=False) as response:
                    if response.status==200:body=await response.json()
        except (OSError,ClientError,asyncio.TimeoutError):pass
        rows=[{'id':m['id'],'name':m.get('name') or m['id'],'kind':'local'} for m in body.get('data',[]) if isinstance(m.get('id'),str)]
        if not any(m['id']==self.portable.model_id() for m in rows):rows.append({'id':self.portable.model_id(),'name':'Huihui Coder · локально','kind':'local','available':False})
        if getattr(self,'cloud',None):rows.extend(self.cloud.models())
        return web.json_response({'models':rows,
                                  'url':self.portable.model_url()})

    async def model_set(self, request):
        sid = request.match_info['sid'];data = await request.json()
        selected = str(data.get('model') or '').strip()
        options = json.loads((await self.model_options(request)).body)
        if selected not in {row['id'] for row in options['models']}:
            raise ValueError('Выберите модель, доступную на подключённом локальном API.')
        snapshot = await self.bridge.resume(sid)
        if (snapshot.get('info') or {}).get('model')==selected:
            return web.json_response({'status':'unchanged','model':selected})
        if snapshot.get('running') or snapshot.get('pending'):
            raise ValueError('Переключите модель после выполнения очереди. История чата сохраняется.')
        if getattr(self,'cloud',None):await asyncio.to_thread(self.cloud.sync_aliases)
        payload = {'model':selected if self.cloud.target(selected) else 'freedom-local-runtime','provider':'custom'}
        if data.get('confirm'):
            payload['confirm']=data['confirm']
        result = await self.bridge.rpc('session.mutate',session_id=sid,request_id=uuid.uuid4().hex,
          expected_revision=snapshot['revision'],expected_generation=snapshot['execution_generation'],operation='model',payload=payload)
        if result.get('status')!='confirmation_required':
            with self.db() as conn:
                conn.execute('INSERT INTO workspace_preferences(session_id,selected_model) VALUES(?,?) ON CONFLICT(session_id) DO UPDATE SET selected_model=excluded.selected_model',(sid,selected))
                endpoint=self.cloud.proxy_url() if self.cloud.target(selected) else self.portable.model_url()
                conn.execute('INSERT OR REPLACE INTO routes VALUES(?,?,?)',(sid,selected,endpoint.rstrip('/')))
        return web.json_response(result)

    def skill_rows(self):
        root = (self.portable.HOME/'skills').resolve()
        rows = []
        for path in root.rglob('SKILL.md'):
            if not path.resolve().is_relative_to(root) or path.stat().st_size>200000:
                continue
            text = path.read_text(encoding='utf-8-sig')
            name = re.search(r'^name:\s*(.+)$',text,re.M)
            description = re.search(r'^description:\s*(.+)$',text,re.M)
            rows.append({'id':path.parent.relative_to(root).as_posix(),'name':name.group(1).strip('"\' ') if name else path.parent.name,
              'description':description.group(1).strip('"\' ') if description else '', 'modified':path.stat().st_mtime})
        return sorted(rows,key=lambda row:row['modified'],reverse=True)

    async def skills(self, request):
        return web.json_response({'skills':await asyncio.to_thread(self.skill_rows),'folder':str(self.portable.HOME/'skills')})

    async def skill_save(self, request):
        data = await request.json()
        name = str(data.get('name') or '').strip()
        description = str(data.get('description') or '').strip()
        instructions = str(data.get('instructions') or '').strip()
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,63}',name) or not description or len(description)>600 or not instructions or len(instructions)>60000:
            raise ValueError('Укажите имя латиницей (2–64 символа), описание и инструкции.')
        root = (self.portable.HOME/'skills').resolve()
        target = root/'user-taught'/name/'SKILL.md'
        if any(row['name']==name and row['id']!='user-taught/'+name for row in self.skill_rows()):
            raise ValueError('Навык с таким именем уже существует. Выберите другое имя.')
        if not target.resolve().is_relative_to(root):
            raise ValueError('Недопустимый путь навыка.')
        content = '---\nname: '+name+'\ndescription: '+json.dumps(description,ensure_ascii=False)+'\n---\n\n'+instructions+'\n'
        if target.exists():
            archive = self.root/'archive'/'skill-edits'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            archive.mkdir(parents=True);shutil.copy2(target,archive/(name+'.md'))
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary = target.with_name('.SKILL.'+uuid.uuid4().hex+'.new')
        temporary.write_text(content,encoding='utf8');temporary.replace(target)
        return web.json_response({'ok':True,'name':name,'path':str(target)})

    def register(self, app):
        app.router.add_get('/api/sessions/{sid}/memory',self.memory_view)
        app.router.add_post('/api/sessions/{sid}/access',self.access)
        app.router.add_get('/api/sessions/{sid}/usage',self.usage)
        app.router.add_post('/api/sessions/{sid}/preferences',self.preferences_set)
        app.router.add_post('/api/sessions/{sid}/queue',self.queue_control)
        app.router.add_post('/api/sessions/{sid}/notes',self.note)
        app.router.add_get('/api/session-models',self.model_options)
        app.router.add_post('/api/sessions/{sid}/model',self.model_set)
        app.router.add_get('/api/skills',self.skills)
        app.router.add_post('/api/skills',self.skill_save)
