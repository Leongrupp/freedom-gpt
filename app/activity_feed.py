"""Bounded, in-memory display of this user's model output and observable tool activity."""
import copy,json,time,uuid
from collections import OrderedDict

KINDS={'message.start','message.delta','message.complete','tool.generating','tool.start','tool.complete',
       'reasoning.delta','reasoning.available','approval.request','approval.settled','clarify.request','clarify.settled'}
MAX_TEXT=100_000

def tool_failed(payload):
    result=payload.get('result')
    if isinstance(result,str):
        try:result=json.loads(result)
        except (ValueError,TypeError):result={}
    result=result if isinstance(result,dict) else {}
    return bool(payload.get('failed') or payload.get('success') is False or result.get('error')
                or result.get('success') is False or result.get('exit_code') not in (None,0))

class ActivityFeed:
    def __init__(self):
        self.sessions=OrderedDict();self.epoch=uuid.uuid4().hex

    def ensure(self,sid):
        if sid not in self.sessions:
            self.sessions[sid]={'epoch':self.epoch,'revision':0,'started':None,'finished':None,'active':False,
                                'events':[],'reasoning':'','reasoning_truncated':False,'streaming_reasoning':False}
        self.sessions.move_to_end(sid)
        # Retain running work; evict only finished, older displays.
        if len(self.sessions)>40:
            for key,value in list(self.sessions.items()):
                if key!=sid and not value['active']:
                    del self.sessions[key]
                    if len(self.sessions)<=40:break
        return self.sessions[sid]

    def adopt(self,sid,live):
        s=self.ensure(sid);now=time.time()
        s.update(active=True,started=live.get('started_at') or now,updated=now,revision=s['revision']+1)
        s['events']=[{'kind':'restored','tool':None,'status':'done','at':now,'finished':now},
                     {'kind':'tool' if live.get('tool') else 'model','tool':live.get('tool'),'status':'active','at':now}]

    def record(self,sid,kind,frame):
        if kind not in KINDS:return
        p=frame.get('payload') or {};s=self.ensure(sid);now=time.time()
        if kind=='message.complete' and frame.get('execution_generation') is None and p.get('outcome') in {'cancelled','steered'}:return
        if kind=='message.start':
            revision=s['revision'];s.update(started=now,finished=None,active=True,events=[],reasoning='',reasoning_truncated=False,streaming_reasoning=False,revision=revision)
        s['revision']+=1;s['updated']=now
        def phase(code,tool=None,status='active'):
            rows=s['events']
            if rows and rows[-1]['kind']==code and rows[-1].get('tool')==tool and rows[-1]['status']==status:return
            if rows and rows[-1]['status']=='active':rows[-1].update(status='done',finished=now)
            rows.append({'kind':code,'tool':tool,'status':status,'at':now,**({'finished':now} if status!='active' else {})})
            s['events']=rows[-80:]
        if kind=='message.start':phase('model')
        elif kind.startswith('reasoning.'):
            s['active']=True
            value=p.get('text') or p.get('delta') or ''
            if not isinstance(value,str) or not value:return
            # A completed reasoning summary can repeat the streamed segment.
            if kind=='reasoning.available' and s['streaming_reasoning']:return
            if not s['events'] or s['events'][-1]['kind']!='reasoning':
                if s['reasoning']:s['reasoning']+='\n\n'
                phase('reasoning')
            if kind=='reasoning.delta':s['streaming_reasoning']=True
            s['reasoning']+=value
            if len(s['reasoning'])>MAX_TEXT:s['reasoning']=s['reasoning'][-MAX_TEXT:];s['reasoning_truncated']=True
        elif kind=='message.delta':
            s['active']=True;phase('writing')
        elif kind in {'tool.generating','tool.start'}:
            name=str(p.get('tool_name') or p.get('name') or 'tool')[:80]
            if kind=='tool.start' and s['events'] and s['events'][-1]['kind']=='preparing' and s['events'][-1].get('tool')==name:
                s['events'][-1].update(kind='tool',at=now,status='active')
            else:phase('tool' if kind=='tool.start' else 'preparing',name)
            s['active']=True;s['streaming_reasoning']=False
        elif kind=='tool.complete':
            for row in reversed(s['events']):
                if row['kind'] in {'tool','preparing'} and row['status']=='active':
                    row.update(status='error' if tool_failed(p) else 'done',finished=now);break
            phase('model');s['streaming_reasoning']=False
        elif kind=='approval.request':phase('approval')
        elif kind=='clarify.request':phase('clarify')
        elif kind in {'approval.settled','clarify.settled'}:phase('model')
        elif kind=='message.complete':
            outcome=p.get('outcome')
            phase('cancelled' if outcome in {'cancelled','steered'} else 'failed' if outcome in {'failed','error'} else 'finished',status='error' if outcome in {'failed','error'} else 'done')
            s.update(active=False,finished=now,streaming_reasoning=False)

    def snapshot(self,sid):
        s=self.sessions.get(sid)
        if not s:return None
        return copy.deepcopy(s)

    def stamp(self,sid):
        s=self.sessions.get(sid)
        return {'activity_revision':s['revision'],'activity_epoch':self.epoch} if s else {}
