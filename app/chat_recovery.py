"""Continue one interrupted chat using a newly accepted human instruction.

The native owner alone resolves an unknown receipt and closes its transcript.
The interrupted action is never resubmitted. Its waiting successors retain their
identities/payloads; the explicit new instruction is put first before unpausing.
"""
import asyncio

from queue_order import QueueConflict


def has_unknown(snapshot):
    return any(row.get('status') == 'unknown' for row in snapshot.get('pending', []))


class ChatRecovery:
    def __init__(self, bridge, queue_order):
        self.bridge, self.queue_order = bridge, queue_order
        self.locks = {}

    async def after_input(self, sid, admission_id):
        async with self.locks.setdefault(sid, asyncio.Lock()):
            for attempt in range(3):
                snapshot = await self.bridge.resume(sid)
                unknown = [row for row in snapshot.get('pending', []) if row.get('status') == 'unknown']
                if not unknown:
                    return {'recovered': False}
                waiting = [row['admission_id'] for row in snapshot.get('pending', [])
                           if row.get('status') == 'queued']
                # A read/refresh or a stale retry must never acknowledge an
                # uncertain action. A committed, still-waiting instruction is
                # required, and it belongs to this exact authorized session.
                if admission_id not in waiting:
                    raise ValueError('Новое указание не найдено в очереди. Обновите чат.')
                try:
                    await asyncio.to_thread(self._prioritize, sid, admission_id, waiting,
                                            snapshot['authority_epoch'])
                    break
                except QueueConflict:
                    if attempt == 2:
                        raise
            for row in unknown:
                await self.bridge.rpc('prompt.resolve_unknown', session_id=sid,
                    admission_id=row['admission_id'], execution_generation=row['execution_generation'])
            await self.bridge.broadcast({'type': 'queue.changed', 'session_id': sid})
            return {'recovered': True, 'resolved_count': len(unknown)}

    def _prioritize(self, sid, admission_id, waiting, epoch):
        order = list(waiting)
        while order.index(admission_id) > 0:
            index = order.index(admission_id)
            self.queue_order.move(sid, admission_id, 'up', order, epoch)
            order[index-1], order[index] = order[index], order[index-1]
