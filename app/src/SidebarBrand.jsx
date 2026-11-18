import React,{useEffect,useState} from 'react';
import './sidebar-brand.css';

const NAME='Freedom GPT';

export default function SidebarBrand({tagline}){
 const [letters,setLetters]=useState(NAME.length),[active,setActive]=useState(false),[cycle,setCycle]=useState(0);
 useEffect(()=>{
  const preference=window.matchMedia('(prefers-reduced-motion: reduce)');
  let typing,finish;
  function clear(){clearTimeout(typing);clearTimeout(finish)}
  function play(){
   clear();
   if(preference.matches){setLetters(NAME.length);setActive(false);return}
   if(document.hidden)return;
   setLetters(0);setActive(true);setCycle(value=>value+1);
   let count=0;
   function step(){count++;setLetters(count);if(count<NAME.length)typing=setTimeout(step,85);else finish=setTimeout(()=>setActive(false),1100)}
   typing=setTimeout(step,220);
  }
  function preferenceChanged(){clear();setLetters(NAME.length);setActive(false)}
  play();const repeat=setInterval(play,60000);
  preference.addEventListener('change',preferenceChanged);
  return()=>{clear();clearInterval(repeat);preference.removeEventListener('change',preferenceChanged)};
 },[]);
 return <>
  <span className="sidebar-brand-mark" data-animating={active} data-animation-cycle={cycle} aria-hidden="true">
   <svg viewBox="0 0 64 64" fill="none"><defs><linearGradient id="sidebar-brand-gradient" x1="8" y1="3" x2="57" y2="64" gradientUnits="userSpaceOnUse"><stop stopColor="#c5b5ff"/><stop offset="1" stopColor="#947bdf"/></linearGradient></defs><rect x="1" y="1" width="62" height="62" rx="18" fill="url(#sidebar-brand-gradient)" stroke="#d4c7ff" strokeOpacity=".35"/><path d="M21 46V18h24M21 30h18" stroke="#191720" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round"/><circle cx="43" cy="44" r="4" fill="#191720"/></svg>
  </span>
  <span className="sidebar-brand-copy"><span className="sidebar-brand-name" role="img" aria-label={NAME}>
   <span className="sidebar-brand-measure" aria-hidden="true">Freedom <b>GPT</b></span>
   <span className="sidebar-brand-typed" aria-hidden="true">{NAME.slice(0,Math.min(letters,8))}<b>{letters>8?NAME.slice(8,letters):''}</b>{active&&<i/>}</span>
  </span><small className="brand-agent-word">{tagline}</small></span>
 </>;
}
