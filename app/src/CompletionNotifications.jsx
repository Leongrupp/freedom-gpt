import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Bell,Check,ChevronRight,Volume2,X} from 'lucide-react';
import {t,useLocale} from './i18n.js';
import {COMPLETION_EVENT,PREVIEW_EVENT,notificationPreferences,saveNotificationPreferences,
  watchNotificationPreferences,unlockNotificationAudio,playNotificationSound} from './completionNotifications.js';
import './completion-notifications.css';

function useNotificationPreferences(){
  const [prefs,setPrefs]=useState(notificationPreferences);
  useEffect(()=>watchNotificationPreferences(()=>setPrefs(notificationPreferences())),[]);
  return prefs;
}

export function NotificationSettings(){
  useLocale();
  const prefs=useNotificationPreferences();
  const toggle=(name,value)=>{unlockNotificationAudio();saveNotificationPreferences({[name]:value})};
  return <section className="completion-settings" aria-label={t('Уведомления')}>
    <header><span className="completion-settings-icon"><Bell size={18}/></span><div><strong>{t('Уведомления')}</strong><p>{t('Узнайте, когда агент закончил ответ.')}</p></div></header>
    <div className="completion-setting-row"><span id="completion-visual-label">{t('Уведомления об ответах')}</span>
      <button type="button" className={'toggle '+(prefs.enabled?'on':'')} role="switch" aria-checked={prefs.enabled} aria-labelledby="completion-visual-label" onClick={()=>toggle('enabled',!prefs.enabled)}><span/></button></div>
    <div className={'completion-setting-row '+(!prefs.enabled?'is-disabled':'')}><span id="completion-sound-label"><Volume2 size={14}/>{t('Короткий звук')}</span>
      <button type="button" className={'toggle '+(prefs.sound?'on':'')} role="switch" aria-checked={prefs.sound} aria-labelledby="completion-sound-label" disabled={!prefs.enabled} onClick={()=>toggle('sound',!prefs.sound)}><span/></button></div>
    <footer><small>{t('На этом устройстве, пока открыт Freedom GPT.')}</small><button type="button" className="completion-preview-button" disabled={!prefs.enabled} onClick={()=>{
      unlockNotificationAudio();window.dispatchEvent(new Event(PREVIEW_EVENT));
    }}>{t('Проверить')}</button></footer>
  </section>;
}

function CompletionCard({item,onDismiss,onOpen}){
  const [paused,setPaused]=useState(false);
  useEffect(()=>{if(paused)return;const timer=setTimeout(()=>onDismiss(item.key),9000);return()=>clearTimeout(timer)},[item.key,paused,onDismiss]);
  return <li className="completion-card" onMouseEnter={()=>setPaused(true)} onMouseLeave={()=>setPaused(false)} onFocusCapture={()=>setPaused(true)} onBlurCapture={event=>{if(!event.currentTarget.contains(event.relatedTarget))setPaused(false)}}>
    <span className="completion-ready-icon"><Check size={18}/></span>
    <button type="button" className="completion-card-open" onClick={()=>onOpen(item)}>
      <span className="completion-card-brand">Freedom GPT <i/> {item.preview?t('Предпросмотр'):t('Ответ готов')}</span>
      <strong>{item.title||t('Агент закончил ответ')}</strong>
      <span className="completion-card-action">{item.preview?t('Так выглядит уведомление о готовом ответе.'):t('Открыть чат')}{!item.preview&&<ChevronRight size={12}/>}</span>
    </button>
    <button type="button" className="completion-card-close" aria-label={t('Закрыть уведомление')} onClick={()=>onDismiss(item.key)}><X size={15}/></button>
  </li>;
}

export function CompletionNotifications({sessions,onOpen}){
  useLocale();
  const prefs=useNotificationPreferences(),[items,setItems]=useState([]);
  const current=useRef({sessions,onOpen});current.current={sessions,onOpen};
  const seen=useRef(new Set());
  const dismiss=React.useCallback(key=>setItems(value=>value.filter(item=>item.key!==key)),[]);
  useEffect(()=>{if(!prefs.enabled)setItems([])},[prefs.enabled]);
  useEffect(()=>{
    const unlock=()=>{if(notificationPreferences().enabled&&notificationPreferences().sound)unlockNotificationAudio()};
    const complete=event=>{
      const item=event.detail;if(!item?.key||seen.current.has(item.key))return;
      seen.current.add(item.key);if(seen.current.size>256)seen.current.delete(seen.current.values().next().value);
      if(!notificationPreferences().enabled)return;
      const chat=current.current.sessions?.find(chat=>chat.id===item.sid);
      setItems(value=>[...value,{...item,title:chat?.title||''}].slice(-3));
      void playNotificationSound(item.key);
    };
    const preview=()=>{
      if(!notificationPreferences().enabled)return;
      const item={key:'preview:'+Date.now(),preview:true,title:t('Агент закончил ответ')};
      setItems(value=>[...value,item].slice(-3));void playNotificationSound(item.key,{preview:true});
    };
    window.addEventListener('pointerdown',unlock,{capture:true,passive:true});
    window.addEventListener('keydown',unlock,{capture:true});
    window.addEventListener(COMPLETION_EVENT,complete);window.addEventListener(PREVIEW_EVENT,preview);
    return()=>{
      window.removeEventListener('pointerdown',unlock,true);window.removeEventListener('keydown',unlock,true);
      window.removeEventListener(COMPLETION_EVENT,complete);window.removeEventListener(PREVIEW_EVENT,preview);
    };
  },[]);
  return createPortal(<section className="completion-notifications" aria-label={t('Уведомления об ответах')} aria-live="polite" aria-relevant="additions" aria-atomic="false"><ul>{items.map(item=><CompletionCard key={item.key} item={item} onDismiss={dismiss} onOpen={item=>{dismiss(item.key);if(!item.preview)current.current.onOpen(item.sid)}}/>)}</ul></section>,document.body);
}
