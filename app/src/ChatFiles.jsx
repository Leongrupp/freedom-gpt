import React, {useEffect, useRef, useState, useId} from 'react';
import {FileText, FolderOpen, Download, ChevronRight, Trash2, RotateCcw, Save, Copy, LoaderCircle, Check, X, Image as ImageIcon} from 'lucide-react';
import {api} from './api.js';
import {copyText} from './clipboard.js';
import {getLocale, t} from './i18n.js';
import './chat-files.css';

const size = bytes => bytes == null ? '—' : new Intl.NumberFormat(getLocale(), {maximumFractionDigits: 1}).format(bytes < 1024 ? bytes : bytes < 1024**2 ? bytes / 1024 : bytes / 1024**2) + ' ' + t(bytes < 1024 ? 'байт' : bytes < 1024**2 ? 'КБ' : 'МБ');

export function ChatFiles({files = [], trash = [], onChanged, Modal, notify}) {
  const [expanded,setExpanded] = useState(false), listId = useId();
  const [selected, setSelected] = useState(null), [trashOpen, setTrashOpen] = useState(false);
  const [restoring, setRestoring] = useState(''), [error, setError] = useState('');
  async function restore(file) {
    setRestoring(file.id); setError('');
    try {
      await api('/artifact-trash/' + file.id + '/restore', {method: 'POST', body: '{}'});
      await onChanged(); notify(t('Файл восстановлен.'));
    } catch (e) {setError(e.message)} finally {setRestoring('')}
  }
  if (!files.length && !trash.length) return null;
  return <section className={'chat-files'+(expanded?' is-open':'')} aria-label={t('Файлы этого чата')}>
    <header className="chat-files-heading"><button className="chat-files-toggle" onClick={()=>setExpanded(value=>!value)} aria-expanded={expanded} aria-controls={listId}><FolderOpen size={14}/><span>{t('Файлы этого чата')}</span><span className="chat-files-count">{files.length}</span><ChevronRight className="chat-files-chevron" size={12}/></button>{expanded&&!!trash.length&&<button className="chat-files-trash-toggle" onClick={()=>setTrashOpen(!trashOpen)} aria-expanded={trashOpen}><Trash2 size={12}/>{t('Корзина')} · {trash.length}</button>}</header>
    <div id={listId} hidden={!expanded}><div className="chat-files-list">{files.map(file=><div key={file.id} className="chat-file-row">
      <button className="chat-file-open" onClick={()=>setSelected(file)} title={t('Открыть файл') + ': ' + file.name}>
        {file.mime?.startsWith('image/') ? <ImageIcon size={16}/> : <FileText size={16}/>}
        <span className="chat-file-name">{file.name}</span><small>{size(file.bytes)}</small><ChevronRight size={12}/>
      </button><a className="chat-file-download" href={file.url} download title={t('Скачать файл')} aria-label={t('Скачать файл') + ': ' + file.name}><Download size={14}/></a>
    </div>)}</div>
    {trashOpen && !!trash.length && <div className="chat-file-trash"><p>{t('Файлы можно восстановить на прежнее место.')}</p>{trash.map(file=><div key={file.id}><FileText size={14}/><span>{file.name}</span><button onClick={()=>restore(file)} disabled={!!restoring}>{restoring===file.id?<LoaderCircle size={13} className="spin"/>:<RotateCcw size={13}/>} {t('Восстановить')}</button></div>)}</div>}
    {error && <p className="file-error" role="alert">{error}</p>}
    </div>
    {selected && <FileEditor key={selected.id} file={selected} Modal={Modal} onClose={()=>setSelected(null)} onChanged={onChanged} notify={notify} onTrashed={()=>{setSelected(null);setTrashOpen(true)}}/>}
  </section>;
}

