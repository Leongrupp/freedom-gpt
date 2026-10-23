"""User-selected context windows and independent, session-scoped reasoning effort."""
import asyncio
import pathlib
import re
import json
import sqlite3
import time
import uuid
from aiohttp import web
import bootstrap
from bootstrap import ROOT, STACK, config, read, write
from platform_support import file_lock

PREFERENCES=ROOT/'data/context-preferences.json'

class ContextModes:
    def __init__(self, performance, library, bridge, cloud, workspace, db):
        self.performance,self.library,self.bridge,self.cloud,self.workspace,self.db=performance,library,bridge,cloud,workspace,db
        performance.context_modes=self
        with db() as conn:
            if 'reasoning' not in {r['name'] for r in conn.execute('PRAGMA table_info(workspace_preferences)')}:
                conn.execute('ALTER TABLE workspace_preferences ADD COLUMN reasoning TEXT')

    def effort(self,sid):
        return self.workspace.preferences(sid).get('reasoning') or 'low'

    def durable_context(self,sid):
        # Read only the context field from the native owner's durable policy.
        # Cold session.info/stats intentionally omit it until an agent is built.
        with sqlite3.connect('file:'+(bootstrap.HOME/'state.db').as_posix()+'?mode=ro',uri=True,timeout=3) as conn:
            row=conn.execute('SELECT value FROM state_meta WHERE key=?',('gateway.local_policy.v1:'+sid,)).fetchone()
        if row:
            return json.loads(json.loads(row[0])['policy']['config_json']).get('model',{}).get('context_length')

    def status(self,sid=None):
        cfg=read(STACK/'server-settings.json',{});item=self.library.model(cfg.get('catalog_id'))
        native=self.library.native_context(item) if item else int(cfg.get('native_context') or cfg.get('context') or 65536)
        choices=sorted({min(native,n) for n in [65536,131072,262144] if min(native,n)>0})
        if native>262144:choices.append(native)
        preferences=read(PREFERENCES,{})
        current=int(cfg.get('context') or 65536)
        available=bool(item and not config().get('external_url'))
        template=str(self.library.metadata(item).get('tokenizer.chat_template') or '') if item else ''
        levels=['none']
        if 'reasoning_effort' in template:levels+=['low','medium','xhigh' if 'xhigh' in template else 'high']
        elif 'enable_thinking' in template:levels+=['low']
        return {'available':available,'model':(item or {}).get('name'),'model_id':cfg.get('catalog_id'),
          'context':current,'native_context':native,'choices':choices,'performance':self.performance.status(),
          'reasoning':self.effort(sid) if sid else 'low','reasoning_levels':levels,
          'selection':preferences.get(cfg.get('catalog_id')),'placement':cfg.get('ngl'),
          'gpu_only':cfg.get('ngl')=='all','global_context':True}

    def request(self,value,sid):
        status=self.status(sid)
        if not status['available']:raise ValueError('Выбор контекста доступен для управляемой локальной модели.')
        if type(value) is not int or value not in status['choices']:raise ValueError('Выберите объём в пределах установленной модели.')
        if self.performance.phase not in {'ready','error','waiting'}:raise ValueError('Дождитесь текущей настройки двигателя.')
        if self.performance.pending is not None:raise ValueError('Уже запланировано изменение. Сначала отмените его.')
        if value==status['context']:return self.status(sid)
        self.performance.pending={'context':value,'sid':sid,'model_id':status['model_id']}
        self.performance.phase,self.performance.message='waiting',''
        self.performance.cancel.clear()
        return self.status(sid)

    def apply(self,target):
        perf=self.performance;before=read(STACK/'server-settings.json',{})
        if before.get('catalog_id')!=target['model_id']:raise ValueError('Модель уже изменилась. Выберите контекст заново.')
        item=self.library.model(target['model_id']);value=target['context']
        old_app=config();old_preferences=read(PREFERENCES,{})
        previous_activation=self.library.activation
        cfg=dict(before,context=value,context_mode='auto',context_verified=True,fit_min_context=value,
                 fit_margin_mb=2048,ngl='auto',batch_size=512,ubatch_size=256,performance_mode='balanced',reasoning_budget=-1)
        cfg.pop('performance_key',None)
        hardware=read(ROOT/'data/hardware.json',{})
        device=[before.get('backend'),hardware.get('ram_gb'),[[g.get('name'),g.get('vram_gb')] for g in hardware.get('gpus',[])]]
        cfg['threads']=int(hardware.get('physical_cores') or before.get('threads') or 4)
        verified=read(ROOT/'data/model-context-profiles.json',{}).get(item['id'],{})
        prefer_turbo=before.get('performance_mode')=='turbo' or old_preferences.get(item['id'],{}).get('prefer_turbo',False)
        if verified.get('device')==device and verified.get('context')==value:
            cfg.update(ngl=verified['ngl'],context_mode='verified')
            key=perf.identity(cfg);cached=read(ROOT/'data/performance-profiles.json',{}).get(key,{})
            if prefer_turbo and cached.get('turbo'):
                cfg.update(cached['turbo']);cfg.update(performance_key=key,performance_mode='turbo',reasoning_budget=-1)
        with self.library.transition,file_lock(STACK/'.tmp/private-model-switch.lock'):
            self.library.activation={'id':item['id'],'state':'loading'}
            write(ROOT/'archive/context-settings'/f'{time.time_ns()}.json',{'engine':before,'application':old_app})
            write(ROOT/'data/performance-recovery.json',{'engine':before,'application':old_app,'context_preferences':old_preferences,
                  'key':before.get('performance_key') or 'context-recovery','created':time.time()})
            try:
                perf.phase,perf.message='applying','Подбираем размещение модели в памяти…'
                perf.restart(cfg);perf.check_cancel()
                # Record the actual offload. Keep the exact selected context on recovery.
                marker=STACK/'.tmp/current-server-log.txt'
                path=pathlib.Path(marker.read_text(encoding='utf-8-sig').strip()).resolve()
                if not path.is_relative_to((STACK/'logs').resolve()):raise ValueError('Не подтверждён журнал двигателя.')
                with path.open('rb') as log:text=log.read(150000).decode('utf8','replace')
                matches=re.findall(r'offloaded (\d+)/(\d+) layers to GPU',text)
                if matches:
                    loaded,total=map(int,matches[-1]);cfg['ngl']='all' if loaded==total else str(loaded)
                cfg.update(context_mode='selected',context_verified=True)
                self.library.record_context(item,cfg)
                own=config();own['external_context']=value;write(ROOT/'data/settings.json',own)
                preferences=read(PREFERENCES,{});preferences[item['id']]={'context':value,'ngl':cfg['ngl'],'device':device,'prefer_turbo':prefer_turbo,'updated':time.time()}
                write(PREFERENCES,preferences)
                write(ROOT/'output/context-modes'/f'{value}.json',{'context':value,'native_context':cfg.get('native_context'),
                  'placement':cfg['ngl'],'ready':True,'settings':cfg})
                write(ROOT/'data/performance-recovery.json',{})
            except Exception:
                perf.phase='restoring';perf.restart(before);write(ROOT/'data/settings.json',old_app);write(PREFERENCES,old_preferences)
                self.library.record_context(item,before)
                write(ROOT/'data/performance-recovery.json',{})
                raise
            finally:self.library.activation=previous_activation

    async def ensure_context(self,sid,snapshot=None):
        snapshot=snapshot or await self.bridge.resume(sid)
        info=snapshot.get('info') or {};model=info.get('model') or ''
        local=self.library.route_item(model)
        if not local and model!=bootstrap.model_id():return snapshot
        if local and self.library.active_id()!=local['id']:return snapshot
        actual=int(read(STACK/'server-settings.json',{}).get('context') or 65536)
        # Cold sessions expose the frozen policy pin in info; warm ones also carry stats.
        stats=await self.bridge.rpc('session.stats',session_id=sid)
        known=stats.get('context_length') or await asyncio.to_thread(self.durable_context,sid) or info.get('context_length')
        if known==actual:return snapshot
        if snapshot.get('running') or snapshot.get('pending'):return snapshot
        alias=model if local else 'freedom-local-runtime'
        result=await self.bridge.rpc('session.mutate',session_id=sid,request_id=uuid.uuid4().hex,
          expected_revision=snapshot['revision'],expected_generation=snapshot['execution_generation'],operation='model',
          payload={'model':alias,'context_length':actual})
        if result.get('status')=='confirmation_required':raise ValueError(result.get('confirm_message') or 'Подтвердите смену контекста.')
        updated=await self.bridge.resume(sid)
        if (updated.get('info') or {}).get('context_length') not in (None,actual):raise ValueError('Контекст чата ещё не обновлён.')
        return updated

    async def after_apply(self,target):
        await asyncio.to_thread(self.cloud.sync_aliases)
        if target.get('sid'):await self.ensure_context(target['sid'])
        self.performance.message='Контекст обновлён. Применяется ко всем локальным чатам.'

    def register(self,app):
        async def get(request):return web.json_response(self.status(request.query.get('sid')))
        async def change(request):
            data=await request.json()
            if data.get('action')=='cancel':self.performance.request(False);return web.json_response(self.status(data.get('sid')))
            return web.json_response(self.request(data.get('context'),data.get('sid')))
        async def thinking(request):
            sid=request.match_info['sid'];data=await request.json();effort=data.get('reasoning')
            if effort not in self.status(sid)['reasoning_levels']:raise ValueError('Выберите уровень обдумывания, поддерживаемый этой моделью.')
            snapshot=await self.bridge.resume(sid)
            if snapshot.get('running') or snapshot.get('pending'):raise ValueError('Дождитесь завершения ответа и очереди.')
            await self.bridge.rpc('config.set',session_id=sid,key='reasoning',value=effort,scope='session')
            with self.db() as conn:
                conn.execute('INSERT INTO workspace_preferences(session_id,reasoning) VALUES(?,?) ON CONFLICT(session_id) DO UPDATE SET reasoning=excluded.reasoning',(sid,effort))
            return web.json_response(self.status(sid))
        app.router.add_get('/api/run-settings',get);app.router.add_post('/api/context',change)
        app.router.add_post('/api/sessions/{sid}/run-settings',thinking)
