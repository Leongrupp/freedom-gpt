import React,{useEffect,useState} from 'react';
import {Gamepad2,ExternalLink,X} from 'lucide-react';
import {api} from './api.js';
import './ArcadePanel.css';
export default function ArcadePanel({busy,onClose}){
 const [error,setError]=useState('');
 useEffect(()=>{const old=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{document.body.style.overflow=old;};},[]);
 async function openDesktop(){try{await api('/arcade/call',{method:'POST',body:JSON.stringify({method:'launch_desktop',args:[]})});}catch(e){setError(e.message);}}
 return <section className="freedom-arcade-panel" role="dialog" aria-label="Freedom Arcade — игры" aria-modal="true"><header><div className="arcade-title"><Gamepad2 size={22}/><div><strong>Freedom Arcade</strong><small>Dendy · SEGA · свои игры</small></div></div><span className={'arcade-agent-status '+(busy?'working':'')}><i/>{busy?'Агент работает в текущем чате':'Текущий чат открыт'}</span><button onClick={openDesktop}><ExternalLink size={15}/>Отдельное приложение</button><button onClick={onClose} aria-label="Вернуться в чат"><X size={19}/><span>К чату</span></button></header>{error&&<div role="alert" className="arcade-panel-error">{error}</div>}<iframe src="/arcade/?embedded=1" title="Игровая библиотека Dendy и SEGA" allow="autoplay; fullscreen; gamepad"/></section>;
}