function FileEditor({file, Modal, onClose, onChanged, notify, onTrashed}) {
  const [doc, setDoc] = useState(null), [text, setText] = useState(''), [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(''), [error, setError] = useState(''), [conflict, setConflict] = useState(false);
  const [discard, setDiscard] = useState(false), [deleting, setDeleting] = useState(false), [copied, setCopied] = useState(false);
  const draft = useRef(null), alive = useRef(true);
  const dirty = doc?.editable && text !== doc.text;
  useEffect(()=>{alive.current=true; load(); return()=>{alive.current=false}}, []);
  useEffect(()=>{
    if(!dirty) return;
    const prevent=e=>{e.preventDefault();e.returnValue=''};
    window.addEventListener('beforeunload',prevent);return()=>window.removeEventListener('beforeunload',prevent);
  },[dirty]);
  async function load() {
    setLoading(true);setError('');setConflict(false);setDiscard(false);setDeleting(false);
    try {
      const value=await api('/artifacts/'+file.id+'/document');
      if(alive.current){setDoc(value);setText(value.text??'')}
    } catch(e){if(alive.current)setError(e.message)} finally {if(alive.current)setLoading(false)}
  }
  function close(){if(pending)return;if(dirty){setDiscard(true);setDeleting(false)}else onClose()}
  async function save() {
    if(!dirty||pending)return;
    setPending('save');setError('');setConflict(false);
    try {
      const value=await api('/artifacts/'+file.id+'/document',{method:'PUT',body:JSON.stringify({revision:doc.revision,text})});
      setDoc(value);setText(value.text);setDiscard(false);notify(t('Правки сохранены. Резервная копия создана.'));
      await onChanged();
    } catch(e){setError(e.message);setConflict(e.status===409)} finally{setPending('')}
  }
  async function remove() {
    setPending('trash');setError('');
    try {
      await api('/artifacts/'+file.id+'/trash',{method:'POST',body:JSON.stringify({revision:doc.revision})});
      await onChanged();notify(t('Файл перемещён в корзину. Его можно восстановить.'));onTrashed();
    } catch(e){setError(e.message);setConflict(e.status===409);setDeleting(false)} finally{setPending('')}
  }
  async function copy() {
    try{await copyText(text);setCopied(true);setTimeout(()=>{if(alive.current)setCopied(false)},1600)}catch(e){setError(e.message)}
  }
  return <Modal wide title={file.name} subtitle={t('Локальный файл этого чата')} onClose={close}>
    <div className="file-editor">
      <div className="file-editor-toolbar"><span>{doc?size(doc.bytes):'—'}{doc?.editable && <> · {doc.encoding.toUpperCase()} · {new Intl.NumberFormat(getLocale()).format(text.split('\n').length)} {t('строк')}</>}{dirty && <i>{t('Есть правки')}</i>}</span>
        {doc?.editable && <button onClick={copy} disabled={!!pending}>{copied?<Check size={14}/>:<Copy size={14}/>} {t('Копировать')}</button>}
        <a href={file.url} download><Download size={14}/>{t('Скачать')}</a>
      </div>
      {loading?<div className="file-loading"><LoaderCircle size={22} className="spin"/>{t('Открываем файл…')}</div>:doc?.editable?<textarea ref={draft} className="file-code-editor" aria-label={t('Содержимое файла')} value={text} onChange={e=>setText(e.target.value)} spellCheck={false} disabled={!!pending} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save()}}}/>:<div className="file-readonly">{doc?.preview_image && <img src={file.url} alt={file.name}/>}<p>{t(doc?.reason||'Предпросмотр недоступен. Можно скачать файл.')}</p></div>}
      {error && <div className="file-error" role="alert">{error}{conflict && <p>{t('Ваш текст остаётся в редакторе — скопируйте его перед загрузкой свежей версии.')} <button onClick={load}>{t('Загрузить свежую версию')}</button></p>}</div>}
      {discard && <div className="file-confirm" role="alert"><span>{t('Закрыть без сохранения правок?')}</span><button onClick={()=>setDiscard(false)}>{t('Продолжить редактирование')}</button><button onClick={onClose}>{t('Закрыть без сохранения')}</button></div>}
      {deleting && <div className="file-confirm" role="alert"><span>{t('Переместить файл с диска в локальную корзину?')}{doc?.references>1 && <> {t('Этот файл используется также в других чатах.')}</>}{dirty && <> {t('Несохранённые правки не попадут в корзину.')}</>}</span><button disabled={!!pending} onClick={()=>setDeleting(false)}>{t('Отмена')}</button><button className="file-danger" disabled={!!pending} onClick={remove}>{pending==='trash'?<LoaderCircle className="spin" size={13}/>:<Trash2 size={13}/>} {t('В корзину')}</button></div>}
      <footer className="file-editor-footer"><button className="file-trash-button" disabled={!doc||loading||!!pending} onClick={()=>{setDeleting(true);setDiscard(false)}}><Trash2 size={14}/>{t('Удалить')}</button><small>{t('При сохранении создаётся резервная копия.')}</small><button onClick={close} disabled={!!pending}>{t('Закрыть')}</button>{doc?.editable && <button className="primary-button" disabled={!dirty||!!pending||loading} onClick={save}>{pending==='save'?<LoaderCircle className="spin" size={14}/>:<Save size={14}/>} {t('Сохранить')}</button>}</footer>
    </div>
  </Modal>;
}
