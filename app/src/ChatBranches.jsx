import React,{useRef,useState} from 'react';
import {GitBranch,ArrowUpRight,Folder,LoaderCircle} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
import './chat-branches.css';

export function BranchDialog({source,onCreated,onCancel,onBusy}){
 const storage='freedom-branch-intent:'+source.id;
 const restored=useRef(null);
 if(!restored.current){
  let saved=null;try{saved=JSON.parse(localStorage.getItem(storage)||'null')}catch{}
  restored.current=saved?.request_id&&typeof saved.title==='string'?saved:{request_id:crypto.randomUUID(),title:(source.title.slice(0,130)+t(' · ветка')),pending:false};
 }
 const[title,setTitle]=useState(restored.current.title),[sealed,setSealed]=useState(!!restored.current.pending),[working,setWorking]=useState(false),[error,setError]=useState('');
 async function create(e){
  e.preventDefault();if(working)return;setWorking(true);onBusy(true);setError('');
  try{
   const intent={request_id:restored.current.request_id,title:sealed?restored.current.title:title.trim(),pending:true};
   // Keep the exact intent across a lost response, closed window or app reload.
   localStorage.setItem(storage,JSON.stringify(intent));restored.current=intent;setSealed(true);
   const result=await api('/sessions/'+source.id+'/branch',{method:'POST',body:JSON.stringify(intent)});
   localStorage.removeItem(storage);await onCreated(result);
  }catch(e){
   if(e.code==='branch_refused'){
    localStorage.removeItem(storage);restored.current={request_id:crypto.randomUUID(),title,pending:false};setSealed(false);
   }
   setError(e.message);
  }finally{setWorking(false);onBusy(false)}
 }
 return <form className="branch-dialog" onSubmit={create}>
  <div className="branch-source"><GitBranch size={19}/><div><span>{t('На основе чата')}</span><strong>{source.title}</strong></div></div>
  <p>{t('Текущая история и выбранная модель перейдут в новый чат. Дальше в каждой ветке будет своя переписка и очередь заданий.')}</p>
  <label>{t('Название ветки')}<input className="full-input" aria-label={t('Название ветки')} autoFocus value={title} disabled={sealed||working} onChange={e=>setTitle(e.target.value)} maxLength={160}/></label>
  <div className="branch-folder-note"><Folder size={13}/><span>{t('Папка проекта и файлы общие. Активная цель и задания из очереди не переносятся.')}</span></div>
  {sealed&&!working&&<p className="muted-copy">{t('Повторная отправка проверит тот же запрос и не создаст вторую ветку.')}</p>}
  {error&&<p role="alert" className="panel-error">{t(error)}</p>}
  <div className="modal-buttons"><button type="button" disabled={working} onClick={onCancel}>{t('Отмена')}</button><button className="primary-button" type="submit" disabled={working||!title.trim()}>{working?<LoaderCircle size={14} className="spin"/>:<GitBranch size={14}/>} {working?t('Создаём ветку…'):t('Создать ветку')}</button></div>
 </form>;
}

export function BranchOrigin({branch,onOpen}){
 if(!branch)return null;
 return <div className="chat-branch-origin"><GitBranch size={12}/><span>{t('Ветка чата')}</span><button onClick={()=>onOpen(branch.parent_id)} title={branch.parent_title}>{branch.parent_title}<ArrowUpRight size={12}/></button></div>;
}
