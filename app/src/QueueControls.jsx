import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowDown, ArrowUp, Check, CornerDownRight, EyeOff, ListOrdered, LoaderCircle, MoreHorizontal, Paperclip, Pencil, Square, Trash2, X} from 'lucide-react';
import {t} from './i18n.js';
import {formatTime} from './WorkspacePanels.jsx';
import './queue-controls.css';

export function QueuePanel({items=[],notes=[],busy=false,onAction}) {
  const [working,setWorking]=useState(''),[error,setError]=useState(''),[menu,setMenu]=useState(null),[editing,setEditing]=useState(null);
  const trigger=useRef(null),popup=useRef(null),editor=useRef(null);
  const waiting=items.filter(row=>row.status==='queued'&&!row.steering);
  const order=waiting.map(row=>row.admission_id);
  const correction=busy?notes.find(note=>note.steering):null;
  const editable=editing&&waiting.some(row=>row.admission_id===editing.row.admission_id);
  useEffect(()=>{if(editing){editor.current?.focus();editor.current?.setSelectionRange(editing.text.length,editing.text.length)}},[editing?.row.admission_id]);
  function closeMenu(){setMenu(null);trigger.current?.focus()}
  useEffect(()=>{if(menu&&!items.some(row=>row.admission_id===menu.row.admission_id&&row.status==='queued'&&!row.steering))setMenu(null)},[items,menu]);
  useEffect(()=>{
    if(!menu)return;
    popup.current?.querySelector('button:not(:disabled)')?.focus();
    const close=e=>{if(e.key==='Escape'){e.preventDefault();closeMenu()}};
    document.addEventListener('keydown',close);
    return()=>document.removeEventListener('keydown',close);
  },[menu]);
  async function act(row,action){
    setMenu(null);setWorking(row.admission_id);setError('');
    try{await onAction(row,action,order)}catch(e){setError(e.message)}finally{setWorking('')}
  }
  function openMenu(event,row){
    const rect=event.currentTarget.getBoundingClientRect();trigger.current=event.currentTarget;
    setMenu({row,left:Math.max(8,Math.min(window.innerWidth-196,rect.right-188)),top:Math.max(8,rect.top-132)});
  }
  function edit(row){setMenu(null);setError('');setEditing({row,text:row.text,editId:crypto.randomUUID()})}
  async function saveEdit(asCorrection=false){
    if(!editing?.text.trim())return;
    setWorking(editing.row.admission_id);setError('');
    try{await onAction(editing.row,asCorrection?'send_correction':'edit',order,{text:editing.text.trim(),edit_id:editing.editId,expected_text:editing.row.text});setEditing(null)}catch(e){setError(e.message)}finally{setWorking('')}
  }
  if(!waiting.length&&!error&&!editing&&!correction)return null;
  return <section className="pending-strip" aria-label={t('Очередь заданий')}>
    {!!waiting.length&&<div className="pending-list" role="list">{waiting.map(row=><div className="pending-row" key={row.admission_id} role="listitem">
      <ListOrdered className="pending-marker" size={14} aria-hidden="true"/>
      <button className="pending-text" disabled={!row.controls?.includes('replace')||!!working} title={row.controls?.includes('replace')?t('Редактировать задание'):row.text} onClick={()=>edit(row)}>{row.text}</button>
      {!!row.files?.length&&<span className="pending-files" title={t('Вложения')}><Paperclip size={11}/>{row.files.length}</span>}
      <div className="pending-actions">
        {busy&&row.controls?.includes('steer')&&<button className="pending-steer" disabled={!!working} onClick={()=>act(row,'steer')} title={t('Передать как поправку текущей задаче')}><CornerDownRight size={13}/><span>{t('Скорректировать')}</span></button>}
        <button className="pending-icon" disabled={!!working} onClick={()=>act(row,'cancel')} aria-label={t('Убрать задание из очереди')+': '+row.text} title={t('Убрать из очереди')}>{working===row.admission_id?<LoaderCircle className="spin" size={14}/>:<Trash2 size={14}/>}</button>
        <button className="pending-icon" disabled={!!working} aria-haspopup="menu" aria-expanded={menu?.row.admission_id===row.admission_id} aria-label={t('Порядок задания')+': '+row.text} title={t('Порядок задания')} onClick={event=>openMenu(event,row)}><MoreHorizontal size={16}/></button>
      </div>
    </div>)}</div>}
    {editing&&<div className="pending-editor"><div className="pending-editor-heading"><Pencil size={12}/><span>{t('Редактирование задания')}</span>{!!editing.row.files?.length&&<small><Paperclip size={10}/>{t('Вложения сохранятся')}</small>}<button className="pending-icon" disabled={!!working} title={t('Отменить редактирование')} onClick={()=>setEditing(null)}><X size={13}/></button></div><textarea ref={editor} disabled={!!working} rows={3} maxLength={100000} aria-label={t('Текст задания в очереди')} value={editing.text} onChange={e=>setEditing(value=>({...value,text:e.target.value,editId:crypto.randomUUID()}))} onKeyDown={e=>{if(e.key==='Escape'){e.preventDefault();setEditing(null)}else if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();if(editable)saveEdit()}}}/><div className="pending-editor-footer"><span>{editable?t('Ctrl + Enter — сохранить'):t('Задание уже началось. Изменения можно передать как поправку.')}</span><button disabled={!!working} onClick={()=>setEditing(null)}>{t('Отмена')}</button>{editable?<button className="pending-save" disabled={!!working||!editing.text.trim()} onClick={()=>saveEdit()}>{working?<LoaderCircle size={12} className="spin"/>:<Check size={12}/>} {t('Сохранить')}</button>:busy&&!editing.row.files?.length&&<button className="pending-save" disabled={!!working||!editing.text.trim()} onClick={()=>saveEdit(true)}><CornerDownRight size={12}/>{t('Скорректировать')}</button>}</div></div>}
    {correction&&<div className="pending-correction" role="status"><CornerDownRight size={12}/><span>{t('Поправка принята')}</span><p title={correction.text}>{correction.text}</p></div>}
    {error&&<div className="pending-error" role="alert"><span>{t(error)}</span><button className="pending-icon" onClick={()=>setError('')} aria-label={t('Скрыть ошибку')}><X size={13}/></button></div>}
    {menu&&createPortal(<div className="pending-menu-layer" onMouseDown={event=>{if(event.target===event.currentTarget)closeMenu()}}><div className="pending-menu" role="menu" ref={popup} style={{left:menu.left,top:menu.top}} aria-label={t('Порядок задания')}><button role="menuitem" disabled={!!working||!menu.row.controls?.includes('replace')} onClick={()=>edit(menu.row)}><Pencil size={14}/>{t('Редактировать')}</button><button role="menuitem" disabled={!!working||order.indexOf(menu.row.admission_id)<=0} onClick={()=>act(menu.row,'up')}><ArrowUp size={14}/>{t('Выше в очереди')}</button><button role="menuitem" disabled={!!working||order.indexOf(menu.row.admission_id)>=waiting.length-1} onClick={()=>act(menu.row,'down')}><ArrowDown size={14}/>{t('Ниже в очереди')}</button></div></div>,document.body)}
  </section>;
}

