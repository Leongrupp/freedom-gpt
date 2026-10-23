import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Check,ChevronDown,ChevronRight,Copy,Terminal,AlertCircle} from 'lucide-react';
import {t} from './i18n.js';
import {duration,RunClock} from './WorkspacePanels.jsx';
import {copyText} from './clipboard.js';
import './live-activity.css';

const kinds=new Set(['message.start','message.delta','message.complete','tool.generating','tool.start','tool.complete',
  'approval.request','approval.settled','clarify.request','clarify.settled']);
const secret=/api[_-]?key|password|passwd|authorization|access[_-]?token|refresh[_-]?token|secret|cookie/i;
function clean(value,depth=0){
  if(depth>8)return '…';
  if(Array.isArray(value))return value.slice(0,64).map(item=>clean(item,depth+1));
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).slice(0,64).map(([key,item])=>[key,secret.test(key)?'[hidden]':clean(item,depth+1)]));
  if(typeof value==='string')return value.replace(/(Bearer\s+)[A-Za-z0-9._~+/-]+/gi,'$1[hidden]')
    .replace(/((?:api[_-]?key|password|passwd|access[_-]?token|secret|authorization|cookie)["\s]*[:=]\s*["']?)[^\s"',;}]+/gi,'$1[hidden]')
    .replace(/(https?:\/\/)[^/\s:@]+:[^/\s@]+@/g,'$1[hidden]@');
  return value;
}
function parse(value){if(typeof value==='string'){try{return JSON.parse(value)}catch{}}return value}
function display(value,limit){const safe=clean(parse(value));const text=typeof safe==='string'?safe:JSON.stringify(safe,null,2)||'';return text.slice(0,limit)+(text.length>limit?'\n…':'')}
function details(p){
  const args=parse(p.args)||{},result=parse(p.result);
  const primary=typeof args==='object'&&['command','code','script','source','patch','content'].find(key=>typeof args[key]==='string'&&args[key]);
  const metadata=primary?Object.fromEntries(Object.entries(args).filter(([key])=>key!==primary)):null;
  const input=primary?(Object.keys(metadata).length?display(metadata,2000)+'\n\n':'')+display(args[primary],12000):display(args,12000);
  return {id:String(p.tool_call_id||p.tool_id||''),tool:String(p.tool_name||p.name||'tool').slice(0,80),input,
    output:p.result==null?'':display(p.result,8000),duration:p.duration_s,
    failed:!!(p.is_error||p.failed||p.success===false||result?.error||result?.success===false||(result?.exit_code!=null&&result.exit_code!==0))};
}
function historyCalls(messages){
  const calls=new Map();
  // Only the latest user turn, not a second transcript of the whole chat.
  const lastUser=messages.findLastIndex(message=>message.role==='user');
  for(const message of messages.slice(Math.max(0,lastUser))){
    if(message.role==='assistant')for(const item of message.tool_calls||[]){
      if(item.id)calls.set(item.id,{...details({tool_call_id:item.id,name:item.function?.name,args:item.function?.arguments}),status:'active'});
    }
    if(message.role==='tool'){
      const call=calls.get(message.tool_call_id);
      if(call){const value=details({name:call.tool,result:message.content});Object.assign(call,{output:value.output,failed:value.failed,status:value.failed?'error':'done'})}
    }
  }
  return [...calls.values()].slice(-6);
}
function mergeCalls(base,incoming){const calls=new Map(base.map(call=>[call.id,call]));for(const call of incoming)calls.set(call.id,{...calls.get(call.id),...call});return [...calls.values()].slice(-6)}
const empty=()=>({revision:0,phase:'model',calls:[]});

// Passive observation only: no prompts, instructions or work are sent to the agent.
export function publishActivityFrame(frame){
  if(frame.type!=='gateway.event'||!kinds.has(frame.event_type)||!frame.session_id)return;
  const p=frame.payload||{};
  window.dispatchEvent(new CustomEvent('freedom-activity-event',{detail:{
    sid:frame.session_id,kind:frame.event_type,generation:frame.execution_generation,
    revision:frame.activity_revision,epoch:frame.activity_epoch,outcome:p.outcome,
    call:frame.event_type==='tool.start'||frame.event_type==='tool.complete'?details(p):null
  }}));
}
function applyEvent(previous,event){
  if(event.kind==='message.complete'&&event.generation==null&&['cancelled','steered'].includes(event.outcome))return previous;
  if(event.epoch===previous.epoch&&event.revision!=null&&event.revision<=previous.revision)return previous;
  const now=Date.now()/1000;
  let s={...previous,epoch:event.epoch||previous.epoch,revision:event.revision??previous.revision+1};
  if(event.kind==='message.start')return {...s,phase:'model',calls:[],started:now,finished:null};
  if(event.kind==='tool.start'||event.kind==='tool.complete'){
    const old=s.calls.find(call=>event.call.id&&call.id===event.call.id);
    const call={...event.call,id:event.call.id||old?.id||'call-'+s.revision,at:old?.at||now,
      status:event.kind==='tool.start'?'active':event.call.failed?'error':'done'};
    if(event.kind==='tool.complete')call.finished=now;
    s.calls=mergeCalls(s.calls,[call]);s.phase=event.kind==='tool.start'?'tool':'model';
  }else if(event.kind==='message.delta')s.phase='writing';
  else if(event.kind==='tool.generating')s.phase='preparing';
  else if(event.kind==='approval.request')s.phase='approval';
  else if(event.kind==='clarify.request')s.phase='clarify';
  else if(event.kind.endsWith('.settled'))s.phase='model';
  else if(event.kind==='message.complete'){s.phase='finished';s.finished=now}
  return s;
}

