export function textOf(content){return typeof content==='string'?content:Array.isArray(content)?content.map(p=>p.text||'').join('\n'):''}
export function roomData({snapshot,live,busy,metrics,sessions,index,voice}={}){
 const messages=(snapshot?.messages||[]).filter(m=>['user','assistant'].includes(m.role)&&!['hidden','internal_notification'].includes(m.display_kind));
 const transcript=messages.slice(-30).map(m=>(m.role==='user'?'ВЫ':'FREEDOM')+'\n'+textOf(m.content)).join('\n\n');
 const last=live||textOf(messages.filter(m=>m.role==='assistant').at(-1)?.content);
 const codes=[...last.matchAll(/```[^\n]*\n([\s\S]*?)```/g)].map(m=>m[1]);
 return {voice,chat:(transcript+(live?'\n\nFREEDOM · В РАБОТЕ\n'+live:'')).trim()||'Выберите чат на экране слева.\n\nГолосовые задания используют текущий чат и его память.',
 code:codes.join('\n\n')||'Код из последнего ответа появится здесь.\n\nФайлы чата:\n'+(snapshot?.artifacts||[]).map(a=>a.name||a.path||'Файл').join('\n'),
 activity:(snapshot?.activity?.events||[]).slice(-22).map(e=>[e.status,e.tool||e.kind,e.summary||e.text||''].filter(Boolean).join(' · ')).join('\n\n')||'Пока нет действий агента.',
 state:[busy?'АГЕНТ В РАБОТЕ':'АГЕНТ ОЖИДАЕТ',voice?.enabled?'Микрофон: '+(voice.phase||'включён'):'Микрофон выключен',metrics?.gpu?.name||'GPU: нет данных','GPU: '+(metrics?.gpu?.percent??'—')+'%', 'Генерация: '+(metrics?.tokens_per_second??metrics?.speed??'—')+' ток/с','Очередь: '+(snapshot?.queue?.length||0),'Цель: '+(snapshot?.goal_state?.goal?.title||snapshot?.goal_state?.goal?.objective||'не задана')].join('\n\n'),
 sessions:(sessions||[]).slice(0,60),projects:(index?.projects||[]).slice(0,160),busy:!!busy};
}