export function NotesPanel({notes=[],onAction}) {
  const [working,setWorking]=useState(''),[error,setError]=useState('');
  async function act(note){setWorking(note.input_id);setError('');try{await onAction(note,note.queued?'cancel':'hide_note')}catch(e){setError(e.message)}finally{setWorking('')}}
  return <div className="notes-history"><p className="panel-intro">{t('Отправленные поправки остаются в истории чата.')}</p>{notes.map(note=><div className="notes-history-row" key={note.input_id}><div><time>{formatTime(note.created)}</time><p>{note.text}</p>{note.queued&&<small>{t('Ожидает передачи')}</small>}</div><button className="pending-icon" disabled={!!working} title={note.queued?t('Отменить ожидающую поправку'):t('Скрыть поправку из списка')} aria-label={(note.queued?t('Отменить ожидающую поправку'):t('Скрыть поправку из списка'))+': '+note.text} onClick={()=>act(note)}>{working===note.input_id?<LoaderCircle size={14} className="spin"/>:note.queued?<Trash2 size={14}/>:<EyeOff size={14}/>}</button></div>)}{!notes.length&&<p className="panel-intro">{t('Здесь пока нет поправок.')}</p>}{error&&<p className="panel-error" role="alert">{t(error)}</p>}</div>;
}

export function ComposerSendActions({busy,hasContent,canSubmit,canSteer,sending,onSend,onStop}) {
  return <>
    {busy&&hasContent&&canSteer&&<button className="composer-steer" disabled={!canSubmit||sending} title={t('Передать как поправку текущей задаче')} onClick={()=>onSend('steer')}><CornerDownRight size={14}/><span>{t('Скорректировать')}</span></button>}
    {busy&&<button className="send-button stop" title={t('Остановить ответ')} aria-label={t('Остановить ответ')} onClick={onStop}><Square size={14} fill="currentColor"/></button>}
    {(!busy||hasContent||sending)&&<button className="send-button" disabled={!canSubmit||sending} title={busy?t('Добавить в очередь'):t('Отправить сообщение')} aria-label={busy?t('Добавить в очередь'):t('Отправить сообщение')} onClick={()=>onSend('queue')}>{sending?<LoaderCircle size={18} className="spin"/>:<ArrowUp size={20}/>}</button>}
  </>;
}
