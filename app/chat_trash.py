"""Recoverable removal from Freedom lists; native transcripts remain authority-owned."""
import asyncio,contextlib,time
from aiohttp import web


class ChatTrash:
 def __init__(self,db,bridge):
  self._db,self.bridge,self.locks=db,bridge,{}
  with self.db() as conn:conn.execute('CREATE TABLE IF NOT EXISTS chat_trash(session_id TEXT PRIMARY KEY,deleted REAL NOT NULL)')
 @contextlib.contextmanager
 def db(self):
  conn=self._db()
  try:
   with conn:yield conn
  finally:conn.close()
 def rows(self):
  with self.db() as conn:return {row[0]:row[1] for row in conn.execute('SELECT session_id,deleted FROM chat_trash')}
 def contains(self,sid):
  with self.db() as conn:return conn.execute('SELECT 1 FROM chat_trash WHERE session_id=?',(sid,)).fetchone() is not None
 def require_available(self,sid):
  if self.contains(sid):raise ValueError('Чат в корзине. Восстановите его перед новым заданием.')
 async def change(self,request):
  data=await request.json();sid=request.match_info['sid']
  if type(data.get('restore')) is not bool:raise ValueError('Укажите действие с чатом.')
  async with self.locks.setdefault(sid,asyncio.Lock()):
   if data['restore']:
    with self.db() as conn:
     conn.execute('DELETE FROM chat_trash WHERE session_id=?',(sid,))
     conn.execute('UPDATE chats SET archived=0 WHERE id=?',(sid,))
    return web.json_response({'ok':True,'deleted':False})
   if self.contains(sid):return web.json_response({'ok':True,'deleted':True})
   snap=await self.bridge.resume(sid)
   if snap.get('running') or any(p.get('status') not in {'completed','cancelled','failed','rejected'} for p in snap.get('pending',[])):
    raise ValueError('Сначала дождитесь окончания ответа и очереди или остановите их в этом чате.')
   goal=((await self.bridge.rpc('session.control.read',session_id=sid)).get('control') or {}).get('goal') or {}
   if goal.get('status')=='active':raise ValueError('Сначала приостановите активную цель этого чата.')
   workers=await self.bridge.rpc('subagent.list',session_id=sid)
   if workers.get('subagents'):raise ValueError('Сначала дождитесь помощников или остановите их в этом чате.')
   with self.db() as conn:conn.execute('INSERT OR IGNORE INTO chat_trash VALUES(?,?)',(sid,time.time()))
   return web.json_response({'ok':True,'deleted':True})
 def register(self,app):app.router.add_post('/api/sessions/{sid}/trash',self.change)
