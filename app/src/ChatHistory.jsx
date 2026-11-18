import React,{useCallback,useEffect,useRef,useState} from 'react';
import {ArrowDown,ArrowUp,Bookmark,Check,ChevronRight,Clock3,Search,Terminal} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
import {formatTime} from './WorkspacePanels.jsx';
import './chat-history.css';
import {messageKey,mergeHistory} from './historyState.js';
export {messageKey} from './historyState.js';
export function useChatHistory(sid,snapshot,scroll,autoScroll){
 const[state,setState]=useState(null),[error,setError]=useState(''),[working,setWorking]=useState(false),[highlight,setHighlight]=useState(''),[bookmarkRevision,bump]=useState(0);
 const current=useRef(sid),stateRef=useRef(null),request=useRef(0),paging=useRef(false);current.current=sid;stateRef.current=state;
 useEffect(()=>{request.current++;setState(null);setError('');setHighlight('');setWorking(false);paging.current=false},[sid]);
 const refresh=useCallback(async()=>{
  if(!sid||paging.current)return;const ticket=++request.current,opening=stateRef.current?.sid!==sid;
  try{const page=await api('/sessions/'+sid+'/history');if(current.current!==sid||ticket!==request.current)return;
   setState(old=>old?.sid===sid&&old.has_newer?{...old,total:page.total}:old?.sid===sid?{...page,sid,messages:mergeHistory(old.messages,page.messages),first:old.first||page.first,has_older:old.has_older}:{...page,sid});setError('');
   if(opening)requestAnimationFrame(()=>requestAnimationFrame(()=>{if(current.current===sid&&scroll.current){autoScroll.current=true;scroll.current.scrollTo({top:scroll.current.scrollHeight,behavior:'instant'})}}));
  }catch(e){if(current.current===sid)setError(e.message)}
 },[sid]);
 useEffect(()=>{if(snapshot?.messages)refresh()},[sid,snapshot?.messages,refresh]);
 async function load(kind,uid){
  if(!sid||paging.current)return;paging.current=true;setWorking(true);autoScroll.current=false;const ticket=++request.current;
  const height=scroll.current?.scrollHeight||0,top=scroll.current?.scrollTop||0;
  try{
   const suffix=kind==='older'?'?before='+stateRef.current.first:kind==='around'?'?around='+encodeURIComponent(uid):'';
   const page=await api('/sessions/'+sid+'/history'+suffix);
   if(current.current!==sid||ticket!==request.current)return;
   setState(old=>kind==='older'&&old?.sid===sid?{...old,messages:mergeHistory(page.messages,old.messages),first:page.first,has_older:page.has_older,total:page.total}:{...page,sid});setError('');setHighlight(uid||'');
   requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(current.current!==sid||!scroll.current)return;
    if(kind==='older')scroll.current.scrollTo({top:top+scroll.current.scrollHeight-height,behavior:'instant'});
    else if(uid){const target=document.getElementById('history-message-'+uid);target?.scrollIntoView({behavior:'instant',block:target.offsetHeight>scroll.current.clientHeight*.75?'start':'center'})}
    else{autoScroll.current=true;scroll.current.scrollTo({top:scroll.current.scrollHeight,behavior:'instant'})}
   }));
  }catch(e){if(current.current===sid)setError(e.message)}finally{if(current.current===sid){paging.current=false;setWorking(false)}}
 }
 async function bookmark(message){
  const uid=messageKey(message);if(!sid||!uid)return;
  try{const result=await api('/sessions/'+sid+'/history/bookmark',{method:'POST',body:JSON.stringify({uid,enabled:!message.bookmarked})});
   if(current.current!==sid)return;setState(old=>old?.sid===sid?{...old,messages:old.messages.map(m=>messageKey(m)===uid?{...m,bookmarked:result.bookmarked}:m)}:old);bump(n=>n+1);setError('');
  }catch(e){setError(e.message)}
 }
 const page=state?.sid===sid?state:null;
 return {page,messages:page?.messages,error,working,highlight,bookmarkRevision,bookmark,older:()=>load('older'),jump:uid=>load('around',uid),latest:()=>load('latest')};
}

export function HistoryPaging({history}){
 return <div className="history-paging">
  {history.page?.has_older&&<button type="button" disabled={history.working} onClick={history.older}><ArrowUp size={13}/>{t(history.working?'Загружаем…':'Предыдущие сообщения')}</button>}
  {history.page&&<span>{history.page.total} {t('сообщений сохранено')}</span>}
  {history.page?.has_newer&&<button type="button" disabled={history.working} onClick={history.latest}><ArrowDown size={13}/>{t('К последним сообщениям')}</button>}
  {history.error&&<span role="alert">{history.error}</span>}
 </div>;
}

export function BookmarkMessage({message,onClick}){
 if(!messageKey(message))return null;
 return <button type="button" className={'icon-text history-bookmark '+(message.bookmarked?'is-saved':'')} title={t(message.bookmarked?'Убрать закладку':'Добавить закладку')} aria-label={t(message.bookmarked?'Убрать закладку':'Добавить закладку')} aria-pressed={!!message.bookmarked} onClick={onClick}><Bookmark size={14}/></button>;
}

