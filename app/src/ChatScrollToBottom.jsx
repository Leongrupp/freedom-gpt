import React,{useEffect,useState} from 'react';
import {ArrowDown} from 'lucide-react';
import {t} from './i18n.js';
import './chat-scroll.css';

export default function ChatScrollToBottom({scroll,autoScroll,sid,hidden,history}){
 const [visible,setVisible]=useState(false);
 const hasNewer=!!history.page?.has_newer;
 useEffect(()=>{
  const el=scroll.current;
  if(!el||!sid||hidden){setVisible(false);return}
  const update=()=>setVisible(hasNewer||el.scrollHeight-el.scrollTop-el.clientHeight>120);
  update();el.addEventListener('scroll',update,{passive:true});
  const observer=new ResizeObserver(update);observer.observe(el);
  for(const child of el.children)observer.observe(child);
  return()=>{el.removeEventListener('scroll',update);observer.disconnect()};
 },[scroll,sid,hidden,hasNewer,history.messages]);
 if(!visible||!sid||hidden)return null;
 function jump(){
  if(hasNewer){history.latest();return}
  autoScroll.current=true;
  scroll.current?.scrollTo({top:scroll.current.scrollHeight,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 }
 return <div className="chat-jump-anchor"><button type="button" className="chat-jump-bottom" aria-label={t('К последним сообщениям')} title={t('К последним сообщениям')} disabled={history.working} onClick={jump}><ArrowDown size={18} strokeWidth={1.7}/></button></div>;
}
