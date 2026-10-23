import React,{useEffect,useRef,useState} from 'react';
import {ArrowLeft,ArrowRight,RefreshCw,ExternalLink,X,Globe,Smartphone,Monitor,Camera,LoaderCircle,ArrowUpRight,Maximize2,Minimize2} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
import {selectPreviewState} from './preview-state.js';
import './browser-preview.css';

export class PreviewBoundary extends React.Component{
 state={failed:false,retrying:false};
 static getDerivedStateFromError(){return {failed:true}}
 componentDidCatch(error){console.error('Freedom GPT preview:',error?.message||'Preview render failed')}
 async retry(){
  this.setState({retrying:true});
  try{await this.props.onRetry?.();this.setState({failed:false,retrying:false})}
  catch{this.setState({retrying:false})}
 }
 render(){
  if(!this.state.failed)return this.props.children;
  return <aside className="browser-preview preview-recovery" aria-label={t('Просмотр сайта')}>
   <header><div><Globe size={15}/><strong>{t('Просмотр сайта')}</strong></div><button className="icon-button" aria-label={t('Свернуть панель просмотра')} onClick={this.props.onClose}><X size={16}/></button></header>
   <div className="preview-empty" role="alert"><Globe size={33}/><h3>{t('Не удалось показать окно просмотра')}</h3><p>{t('Чат и работа агента продолжаются. Попробуйте открыть просмотр ещё раз.')}</p><div className="preview-recovery-actions"><button disabled={this.state.retrying} onClick={()=>this.retry()}>{t('Повторить просмотр')}</button><button onClick={this.props.onClose}>{t('Закрыть просмотр')}</button></div></div>
  </aside>;
 }
}

