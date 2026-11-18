import React,{useEffect,useState} from 'react';
import {Languages,LoaderCircle} from 'lucide-react';
import {api} from './api.js';
import {t,useLocale} from './i18n.js';
import './reply-language.css';

export function ReplyLanguageSettings(){
  useLocale();
  const [mode,setMode]=useState(null),[saving,setSaving]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let closed=false;api('/reply-language').then(value=>{if(!closed)setMode(value.mode)}).catch(value=>{if(!closed)setError(value.message)});return()=>{closed=true}},[]);
  async function change(value){
    setSaving(true);setError('');
    try{setMode((await api('/reply-language',{method:'POST',body:JSON.stringify({mode:value})})).mode)}
    catch(value){setError(value.message)}finally{setSaving(false)}
  }
  return <section className="reply-language-settings" aria-label={t('Язык ответов агента')}>
    <header><Languages size={19}/><div><strong>{t('Язык ответов агента')}</strong><p>{t('Отдельно от языка интерфейса.')}</p></div>{saving&&<LoaderCircle size={15} className="spin"/>}</header>
    <label><span>{t('Отвечать мне')}</span><select aria-label={t('Язык ответов агента')} value={mode||'ru'} disabled={!mode||saving} onChange={event=>change(event.target.value)}><option value="ru">{t('Всегда по-русски')}</option><option value="auto">{t('На языке задания')}</option></select></label>
    <small>{t('Для новых сообщений во всех чатах. Код, команды и имена файлов сохраняются без перевода.')}</small>
    {error&&<p className="error-text" role="alert">{t(error)}</p>}
  </section>;
}
