"""Local queue rank changes for the installed native SQLite FIFO.

This owner has no reorder RPC. Its admission sequence is the FIFO rank; identity,
payload and execution state are separate. Swap two waiting ranks in one writer
transaction, fenced by epoch and the complete expected queue. Native claim_session_input
rechecks the head identity inside its own writer transaction. A concurrent claim
therefore either wins first (this change refuses), or validates the new head.
No resubmission, native code patch, schema migration or gateway restart is needed.
"""
from __future__ import annotations
import json, os, pathlib, sqlite3, threading, time, uuid


class QueueConflict(ValueError):
    pass


class QueueOrder:
    def __init__(self, root, home):
        self.path = pathlib.Path(home) / 'state.db'
        self.audit = pathlib.Path(root) / 'logs/queue-reorders.jsonl'
        self.lock = threading.Lock()
        self.identity = None

    def _record(self, value):
        with self.audit.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
            stream.flush(); os.fsync(stream.fileno())

    def place_replacement(self, sid, previous, replacement, expected, epoch):
        """Restore an edited waiting row's relative place; never mutate a started input."""
        if not isinstance(expected,list) or previous not in expected:return False
        with self.lock:
            info=self.path.stat();identity=(info.st_dev,info.st_ino)
            if self.identity is not None and self.identity!=identity:return False
            self.identity=identity
            conn=sqlite3.connect('file:'+self.path.as_posix()+'?mode=rw',uri=True,timeout=5,isolation_level=None)
            conn.row_factory=sqlite3.Row
            try:
                conn.execute('BEGIN IMMEDIATE')
                fresh=self.path.stat()
                if (fresh.st_dev,fresh.st_ino)!=identity:return False
                owner=conn.execute('SELECT epoch FROM runtime_epoch WHERE singleton=1').fetchone()
                if not owner or owner['epoch']!=epoch:return False
                rows=conn.execute("SELECT seq,admission_id FROM session_admissions WHERE target_session_id=? AND status='queued' ORDER BY seq",(sid,)).fetchall()
                actual=[r['admission_id'] for r in rows]
                if replacement not in actual:return False
                known=[i for i in expected if i!=previous and i in actual]
                if [i for i in actual if i in known]!=known:return False
                desired=[i for i in actual if i!=replacement]
                before=[i for i in expected[:expected.index(previous)] if i in desired]
                after=[i for i in expected[expected.index(previous)+1:] if i in desired]
                index=desired.index(before[-1])+1 if before else desired.index(after[0]) if after else 0
                desired.insert(index,replacement)
                if desired==actual:return True
                scratch=min(0,conn.execute('SELECT COALESCE(MIN(seq),0) FROM session_admissions').fetchone()[0])-len(rows)-1
                for n,identifier in enumerate(actual):
                    conn.execute("UPDATE session_admissions SET seq=? WHERE admission_id=? AND target_session_id=? AND status='queued'",(scratch+n,identifier,sid))
                for rank,identifier in zip([r['seq'] for r in rows],desired):
                    conn.execute("UPDATE session_admissions SET seq=? WHERE admission_id=? AND target_session_id=? AND status='queued'",(rank,identifier,sid))
                conn.commit();return True
            finally:
                if conn.in_transaction:conn.rollback()
                conn.close()

    def move(self, sid, admission, direction, expected, epoch):
        if direction not in ('up', 'down') or not isinstance(expected, list) or len(expected) > 1000 or not all(isinstance(item, str) for item in expected):
            raise QueueConflict('Некорректный порядок очереди.')
        with self.lock:
            info = self.path.stat()
            identity = (info.st_dev, info.st_ino)
            if self.identity is not None and self.identity != identity:
                raise QueueConflict('Хранилище агента изменилось. Перезапустите панель.')
            self.identity = identity
            conn = sqlite3.connect('file:' + self.path.as_posix() + '?mode=rw', uri=True, timeout=5, isolation_level=None)
            conn.row_factory = sqlite3.Row
            operation = uuid.uuid4().hex
            try:
                conn.execute('PRAGMA foreign_keys=ON')
                conn.execute('BEGIN IMMEDIATE')
                fresh = self.path.stat()
                if (fresh.st_dev, fresh.st_ino) != identity:
                    raise QueueConflict('Хранилище агента изменилось. Обновите очередь.')
                owner = conn.execute('SELECT epoch FROM runtime_epoch WHERE singleton=1').fetchone()
                if not owner or type(epoch) is not int or owner['epoch'] != epoch:
                    raise QueueConflict('Агент переподключился. Обновите очередь.')
                columns = {r['name']: r for r in conn.execute('PRAGMA table_info(session_admissions)')}
                if not {'seq', 'admission_id', 'target_session_id', 'status', 'payload_digest'} <= columns.keys() or columns['seq']['pk'] != 1:
                    raise QueueConflict('Эта версия хранилища не поддерживает перестановку очереди.')
                rows = conn.execute("SELECT seq,admission_id FROM session_admissions WHERE target_session_id=? AND status='queued' ORDER BY seq", (sid,)).fetchall()
                actual = [r['admission_id'] for r in rows]
                if actual != expected or admission not in actual:
                    raise QueueConflict('Очередь изменилась. Она обновлена — повторите действие.')
                index = actual.index(admission)
                other = index + (-1 if direction == 'up' else 1)
                if other < 0 or other >= len(rows):
                    return {'ok': True, 'changed': False}
                first, second = rows[index], rows[other]
                scratch = min(0, conn.execute('SELECT COALESCE(MIN(seq),0) FROM session_admissions').fetchone()[0]) - 1
                # A small recovery journal contains IDs and ranks only, never prompt text.
                record = {'operation': operation, 'phase': 'prepared', 'time': time.time(), 'session_id': sid,
                          'before': [dict(first), dict(second)], 'epoch': epoch}
                self._record(record)
                for identifier, rank in ((first['admission_id'], scratch), (second['admission_id'], first['seq']), (first['admission_id'], second['seq'])):
                    changed = conn.execute("UPDATE session_admissions SET seq=? WHERE admission_id=? AND target_session_id=? AND status='queued'", (rank, identifier, sid))
                    if changed.rowcount != 1:
                        raise QueueConflict('Задание уже началось. Обновите очередь.')
                conn.commit()
                # Audit failure after commit must not turn a successful move into an ambiguous retry.
                try:
                    self._record({'operation': operation, 'phase': 'committed', 'time': time.time()})
                except OSError:
                    pass
                return {'ok': True, 'changed': True}
            finally:
                if conn.in_transaction:
                    conn.rollback()
                conn.close()