function show(value){return typeof value==='string'?value:JSON.stringify(value,null,2)}
export function HistoryTool({message,messages}){
 const index=messages.indexOf(message);let call;
 for(let i=index-1;i>=0;i--){if(messages[i].role==='user')break;call=messages[i].tool_calls?.find(c=>(messages[i].tool_call_uids?.[c.id]&&messages[i].tool_call_uids[c.id]===message.tool_call_uid)||c.id===message.tool_call_id);if(call)break}
 return <details className="tool-record history-tool" id={'history-message-'+messageKey(message)}><summary><Terminal size={13}/><span>{message.tool_name||call?.function?.name||t('Результат инструмента')}</span><time>{formatTime(message.timestamp)}</time><ChevronRight size={13}/></summary>
 {call?.function?.arguments&&<div><small>{t('Команда / код')}</small><pre tabIndex={0}>{show(call.function.arguments)}</pre></div>}
 <div><small>{t('Результат')}</small><pre tabIndex={0}>{show(message.content)}</pre></div>
 </details>;
}

const eventLabels={'message.start':'Начало работы','message.complete':'Завершение шага','tool.start':'Запуск инструмента','tool.complete':'Результат инструмента','approval.request':'Запрос подтверждения','approval.settled':'Подтверждение получено','clarify.request':'Уточнение','clarify.settled':'Уточнение получено'};
export function ChatHistoryPanel({sid,history,onClose}){
 const[tab,setTab]=useState('search'),[query,setQuery]=useState(''),[day,setDay]=useState(''),[result,setResult]=useState(null),[events,setEvents]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let closed=false;setBusy(true);setError('');const timer=setTimeout(async()=>{
  try{
   if(tab==='events'){
    const data=await api('/sessions/'+sid+'/history/events');if(!closed)setEvents(data);
   }else{
    const params=new URLSearchParams({q:query,limit:'50'});if(tab==='bookmarks')params.set('bookmarks','1');
    if(day){const start=new Date(day+'T00:00:00'),end=new Date(start);end.setDate(end.getDate()+1);params.set('from',String(start.getTime()/1000));params.set('to',String(end.getTime()/1000))}
    const data=await api('/sessions/'+sid+'/history?'+params);if(!closed)setResult(data);
   }
  }catch(e){if(!closed)setError(e.message)}finally{if(!closed)setBusy(false)}
 },200);return()=>{closed=true;clearTimeout(timer)}},[sid,tab,query,day,history.bookmarkRevision]);
 async function olderEvents(){setBusy(true);try{const data=await api('/sessions/'+sid+'/history/events?before='+events.events.at(-1).id);setEvents(old=>({...data,events:[...old.events,...data.events]}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <div className="chat-history-panel">
  <p className="history-explainer">{t('Переписка хранится на диске отдельно от рабочего контекста модели. Сжатие контекста не удаляет этот архив.')}</p>
  <nav aria-label={t('Разделы истории')}>{[['search','Переписка'],['bookmarks','Закладки'],['events','Ход работы']].map(([key,label])=><button type="button" aria-pressed={tab===key} className={tab===key?'selected':''} key={key} onClick={()=>setTab(key)}>{t(label)}</button>)}</nav>
  {tab!=='events'&&<div className="history-filters"><label><Search size={14}/><input autoFocus placeholder={t('Найти в вопросах, ответах и командах')} value={query} onChange={e=>setQuery(e.target.value)}/></label><input type="date" aria-label={t('Дата сообщения')} value={day} onChange={e=>setDay(e.target.value)}/>{day&&<button type="button" onClick={()=>setDay('')}>{t('Сбросить дату')}</button>}</div>}
  {error&&<p role="alert" className="panel-error">{error}</p>}
  {busy&&<p className="history-empty" role="status">{t('Загружаем…')}</p>}
  {tab==='events'?<>
   <p className="history-explainer">{t('Журнал событий ведётся с этого обновления. Более ранние команды и результаты доступны в самой переписке.')}</p>
   {(events?.events||[]).map(event=><details className="history-event" key={event.id}><summary><Clock3 size={13}/><span>{t(eventLabels[event.kind]||event.kind)}{event.body.tool_name||event.body.name?' · '+(event.body.tool_name||event.body.name):''}</span><time>{formatTime(event.stamp)}</time><ChevronRight size={13}/></summary><pre tabIndex={0}>{show(event.body)}</pre></details>)}
   {!busy&&!events?.events?.length&&<p className="history-empty">{t('Новые действия агента появятся здесь автоматически.')}</p>}
   {events?.has_older&&<button type="button" className="history-more" disabled={busy} onClick={olderEvents}>{t('Более ранние действия')}</button>}
  </>:<div className="history-results">{(result?.results||[]).map(row=><button type="button" disabled={history.working||busy} key={row.uid} onClick={()=>{history.jump(row.uid);onClose()}}><span className="history-result-heading"><strong>{row.role==='user'?t('Вы'):row.role==='tool'?t('Инструмент'):'Freedom GPT'}</strong><time>{formatTime(row.timestamp)}</time>{row.bookmarked&&<Bookmark size={12}/>}</span><span>{row.preview||t('Вызов инструмента')}</span><ChevronRight size={14}/></button>)}
   {!busy&&!result?.results?.length&&<p className="history-empty">{t(tab==='bookmarks'?'Закладок пока нет. Нажмите значок закладки под нужным сообщением.':'Совпадений не найдено.')}</p>}
   {result?.more&&<p className="history-empty">{t('Показаны первые 50 совпадений. Уточните запрос или дату.')}</p>}
  </div>}
 </div>;
}
