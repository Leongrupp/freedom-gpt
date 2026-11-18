"""Private Windows voice input. Local CPU transcription, separate from agent inference."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
import wave
from array import array

from aiohttp import web

VOICE_NOTE = (
    'Это задание продиктовано голосом. Сначала преобразуй расшифровку в ясную рабочую задачу: '
    'выдели желаемый результат, явные требования и критерии готовности, учитывая историю чата. '
    'Исправляй речевые повторы и очевидные оговорки, сохраняя смысл. Не добавляй за пользователя '
    'новые функции, адреса, имена файлов или разрешения. Если существенная неоднозначность '
    'не позволяет безопасно начать, задай короткий вопрос; иначе сразу выполняй задачу. '
    'Для задачи с действиями кратко обозначь понимание перед работой; для простого вопроса '
    'ответь прямо и соблюдай запрошенный пользователем формат. Действующий режим доступа сохраняется.'
)
ID = re.compile(r'[a-f0-9]{32}')

def recognition_quality(document):
    probabilities=[token['p'] for segment in document.get('transcription',[]) for token in segment.get('tokens',[])
                   if isinstance(token.get('p'),(int,float)) and 0<=token['p']<=1 and str(token.get('text','')).strip() and not str(token.get('text','')).strip().startswith(('[','<|'))]
    mean=sum(probabilities)/len(probabilities) if probabilities else None
    return {'language':document.get('result',{}).get('language'),
            'mean_token_probability':round(mean,3) if mean is not None else None,
            'low_confidence':mean is not None and mean<.45}


class PersonalVoice:
    def __init__(self, root, enabled=False):
        self.root=pathlib.Path(root).resolve()
        self.enabled=bool(enabled)
        self.folder=self.root/'.cache/personal-voice'
        self.database=self.root/'data/personal-voice.sqlite3'
        self.queue=asyncio.Queue(maxsize=8)
        self.worker=None
        self.process=None
        self.current=None
        self.lock=asyncio.Lock()
        self.config={}
        if self.enabled:
            self.folder.mkdir(parents=True,exist_ok=True)
            self.database.parent.mkdir(parents=True,exist_ok=True)
            with self.db() as conn:
                conn.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS recordings(
                  id TEXT PRIMARY KEY,digest TEXT NOT NULL,state TEXT NOT NULL,
                  created REAL NOT NULL,updated REAL NOT NULL,text TEXT DEFAULT '',
                  error TEXT DEFAULT '',seconds REAL DEFAULT 0,session_id TEXT,admission_id TEXT);''')
                if 'ephemeral' not in {r[1] for r in conn.execute('PRAGMA table_info(recordings)')}:
                    conn.execute('ALTER TABLE recordings ADD COLUMN ephemeral INTEGER NOT NULL DEFAULT 0')
                if 'recognition' not in {r[1] for r in conn.execute('PRAGMA table_info(recordings)')}:
                    conn.execute("ALTER TABLE recordings ADD COLUMN recognition TEXT NOT NULL DEFAULT '{}'")
                if 'language' not in {r[1] for r in conn.execute('PRAGMA table_info(recordings)')}:
                    conn.execute("ALTER TABLE recordings ADD COLUMN language TEXT NOT NULL DEFAULT 'auto'")
            try:self.config=json.loads((self.root/'data/personal-voice.json').read_text(encoding='utf-8-sig'))
            except (OSError,ValueError):self.config={}

    @contextlib.contextmanager
    def db(self):
        connection=sqlite3.connect(self.database,timeout=5)
        connection.row_factory=sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:connection.close()

    def asset(self, name):
        path=(self.root/self.config.get(name,'')).resolve()
        if not path.is_relative_to((self.root/'runtime/personal-voice').resolve()) or not path.is_file():
            raise ValueError('Локальный движок распознавания ещё не готов.')
        return path

    def status(self):
        ready=False
        if self.enabled and self.config.get('enabled'):
            try:
                self.asset('binary');self.asset('model')
                self.ffmpeg();ready=True
            except ValueError:pass
        return {'enabled':self.enabled,'ready':ready,'local':True,'device':'cpu',
                'model':'Whisper small','max_seconds':300,'max_bytes':16*1024*1024}

    def ffmpeg(self):
        configured=pathlib.Path(self.config.get('ffmpeg',''))
        if configured.is_file():return str(configured)
        installed=shutil.which('ffmpeg')
        if installed:return installed
        raise ValueError('Не найден установленный обработчик звука FFmpeg.')

    def row(self, recording):
        if not ID.fullmatch(recording):raise ValueError('Некорректный номер голосовой записи.')
        with self.db() as conn:
            row=conn.execute('SELECT * FROM recordings WHERE id=?',(recording,)).fetchone()
        if not row:raise ValueError('Голосовая запись не найдена.')
        return dict(row)

    @staticmethod
    def public(row):
        result={key:row[key] for key in ('id','state','text','error','seconds','session_id','admission_id')}
        result['recognition']=json.loads(dict(row).get('recognition') or '{}');return result

    def update(self, recording, **values):
        allowed={'state','text','error','seconds','session_id','admission_id','recognition'}
        if not values or set(values)-allowed:raise ValueError('Invalid voice state update')
        with self.db() as conn:
            conn.execute('UPDATE recordings SET '+','.join(key+'=?' for key in values)+',updated=? WHERE id=?',
                         (*values.values(),time.time(),recording))

    async def upload(self, request):
        if not self.status()['ready']:return web.json_response({'error':'Распознавание голоса ещё не готово.'},status=503)
        language=request.query.get('language','auto')
        if language not in {'ru','en','auto'}:raise ValueError('Выберите русский, английский или автоматическое распознавание.')
        recording=request.match_info['recording']
        if not ID.fullmatch(recording):raise web.HTTPBadRequest()
        if self.queue.full():return web.json_response({'error':'Очередь распознавания заполнена. Повторите позже.'},status=429)
        directory=self.folder/recording;directory.mkdir(exist_ok=True)
        part=directory/(uuid.uuid4().hex+'.part')
        digest=hashlib.sha256();size=0
        try:
            reader=await request.multipart();field=await reader.next()
            if not field or field.name!='audio':raise ValueError('Добавьте голосовую запись.')
            with part.open('wb') as stream:
                while chunk:=await field.read_chunk(65536):
                    size+=len(chunk)
                    if size>16*1024*1024:raise ValueError('Голосовая запись превышает 16 МБ.')
                    digest.update(chunk);stream.write(chunk)
                stream.flush();os.fsync(stream.fileno())
            if not size:raise ValueError('Запись пустая. Повторите диктовку.')
            async with self.lock:
                with self.db() as conn:
                    prior=conn.execute('SELECT * FROM recordings WHERE id=?',(recording,)).fetchone()
                    if prior:
                        if prior['digest']!=digest.hexdigest() or prior['language']!=language:
                            return web.json_response({'error':'Этот номер уже принадлежит другой записи.'},status=409)
                        if prior['state']=='error' and (directory/'audio.upload').is_file():
                            self.update(recording,state='queued',error='');self.queue.put_nowait(recording)
                            return web.json_response(self.public(self.row(recording)),status=202)
                        return web.json_response(self.public(dict(prior)))
                    if self.queue.full():return web.json_response({'error':'Повторите распознавание позже.'},status=429)
                    os.replace(part,directory/'audio.upload')
                    now=time.time()
                    conn.execute('INSERT INTO recordings(id,digest,state,created,updated,ephemeral,language) VALUES(?,?,?,?,?,?,?)',
                                 (recording,digest.hexdigest(),'queued',now,now,int(request.path.startswith('/api/jarvis/')),language))
                self.queue.put_nowait(recording)
            return web.json_response(self.public(self.row(recording)),status=202)
        finally:part.unlink(missing_ok=True)

    async def read(self, request):return web.json_response(self.public(self.row(request.match_info['recording'])))

    async def get_status(self, request):return web.json_response(self.status())

    async def discard(self, request):
        recording=request.match_info['recording'];row=self.row(recording)
        if not row.get('admission_id'):self.update(recording,state='discarded')
        if self.current==recording and self.process and self.process.returncode is None:
            self.process.kill();await self.process.wait()
        self.remove_audio(recording)
        return web.json_response({'ok':True})

    def remove_audio(self, recording):
        directory=self.folder/recording
        for name in ('audio.upload','audio.wav','transcript.txt','transcript.json'):
            (directory/name).unlink(missing_ok=True)

    async def command(self, args, timeout):
        flags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=='nt' else 0
        process=await asyncio.create_subprocess_exec(*map(str,args),cwd=self.root,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=flags)
        self.process=process
        try:
            stdout,stderr=await asyncio.wait_for(process.communicate(),timeout)
            if process.returncode:raise ValueError('Не удалось обработать запись. Попробуйте записать её ещё раз.')
            return stdout,stderr
        except BaseException:
            if process.returncode is None:
                process.kill();await process.wait()
            raise
        finally:self.process=None

    @staticmethod
    def inspect_wav(path):
        with wave.open(str(path),'rb') as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):
                raise ValueError('Не удалось преобразовать формат записи.')
            seconds=audio.getnframes()/16000
            if seconds<.35:raise ValueError('Запись слишком короткая. Скажите задание ещё раз.')
            if seconds>300.1:raise ValueError('Записывайте задание не дольше пяти минут.')
            samples=array('h',audio.readframes(audio.getnframes()))
        # Only near-digital silence is rejected here; quiet human speech remains eligible.
        rms=math.sqrt(sum(value*value for value in samples)/max(1,len(samples)))
        if rms<3:raise ValueError('В записи не слышно речи. Проверьте микрофон и повторите.')
        return seconds

    async def transcribe(self, recording):
        directory=self.folder/recording;audio=directory/'audio.wav'
        await self.command([self.ffmpeg(),'-nostdin','-hide_banner','-loglevel','error','-y',
            '-protocol_whitelist','file,pipe','-i',directory/'audio.upload','-map','0:a:0',
            '-vn','-ar','16000','-ac','1','-c:a','pcm_s16le','-t','301',audio],30)
        seconds=await asyncio.to_thread(self.inspect_wav,audio)
        if self.row(recording)['state']=='discarded':return
        self.update(recording,seconds=seconds)
        row=self.row(recording)
        detailed=['-ojf'] if row.get('ephemeral') else []
        await self.command([self.asset('binary'),'-m',self.asset('model'),'-f',audio,*detailed,
            '-t',str(self.config.get('threads',4)),'-l',row['language'],'-ng','-nt','-otxt',
            '-of',directory/'transcript'],max(90,min(300,seconds*2+30)))
        raw_text=(directory/'transcript.txt').read_bytes()
        invalid_encoding=False
        try:text=raw_text.decode('utf-8-sig')
        except UnicodeDecodeError:
            invalid_encoding=True;text=raw_text.decode('utf-8-sig',errors='replace')
        text=' '.join(text.split())
        if not text or text in {'[BLANK_AUDIO]','[Silence]'}:
            raise ValueError('Не удалось разобрать речь. Попробуйте сказать задание ещё раз.')
        recognition={}
        if detailed:
            try:recognition=recognition_quality(json.loads((directory/'transcript.json').read_text(encoding='utf-8-sig',errors='replace')))
            except (OSError,ValueError,TypeError):pass
        if invalid_encoding:
            if not detailed:raise ValueError('Не удалось уверенно разобрать речь. Запишите задание ещё раз.')
            recognition.update(low_confidence=True,invalid_encoding=True)
        if self.row(recording)['state']!='discarded':self.update(recording,state='ready',text=text,error='',recognition=json.dumps(recognition))

    async def run(self):
        while True:
            recording=await self.queue.get()
            self.current=recording
            try:
                if self.row(recording)['state']=='discarded':continue
                self.update(recording,state='working',error='')
                await self.transcribe(recording)
            except asyncio.CancelledError:
                if self.row(recording)['state']!='discarded':self.update(recording,state='queued')
                raise
            except (OSError,ValueError,asyncio.TimeoutError) as exc:
                if self.row(recording)['state']!='discarded':
                    message=str(exc) if isinstance(exc,ValueError) else ('Распознавание не завершилось. Повторите фразу.' if self.row(recording).get('ephemeral') else 'Распознавание не завершилось. Запись сохранена на этом ПК.')
                    self.update(recording,state='error',error=message)
            finally:
                if self.row(recording)['state']=='discarded' or self.row(recording).get('ephemeral'):self.remove_audio(recording)
                self.current=None;self.queue.task_done()

    def validate_submission(self, recording, input_id, text, sid):
        if not ID.fullmatch(recording):raise ValueError('Некорректный номер голосовой записи.')
        with self.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT * FROM recordings WHERE id=?',(recording,)).fetchone()
            if not row or row['state']!='ready' or row['text']!=text or input_id!='voice_'+recording:
                raise ValueError('Голосовое задание не совпадает с сохранённой расшифровкой.')
            if row['session_id'] and row['session_id']!=sid:
                raise ValueError('Эта запись уже отправлена в другой чат.')
            conn.execute('UPDATE recordings SET session_id=? WHERE id=?',(sid,recording))
        return VOICE_NOTE

    def accepted(self, recording, sid, receipt):
        if receipt.get('admission_id'):
            self.update(recording,session_id=sid,admission_id=receipt['admission_id'])
            self.remove_audio(recording)

    async def start(self, app):
        self.worker=asyncio.create_task(self.run(),name='personal-voice-cpu')
        with self.db() as conn:
            rows=conn.execute("SELECT id FROM recordings WHERE state IN ('queued','working') ORDER BY created").fetchall()
        for row in rows:
            if self.row(row['id']).get('ephemeral'):
                self.update(row['id'],state='discarded',error='Запись прервана при перезапуске. Скажите фразу ещё раз.');self.remove_audio(row['id']);continue
            self.update(row['id'],state='queued');await self.queue.put(row['id'])

    async def close(self, app):
        if self.worker:
            self.worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.worker

    def register(self, app):
        if not self.enabled:return
        app.router.add_get('/api/voice/status',self.get_status)
        app.router.add_post('/api/voice/transcriptions/{recording}',self.upload)
        app.router.add_get('/api/voice/transcriptions/{recording}',self.read)
        app.router.add_post('/api/voice/transcriptions/{recording}/discard',self.discard)
        app.router.add_post('/api/jarvis/transcriptions/{recording}',self.upload)
        app.router.add_get('/api/jarvis/transcriptions/{recording}',self.read)
        app.router.add_post('/api/jarvis/transcriptions/{recording}/discard',self.discard)
        app.on_startup.append(self.start);app.on_cleanup.append(self.close)
