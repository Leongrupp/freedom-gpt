"""Bounded local file editor with version checks, backups and recoverable trash."""
from __future__ import annotations
import asyncio, codecs, hashlib, json, os, pathlib, shutil, stat, threading, time, uuid
from aiohttp import web

LIMIT = 2 * 1024**2
RASTER = {'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp'}


class FileProblem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


class ArtifactWorkspace:
    def __init__(self, root, projects, stack, db, bridge):
        self.root, self.projects, self.stack = root.resolve(), projects.resolve(), stack.resolve()
        self.db, self.bridge, self.lock = db, bridge, threading.RLock()
        self.trash = self.root / 'data/file-trash'
        self.trash.mkdir(parents=True, exist_ok=True)
        with db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS artifact_trash(
                id TEXT PRIMARY KEY,path_key TEXT,original_path TEXT,stored_path TEXT,
                name TEXT,created REAL,state TEXT)''')
            conn.execute('CREATE INDEX IF NOT EXISTS artifact_trash_path ON artifact_trash(path_key,state)')
            # Complete or undo bookkeeping if the interface stopped during an atomic rename.
            for row in conn.execute("SELECT * FROM artifact_trash WHERE state IN ('pending','restoring')").fetchall():
                source, saved = pathlib.Path(row['original_path']), pathlib.Path(row['stored_path'])
                state = 'trashed' if saved.exists() else ('restored' if source.exists() else 'missing')
                conn.execute('UPDATE artifact_trash SET state=? WHERE id=?', (state, row['id']))

    @staticmethod
    def key(path):
        return os.path.normcase(os.path.abspath(path))

    def hidden(self, path):
        with self.db() as conn:
            return bool(conn.execute("SELECT 1 FROM artifact_trash WHERE path_key=? AND state IN ('pending','trashed','restoring')", (self.key(path),)).fetchone())

    def path(self, value, *, missing=False):
        path = pathlib.Path(os.path.abspath(value))
        if not path.is_relative_to(self.projects):
            raise FileProblem('Файл находится вне рабочей папки.', 403)
        # Reject junctions and symlinks, including any parent directory.
        for candidate in (path, *path.parents):
            if candidate.exists() or candidate.is_symlink():
                attrs = candidate.lstat()
                if stat.S_ISLNK(attrs.st_mode) or getattr(attrs, 'st_file_attributes', 0) & 0x400:
                    raise FileProblem('Ссылки и перенаправленные папки доступны только вне редактора.', 403)
            if candidate == self.projects:
                break
        resolved = path.resolve()
        if not resolved.is_relative_to(self.projects):
            raise FileProblem('Файл находится вне рабочей папки.', 403)
        parts = {part.casefold() for part in resolved.relative_to(self.projects).parts}
        protected = {'.git', '.venv', 'node_modules', 'runtime', '.cache', 'file-trash'}
        personal_output = any(resolved.is_relative_to(self.root / folder) for folder in ('output', 'workspaces', 'uploads'))
        if (resolved.is_relative_to(self.root) and not personal_output) or resolved.is_relative_to(self.stack) or protected & parts:
            raise FileProblem('Служебный файл приложения защищён от изменений.', 403)
        if resolved.suffix.lower() in {'.gguf', '.safetensors', '.exe', '.dll', '.sqlite', '.db', '.key', '.pem', '.pfx'} or resolved.name.lower().startswith('.env'):
            raise FileProblem('Этот тип файла защищён от изменений в чате.', 403)
        if not missing and not resolved.is_file():
            raise FileProblem('Файл не найден на диске.', 404)
        return resolved

    def row(self, fid):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM artifacts WHERE id=?', (fid,)).fetchone()
        if not row:
            raise FileProblem('Файл не найден.', 404)
        if self.hidden(row['path']):
            raise FileProblem('Файл находится в корзине.', 410)
        return dict(row)

    @staticmethod
    def version(path):
        info = path.stat()
        content = None
        if info.st_size <= LIMIT:
            with path.open('rb') as stream:
                content = stream.read(LIMIT + 1)
            if len(content) > LIMIT:
                content = None
        digest = hashlib.sha256(content).hexdigest() if content is not None else ''
        return f'{info.st_mtime_ns}:{info.st_size}:{digest}', content

    def describe(self, fid):
        row = self.row(fid)
        path = self.path(row['path'])
        revision, raw = self.version(path)
        result = {'id': fid, 'name': row['name'], 'mime': row['mime'], 'bytes': path.stat().st_size,
                  'url': '/api/artifacts/' + fid, 'revision': revision, 'editable': False,
                  'references': 1, 'preview_image': row['mime'] in RASTER}
        with self.db() as conn:
            result['references'] = sum(1 for r in conn.execute('SELECT path FROM artifacts') if self.key(r['path']) == self.key(path))
        if raw is None:
            result['reason'] = 'Для редактирования доступны текстовые файлы до 2 МБ.'
            return result
        encoding = 'utf-8-sig' if raw.startswith(codecs.BOM_UTF8) else 'utf-16' if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) else 'utf-8'
        try:
            text = raw.decode(encoding)
            if any(ord(char) < 32 and char not in '\t\n\r\f' for char in text):
                raise UnicodeError()
        except UnicodeError:
            result['reason'] = 'Двоичный файл или неподдерживаемая кодировка. Доступно скачивание.'
            return result
        result.update(text=text, editable=True, encoding=encoding, preview_image=False)
        return result

    def list(self, sid):
        with self.db() as conn:
            rows = conn.execute('SELECT * FROM artifacts WHERE session_id=? ORDER BY created', (sid,)).fetchall()
        files, trashed = [], []
        for row in rows:
            with self.db() as conn:
                saved = conn.execute("SELECT * FROM artifact_trash WHERE path_key=? AND state IN ('pending','trashed','restoring') ORDER BY created DESC LIMIT 1", (self.key(row['path']),)).fetchone()
            if saved:
                trashed.append({'id': saved['id'], 'name': row['name'], 'created': saved['created']})
                continue
            try:
                size = pathlib.Path(row['path']).stat().st_size
            except OSError:
                size = None
            files.append({'id': row['id'], 'name': row['name'], 'mime': row['mime'], 'bytes': size, 'url': '/api/artifacts/' + row['id'], 'path':row['path']})
        return files, list({item['id']: item for item in trashed}.values())

    def save(self, fid, data):
        with self.lock:
            current = self.describe(fid)
            if not current['editable']:
                raise FileProblem(current['reason'], 415)
            if data.get('revision') != current['revision']:
                raise FileProblem('Файл изменился на диске. Загрузите свежую версию перед сохранением.', 409)
            text = data.get('text')
            if not isinstance(text, str):
                raise FileProblem('Нужен текст файла.')
            row = self.row(fid)
            path = self.path(row['path'])
            original = path.read_bytes()
            encoding = current['encoding']
            # Keep BOM, byte order and original line endings.
            normalized = text.replace('\r\n', '\n')
            if '\r\n' in current['text']:
                normalized = normalized.replace('\n', '\r\n')
            if encoding == 'utf-16':
                prefix = original[:2]
                raw = prefix + normalized.encode('utf-16-le' if prefix == codecs.BOM_UTF16_LE else 'utf-16-be')
            else:
                raw = normalized.encode(encoding)
            if len(raw) > LIMIT:
                raise FileProblem('Текст превышает ограничение 2 МБ.', 413)
            if shutil.disk_usage(self.root).free < 300 * 1024**2:
                raise FileProblem('Для резервной копии недостаточно свободного места.', 507)
            backup = self.root / 'archive/file-edits' / uuid.uuid4().hex
            backup.mkdir(parents=True)
            shutil.copy2(path, backup / path.name)
            (backup / 'restore.json').write_text(json.dumps({'path': str(path), 'created': time.time()}, ensure_ascii=False), encoding='utf-8')
            pending = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.new')
            try:
                with pending.open('xb') as output:
                    output.write(raw); output.flush(); os.fsync(output.fileno())
                if self.version(self.path(row['path']))[0] != current['revision']:
                    raise FileProblem('Файл изменился на диске. Загрузите свежую версию перед сохранением.', 409)
                os.replace(pending, path)
            finally:
                if pending.exists():
                    pending.unlink()
            return self.describe(fid)

    def remove(self, fid, data):
        with self.lock:
            row = self.row(fid)
            path = self.path(row['path'])
            if self.version(path)[0] != data.get('revision'):
                raise FileProblem('Файл изменился на диске. Загрузите свежую версию перед удалением.', 409)
            identifier = uuid.uuid4().hex
            folder = self.trash / identifier
            folder.mkdir()
            target = folder / path.name
            metadata = {'id': identifier, 'original_path': str(path), 'stored_path': str(target), 'name': path.name, 'created': time.time()}
            (folder / 'restore.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            with self.db() as conn:
                conn.execute('INSERT INTO artifact_trash VALUES(?,?,?,?,?,?,?)', (identifier, self.key(path), str(path), str(target), path.name, metadata['created'], 'pending'))
            try:
                # Same volume; rename preserves bytes and never overwrites an existing target.
                os.rename(path, target)
            except OSError:
                with self.db() as conn:
                    conn.execute("UPDATE artifact_trash SET state='failed' WHERE id=?", (identifier,))
                raise
            with self.db() as conn:
                conn.execute("UPDATE artifact_trash SET state='trashed' WHERE id=?", (identifier,))
            return {'ok': True, 'trash_id': identifier}

    def restore(self, identifier):
        with self.lock:
            with self.db() as conn:
                row = conn.execute('SELECT * FROM artifact_trash WHERE id=?', (identifier,)).fetchone()
            if not row or row['state'] != 'trashed':
                raise FileProblem('Файл не найден в корзине.', 404)
            path = self.path(row['original_path'], missing=True)
            saved = pathlib.Path(row['stored_path'])
            if path.exists():
                raise FileProblem('На прежнем месте уже есть файл. Переместите его перед восстановлением.', 409)
            if not saved.resolve().is_relative_to(self.trash.resolve()) or not saved.is_file():
                raise FileProblem('Копия в корзине не найдена.', 404)
            if not path.parent.is_dir():
                raise FileProblem('Исходная папка больше не существует.', 409)
            with self.db() as conn:
                conn.execute("UPDATE artifact_trash SET state='restoring' WHERE id=?", (identifier,))
            try:
                os.rename(saved, path)
            except OSError:
                with self.db() as conn:
                    conn.execute("UPDATE artifact_trash SET state='trashed' WHERE id=?", (identifier,))
                raise
            with self.db() as conn:
                conn.execute("UPDATE artifact_trash SET state='restored' WHERE id=?", (identifier,))
            return {'ok': True}

    async def handle(self, request):
        try:
            fid = request.match_info.get('fid')
            if request.method == 'GET':
                return web.json_response(await asyncio.to_thread(self.describe, fid))
            if 'trash_id' in request.match_info:
                result = await asyncio.to_thread(self.restore, request.match_info['trash_id'])
            else:
                data = await request.json()
                result = await asyncio.to_thread(self.save if request.method == 'PUT' else self.remove, fid, data)
            await self.bridge.broadcast({'type': 'files.changed'})
            return web.json_response(result)
        except FileProblem as exc:
            return web.json_response({'error': exc.message}, status=exc.status)
        except OSError:
            return web.json_response({'error': 'Не удалось изменить файл. Проверьте доступ, свободное место и не занят ли он другой программой.'}, status=409)

    async def session_files(self, request):
        files, trash = await asyncio.to_thread(self.list, request.match_info['sid'])
        return web.json_response({'artifacts': files, 'artifact_trash': trash})

    def register(self, app):
        app.router.add_get('/api/sessions/{sid}/artifacts', self.session_files)
        app.router.add_get('/api/artifacts/{fid}/document', self.handle)
        app.router.add_put('/api/artifacts/{fid}/document', self.handle)
        app.router.add_post('/api/artifacts/{fid}/trash', self.handle)
        app.router.add_post('/api/artifact-trash/{trash_id}/restore', self.handle)
