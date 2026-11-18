import React,{useEffect,useRef,useState} from 'react';
import {FolderOpen,ExternalLink,PanelRightOpen,Copy,Download} from 'lucide-react';
import {api} from './api.js';
import {copyText} from './clipboard.js';
import {t} from './i18n.js';
import './context-menu.css';

export function contextTarget(element,files=[],base=location.href){
 const node=element?.closest?.('[data-freedom-file-id]'),anchor=element?.closest?.('a[href]');
 let url;try{url=anchor?new URL(anchor.getAttribute('href'),base):null}catch{}
 const artifact=url?.origin===new URL(base).origin?url.pathname.match(/^\/api\/(artifacts|files)\/([\w-]+)(?:\/document)?$/):null;
 const fid=node?.dataset.freedomFileId||artifact?.[2];
 const file=files.find(f=>{if(f.id===fid)return true;try{return url&&new URL(f.url,base).href===url.href}catch{return false}});
 if(file||fid)return {file:{...file,id:file?.id||fid,name:file?.name||anchor?.textContent||t('Файл'),url:file?.url||url?.href,source:file?.source||artifact?.[1]||node?.dataset.freedomFileSource||'artifacts'},url:null};
 return url&&['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?{file:null,url:url.href}:null;
}

export function ContextMenu({files=[],onPreview,notify}){
 const[menu,setMenu]=useState(null);const panel=useRef(null);
 const local=location.protocol==='http:'&&['127.0.0.1','localhost','[::1]'].includes(location.hostname);
 useEffect(()=>{
  const open=event=>{
   if(event.shiftKey||event.target.closest?.('input,textarea,[contenteditable="true"]'))return;
   const target=contextTarget(event.target,files);if(!target)return;
   event.preventDefault();const rect=event.target.getBoundingClientRect();
   setMenu({...target,x:event.clientX||rect.left,y:event.clientY||rect.bottom,selection:window.getSelection()?.toString()||''});
  };
  document.addEventListener('contextmenu',open);return()=>document.removeEventListener('contextmenu',open);
 },[files]);
 useEffect(()=>{
  if(!menu)return;
  const close=event=>{if(!panel.current?.contains(event.target))setMenu(null)};
  const escape=event=>{if(event.key==='Escape'){event.preventDefault();setMenu(null)}};
  const resize=()=>setMenu(null);
  document.addEventListener('pointerdown',close);document.addEventListener('keydown',escape);
  window.addEventListener('resize',resize);window.addEventListener('scroll',resize,true);
  panel.current?.querySelector('button')?.focus({preventScroll:true});
  return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',escape);window.removeEventListener('resize',resize);window.removeEventListener('scroll',resize,true)};
 },[menu]);
 if(!menu)return null;
 async function run(action){setMenu(null);try{await action()}catch(error){notify(error.message)}}
 function external(){if(local)return api('/desktop/open-url',{method:'POST',body:JSON.stringify({url:menu.url})});window.open(menu.url,'_blank','noopener,noreferrer')}
 function copy(value){return run(async()=>{await copyText(value);notify(t('Скопировано'))})}
 const file=menu.file;
 return <div ref={panel} className="freedom-context-menu" role="menu" aria-label={t(file?'Действия с файлом':'Действия со ссылкой')}
  style={{left:Math.max(8,Math.min(menu.x,window.innerWidth-282)),top:Math.max(8,Math.min(menu.y,window.innerHeight-(file?220:214)))}}
  onKeyDown={event=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;event.preventDefault();const buttons=[...panel.current.querySelectorAll('button,a')];let index=buttons.indexOf(document.activeElement);index=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;buttons[index]?.focus()}}>
  <div className="context-menu-label" title={file?.name||menu.url}>{file?.name||menu.url}</div>
  {file?<>
   {local&&<button role="menuitem" onClick={()=>run(()=>api('/'+(file.source==='files'?'files':'artifacts')+'/'+file.id+'/reveal',{method:'POST',body:'{}'}))}><FolderOpen size={15}/>{t('Открыть папку с файлом')}</button>}
   {file.path&&/\.html?$/i.test(file.path)&&<button role="menuitem" onClick={()=>run(()=>onPreview(file.path))}><PanelRightOpen size={15}/>{t('Открыть во встроенном браузере')}</button>}
   {file.path&&<button role="menuitem" onClick={()=>copy(file.path)}><Copy size={15}/>{t('Копировать путь к файлу')}</button>}
   {file.url&&<a role="menuitem" href={file.url} download onClick={()=>setMenu(null)}><Download size={15}/>{t('Скачать файл')}</a>}
  </>:<>
   <button role="menuitem" onClick={()=>run(external)}><ExternalLink size={15}/>{t('Открыть в браузере по умолчанию')}</button>
   <button role="menuitem" onClick={()=>run(()=>onPreview(menu.url))}><PanelRightOpen size={15}/>{t('Открыть во встроенном браузере')}</button>
   <button role="menuitem" onClick={()=>copy(menu.url)}><Copy size={15}/>{t('Копировать ссылку')}</button>
  </>}
  {menu.selection&&<button role="menuitem" onClick={()=>copy(menu.selection)}><Copy size={15}/>{t('Копировать выделенный текст')}</button>}
 </div>;
}
