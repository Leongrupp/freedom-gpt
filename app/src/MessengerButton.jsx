import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Mail,X,ArrowUpRight} from 'lucide-react';
import {api} from './api.js';
import './messenger-dock.css';
export default function MessengerButton(){
 const [open,O]=useState(false),[loaded,L]=useState(false),[unread,U]=useState(0),[notice,N]=useState(null),[background,BG]=useState(()=>localStorage.getItem('freedom-messenger-background')!=='false');
 const frame=useRef(null),button=useRef(null),preferences=useRef({notifications:false}),initialTheme=useRef(document.documentElement.dataset.theme||'dark');
 const send=value=>frame.current?.contentWindow?.postMessage(value,location.origin);
 function show(uin){L(true);O(true);if(uin)setTimeout(()=>send({type:'fm-open-chat',uin}),50);N(null)}
 function close(){O(false);if(!background)L(false);button.current?.focus()}
 useEffect(()=>{send({type:'fm-visibility',open})},[open,loaded]);
 useEffect(()=>{const observer=new MutationObserver(()=>send({type:'fm-theme',theme:document.documentElement.dataset.theme||'dark'}));observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});return()=>observer.disconnect()},[]);
 useEffect(()=>{let gone=false;const load=()=>api('/messenger').then(s=>{if(gone)return;U(s.unread||0);if(s.signed_in&&background)L(true);if(!s.signed_in&&!open)L(false)}).catch(()=>{});load();const id=setInterval(load,10000);return()=>{gone=true;clearInterval(id)}},[open,background]);
 useEffect(()=>{const listener=e=>{if(e.origin!==location.origin||e.source!==frame.current?.contentWindow||e.data?.type!=='freedom-messenger')return;const d=e.data.event||{};
  if(d.type==='unread')U(Math.max(0,Math.min(9999,Number(d.count)||0)));
  if(d.type==='close'||d.type==='minimize')close();
  if(d.type==='preferences'){preferences.current=d;const value=d.background!==false;BG(value);localStorage.setItem('freedom-messenger-background',String(value))}
  if(d.type==='notify'){N({title:d.title||'Новое сообщение',uin:d.uin});U(v=>Math.max(v,1));if(preferences.current.notifications&&Notification.permission==='granted'){const n=new Notification(d.title||'Freedom Messenger',{body:'Новое личное сообщение',icon:'/messenger/envelope.svg'});n.onclick=()=>{window.focus();show(d.uin)}}}
 };window.addEventListener('message',listener);return()=>window.removeEventListener('message',listener)},[background]);
 useEffect(()=>{if(!notice)return;const id=setTimeout(()=>N(null),9000);return()=>clearTimeout(id)},[notice]);
 useEffect(()=>{if(!open)return;const key=e=>{if(e.key==='Escape')close()};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[open,background]);
 return <><button ref={button} type="button" className={'icon-button messenger-launch '+(open?'active ':'')+(unread?'has-unread':'')} aria-label={unread?'Мессенджер, непрочитанных: '+unread:'Мессенджер'} title={unread?'Мессенджер · '+unread+' новых':'Мессенджер'} onClick={()=>open?close():show()}><Mail size={18}/>{unread>0&&<b className="messenger-counter">{unread>99?'99+':unread}</b>}</button>{loaded&&createPortal(<section className={'messenger-overlay '+(open?'is-open':'is-closed')} aria-hidden={!open} inert={!open}><div className="messenger-scrim" onClick={close}/><section className="messenger-shell" role="dialog" aria-label="Мессенджер Freedom" aria-modal={open}><header><span className="messenger-shell-icon"><Mail size={19}/></span><div><h2>Мессенджер</h2><small>Freedom · ваши люди на связи</small></div><button className="icon-button" type="button" aria-label="Закрыть мессенджер" onClick={close}><X size={18}/></button></header><iframe ref={frame} src={'/api/messenger/frame?theme='+initialTheme.current} title="Freedom Messenger" allow="autoplay" tabIndex={open?0:-1} onLoad={()=>{send({type:'fm-visibility',open});send({type:'fm-theme',theme:document.documentElement.dataset.theme||'dark'})}}/></section></section>,document.body)}{notice&&createPortal(<aside className="messenger-notice" role="status"><Mail size={20}/><button onClick={()=>show(notice.uin)}><small>НОВОЕ СООБЩЕНИЕ</small><strong>{notice.title}</strong><span>Открыть переписку <ArrowUpRight size={12}/></span></button><button className="icon-button" aria-label="Скрыть уведомление" onClick={()=>N(null)}><X size={14}/></button></aside>,document.body)}</>
}
