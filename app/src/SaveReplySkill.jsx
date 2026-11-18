import React,{useState} from 'react';
import {BookPlus,Check,Save,LoaderCircle} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
import {replySkillTitle,replySkillName,buildReplySkill} from './replySkills.js';
import './save-reply-skill.css';

export default function SaveReplySkill({Modal,text,sessionId,messageId,files=[],onSaved}){
 const[open,setOpen]=useState(false),[title,setTitle]=useState(''),[when,setWhen]=useState(''),[content,setContent]=useState(''),[verified,setVerified]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false),[initialized,setInitialized]=useState(false);
 function show(){
  if(!initialized){const proposed=replySkillTitle(text);setTitle(proposed);setWhen(t('Для похожих задач: ')+proposed);setContent(text);setInitialized(true)}
  setError('');setOpen(true);
 }
 async function save(event){
  event.preventDefault();if(busy)return;setBusy(true);setError('');
  try{
   const name=await replySkillName(sessionId,messageId);
   const payload=buildReplySkill({title,when,content,verified,sessionId,messageId,files});
   await api('/skills',{method:'POST',body:JSON.stringify({name,...payload})});
   setSaved(true);setOpen(false);onSaved?.(t('Навык сохранён. Он доступен в разделе «Навыки и обучение».'));
  }catch(e){setError(e.message)}finally{setBusy(false)}
 }
 return <><button className={'icon-text save-reply-skill'+(saved?' is-saved':'')} type="button" onClick={show} title={t(saved?'Изменить сохранённый навык':'Сохранить решение из этого ответа для следующих задач')}>
  {saved?<Check size={14}/>:<BookPlus size={14}/>}<span>{t(saved?'Навык сохранён':'Сохранить навык')}</span>
 </button>{open&&<Modal title={t(saved?'Изменить навык':'Сохранить навык')} subtitle={t('Готовое решение для следующих задач')} onClose={()=>{if(!busy)setOpen(false)}}>
  <form className="reply-skill-form" onSubmit={save}>
   <p className="reply-skill-intro">{t('Сохраните полезное решение, чтобы агент мог найти его и использовать повторно. Название, условия и пример можно отредактировать.')}</p>
   <label>{t('Название навыка')}<input value={title} onChange={e=>setTitle(e.target.value)} maxLength={120} required/></label>
   <label>{t('Когда применять')}<input value={when} onChange={e=>setWhen(e.target.value)} maxLength={450} required placeholder={t('Например: когда нужно сделать скриншот iPhone по USB')}/></label>
   <label>{t('Инструкция и рабочий пример')}<textarea rows={10} value={content} onChange={e=>setContent(e.target.value)} required spellCheck={false}/></label>
   <label className="reply-skill-verified"><input type="checkbox" checked={verified} onChange={e=>setVerified(e.target.checked)}/><span>{t('Я проверил, что это решение работает')}</span></label>
   <p className="reply-skill-note">{t('Навык сохраняется на вашем ПК и доступен в других чатах. Упомянутые файлы остаются по исходным путям; код из ответа сохраняется в самом навыке.')}</p>
   {error&&<p className="panel-error" role="alert">{t(error)}</p>}
   <div className="reply-skill-actions"><button className="primary-button" disabled={busy}>{busy?<LoaderCircle size={14} className="spin"/>:<Save size={14}/>} {t(saved?'Сохранить изменения':'Сохранить навык')}</button><button type="button" disabled={busy} onClick={()=>setOpen(false)}>{t('Отмена')}</button></div>
  </form>
 </Modal>}</>;
}