export function BrowserPreview({sid,request,liveState,onState,onClose}){
 const key=sid||'workspace';
 const[state,setState]=useState(null),[address,setAddress]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const[expanded,setExpanded]=useState(false),[stageSize,setStageSize]=useState({width:600,height:700}),[screenshot,setScreenshot]=useState(null);
 const pending=useRef(false),alive=useRef(true),stage=useRef(null),image=useRef(null),wheel=useRef(null),editing=useRef(false),typing=useRef(''),typeTimer=useRef(null),scrollAmount=useRef(0),actions=useRef(Promise.resolve());
 function adopt(next){
  if(!next||typeof next!=='object'||Array.isArray(next)){setError(t('Не удалось получить состояние просмотра. Повторите открытие.'));return}
  setState(previous=>selectPreviewState(previous,next));
  if(next.url&&!editing.current)setAddress(next.url);if(next.error)setError(next.error)
 }
 useEffect(()=>{alive.current=true;setState(null);setAddress('');setError('');let stopped=false;
  function read(){if(pending.current)return;pending.current=true;actions.current=actions.current.then(async()=>{try{const next=await api('/preview/'+key);if(!stopped){adopt(next);onState?.(key,next);if(next.state==='ready')setError('')}}catch(e){if(!stopped)setError(e.message)}finally{pending.current=false}})}
  read();const timer=setInterval(read,1500);return()=>{stopped=true;alive.current=false;clearInterval(timer);clearTimeout(typeTimer.current);clearTimeout(wheel.current)};
 },[key]);
 useEffect(()=>{if(liveState){adopt(liveState);if(liveState.state==='ready')setError('')}},[liveState]);
 useEffect(()=>{const observer=new ResizeObserver(entries=>{const rect=entries[0]?.contentRect;if(rect)setStageSize({width:rect.width,height:rect.height})});if(stage.current)observer.observe(stage.current);return()=>observer.disconnect()},[]);
 function act(action,extra={}){actions.current=actions.current.then(()=>execute(action,extra));return actions.current}
 async function execute(action,extra={}){
  if(pending.current&&action==='status')return;
  setBusy(true);pending.current=true;setError('');
  try{const next=await api('/preview/'+key,{method:'POST',body:JSON.stringify({action,...extra})});if(alive.current){adopt(next);onState?.(key,next);if(next.screenshot_url)setScreenshot(next.screenshot_url)}}catch(e){if(alive.current)setError(e.message)}finally{pending.current=false;if(alive.current)setBusy(false)}
 }
 useEffect(()=>{if(request?.url)act('open',{url:request.url})},[request?.id,key]);
 function click(e){if(busy||!state?.frame)return;const r=image.current.getBoundingClientRect();stage.current?.focus({preventScroll:true});act('click',{x:(e.clientX-r.left)/r.width*state.width,y:(e.clientY-r.top)/r.height*state.height})}
 function flushTyping(){clearTimeout(typeTimer.current);if(typing.current){const text=typing.current;typing.current='';act('type',{text})}}
 function keydown(e){
  if(!state?.frame||e.nativeEvent?.isComposing)return;
  if((e.ctrlKey||e.metaKey)&&!e.altKey&&['a','z','y'].includes(e.key.toLowerCase())){e.preventDefault();e.stopPropagation();flushTyping();act('press',{key:(e.metaKey?'Meta+':'Control+')+(e.shiftKey?'Shift+':'')+e.key.toUpperCase()});return}
  if(e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.key.length===1){e.preventDefault();typing.current+=e.key;clearTimeout(typeTimer.current);typeTimer.current=setTimeout(flushTyping,100)}
  else if(['Enter','Tab','Backspace','Delete','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageDown','PageUp'].includes(e.key)){e.preventDefault();flushTyping();act('press',{key:e.shiftKey?'Shift+'+e.key:e.key})}
 }
 function scroll(e){if(!state?.frame)return;scrollAmount.current+=e.deltaY;clearTimeout(wheel.current);wheel.current=setTimeout(()=>{const dy=scrollAmount.current;scrollAmount.current=0;act('scroll',{dy})},100)}
 const ready=state?.state==='ready';
 const watching=state?.activity?.active,cursor=state?.source==='agent'&&state.cursor?.visible?state.cursor:null;
 const scale=Math.max(.1,Math.min(1,(stageSize.width-24)/(state?.width||1280),(stageSize.height-24)/(state?.height||800)));
 return <aside className={'browser-preview'+(expanded?' expanded':'')} aria-label={t('Просмотр сайта')}>
  <header><div><Globe size={15}/><strong>{t('Просмотр сайта')}</strong>{watching&&<span className="preview-live"><i/>{t('Агент в браузере')}</span>}</div><div className="preview-window-controls"><button className="icon-button" aria-label={expanded?t('Свернуть просмотр'):t('Развернуть просмотр')} title={expanded?t('Свернуть просмотр'):t('Развернуть просмотр')} onClick={()=>setExpanded(value=>!value)}>{expanded?<Minimize2 size={14}/>:<Maximize2 size={14}/>}</button><button className="icon-button" aria-label={t('Свернуть панель просмотра')} onClick={onClose}><X size={16}/></button></div></header>
  <form className="preview-address" onSubmit={e=>{e.preventDefault();act('open',{url:address})}}><input aria-label={t('Адрес сайта')} placeholder="http://localhost:5173" value={address} onFocus={()=>editing.current=true} onBlur={()=>editing.current=false} onChange={e=>setAddress(e.target.value)} spellCheck={false}/><button type="submit" className="icon-button" aria-label={t('Открыть сайт')} disabled={busy||!address.trim()}>{busy?<LoaderCircle className="spin" size={15}/>:<ArrowUpRight size={16}/>}</button></form>
  <nav className="preview-toolbar"><button className="icon-button" disabled={!ready||busy} title={t('Назад')} aria-label={t('Назад')} onClick={()=>act('back')}><ArrowLeft size={15}/></button><button className="icon-button" disabled={!ready||busy} title={t('Вперёд')} aria-label={t('Вперёд')} onClick={()=>act('forward')}><ArrowRight size={15}/></button><button className="icon-button" disabled={!ready||busy} title={t('Обновить страницу')} aria-label={t('Обновить страницу')} onClick={()=>act('reload')}><RefreshCw size={14}/></button><span className="preview-title">{state?.title||t('Новая страница')}</span><button className="icon-button" disabled={!ready||busy} title={t('Мобильный размер')} aria-label={t('Мобильный размер')} onClick={()=>act('viewport',{width:390,height:844})}><Smartphone size={14}/></button><button className="icon-button" disabled={!ready||busy} title={t('Размер компьютера')} aria-label={t('Размер компьютера')} onClick={()=>act('viewport',{width:1280,height:800})}><Monitor size={14}/></button><button className="icon-button" disabled={!ready||busy} title={t('Снимок страницы')} aria-label={t('Снимок страницы')} onClick={()=>act('screenshot')}><Camera size={14}/></button>{ready&&/^https?:/.test(state.url)&&<a className="icon-button" href={state.url} target="_blank" rel="noreferrer" title={t('Открыть в обычном браузере')} aria-label={t('Открыть в обычном браузере')}><ExternalLink size={14}/></a>}</nav>
  {error&&<p className="preview-error" role="alert">{t(error)}</p>}
  <div className={'preview-stage '+(ready?'ready':'')} ref={stage} tabIndex={ready?0:-1} onKeyDown={keydown} onPaste={e=>{e.preventDefault();flushTyping();act('type',{text:e.clipboardData.getData('text')})}} onWheel={scroll} role="group" aria-label={t('Страница просмотра')}>
   {state?.frame?<div className="preview-page" style={{width:Math.round(state.width*scale),height:Math.round(state.height*scale)}}><img ref={image} className="preview-frame" src={state.frame} width={state.width} height={state.height} draggable={false} onClick={click} alt={state.title||t('Страница сайта')}/>{cursor&&<span className={'preview-agent-cursor'+(cursor.down?' clicking':'')} style={{left:cursor.x/state.width*100+'%',top:cursor.y/state.height*100+'%'}} aria-hidden="true"><svg width="22" height="27" viewBox="0 0 22 27"><path d="M2 1.5v20l5.8-5.4 4.5 9 4-2-4.6-9 7.9-1z" fill="#a993ef" stroke="#fff" strokeWidth="1.2" strokeLinejoin="round"/></svg>{cursor.down&&<i key={cursor.click_id}/>}<small>{t('Агент')}</small></span>}</div>:<div className="preview-empty">{watching?<LoaderCircle size={30} className="spin"/>:<Globe size={33}/>}<h3>{t(watching?'Агент открывает страницу':'Результат рядом с чатом')}</h3><p>{t(watching?'Здесь будут видны страница, движение курсора и действия агента.':'Введите адрес сайта или откройте его из сообщения. Агент может видеть эту же страницу и снимать скриншоты.')}</p><small>{t('Локальные адреса и обычные сайты. Основные браузеры доступны отдельно.')}</small></div>}
  </div>
  <footer><span className={'tiny-dot '+(ready?'green':'muted')}/>{ready?state.width+' × '+state.height:t('Браузер запускается при открытии сайта')}{screenshot&&<a href={screenshot} download>{t('Скачать снимок')}</a>}<span>{t(watching?'Действия агента в реальном времени':'Кликните на страницу для ввода')}</span></footer>
 </aside>;
}