export function ActivityMessage({sid,activity,history=[],busy,live,tool,started,children}){
  const [feed,setFeed]=useState(empty),[open,setOpen]=useState(false),[selected,setSelected]=useState(null);
  const [copied,setCopied]=useState(false),[copyError,setCopyError]=useState('');
  const panel=useRef(null);
  const savedCalls=useMemo(()=>historyCalls(history),[history]);
  const calls=useMemo(()=>mergeCalls(savedCalls,feed.calls),[savedCalls,feed.calls]);
  useEffect(()=>{
    if(!activity)return;
    setFeed(old=>({...old,started:activity.started||old.started,finished:activity.finished,
      epoch:activity.epoch,revision:Math.max(old.epoch===activity.epoch?old.revision:0,activity.revision||0)}));
  },[activity]);
  useEffect(()=>{const receive=e=>{if(e.detail.sid===sid)setFeed(old=>applyEvent(old,e.detail))};window.addEventListener('freedom-activity-event',receive);return()=>window.removeEventListener('freedom-activity-event',receive)},[sid]);
  useEffect(()=>{if(!busy)setOpen(false);else setSelected(null)},[busy]);
  useEffect(()=>{if(!open)return;const id=requestAnimationFrame(()=>panel.current?.scrollIntoView({block:'nearest',behavior:'smooth'}));return()=>cancelAnimationFrame(id)},[open]);
  const active=busy||!!live,current=calls.find(call=>call.id===selected)||calls.at(-1);
  if(!sid||(!active&&!calls.length))return null;
  const status=tool?t('Работает с инструментом'):feed.phase==='approval'?t('Ждёт подтверждения'):feed.phase==='clarify'?t('Ждёт уточнения'):live?t('Пишет ответ'):t('Думает и пишет');
  const currentActive=active&&current?.status==='active'&&!!tool;
  async function copy(value){try{await copyText(value);setCopied(true);setCopyError('');setTimeout(()=>setCopied(false),1500)}catch(e){setCopyError(e.message)}}
  return <article className={active?'message assistant live-message':'activity-completed'} data-activity-session={sid}>
    {active&&<div className="assistant-avatar"><img src="/freedom.svg" alt=""/></div>}
    <div className="message-body">
      <div className={active?'message-byline':'activity-finished-line'}>
        {active&&'Freedom GPT'}
        <button type="button" className={'live-activity-toggle '+(active?'active':'')} aria-expanded={open} aria-controls={'activity-'+sid}
          title={t('Посмотреть команды и код')} onClick={()=>setOpen(value=>!value)}>
          {active?<i/>:<Terminal size={12}/>}<span>{active?status:t('Действия агента')}</span>{tool&&<code>{tool}</code>}{open?<ChevronDown size={12}/>:<ChevronRight size={12}/>}</button>
        {active&&<RunClock started={feed.started||started}/>}
      </div>
      {open&&<section ref={panel} className="live-activity-panel" id={'activity-'+sid} aria-label={t('Команды и код агента')}>
        <header><strong>{currentActive?t('Сейчас выполняется'):t('Последнее действие')}</strong>
          {current&&<span className="activity-call-state">{current.status==='error'?<AlertCircle size={12}/>:current.status==='done'?<Check size={12}/>:<Terminal size={12}/>}<code>{current.tool}</code>{current.duration!=null&&<time>{duration(current.duration)}</time>}</span>}
        </header>
        {current?<>
          {current.input&&<div className="activity-code"><div><span>{t('Команда / код')}</span><button type="button" onClick={()=>copy(current.input)} aria-label={t('Копировать команду или код')}>{copied?<Check size={12}/>:<Copy size={12}/>}</button></div><pre tabIndex={0}>{current.input}</pre></div>}
          {current.output?<details className="activity-result" key={current.id}><summary>{t('Результат')}<ChevronDown size={12}/></summary><pre tabIndex={0}>{current.output}</pre></details>:<p className="activity-explanation">{currentActive?t('Инструмент работает. Результат появится после выполнения.'):t('Ожидаем следующее действие агента.')}</p>}
          {calls.length>1&&<footer><span>{t('Последние действия')}</span><select aria-label={t('Выбрать действие')} value={current.id} onChange={e=>setSelected(e.target.value)}>{calls.map((call,index)=><option key={call.id} value={call.id}>{index+1}. {call.tool}</option>)}</select><button type="button" disabled={!selected} onClick={()=>setSelected(null)}>{t('Следить за текущим')}</button></footer>}
        </>:<p className="activity-explanation">{t('Агент обрабатывает запрос. Команда или код появятся здесь при запуске инструмента.')}</p>}
        {copyError&&<p className="activity-explanation" role="alert">{copyError}</p>}
      </section>}
      {children}
    </div>
  </article>;
}
