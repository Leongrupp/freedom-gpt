import React from 'react';
import {ExternalLink,PanelRightOpen,Download,Image as ImageIcon,Play} from 'lucide-react';
import {t} from './i18n.js';
import './rich-content.css';

const norm=value=>String(value||'').replaceAll('\\','/').toLowerCase();
const media=file=>/^(image\/(png|jpeg|webp|gif|bmp)|video\/)/.test(file.mime||'');
function target(value,files){
 let raw=value.trim();try{raw=decodeURI(raw)}catch{}
 if(/^https?:\/\/[^\s]+$/i.test(raw))return raw;
 if(/^www\.[^\s]+$/i.test(raw))return 'https://'+raw;
 if(/^\/api\/(artifacts|files|video\/files|cloud\/(?:images|videos))\//.test(raw))return raw;
 const file=files.find(file=>norm(file.path)===norm(raw.replace(/^file:\/\/\//i,''))||norm(file.name)===norm(raw));return file?.url;
}
function Link({href,label,onPreview}){
 if(!href)return label;
 return <span className="rich-link"><a href={href} target="_blank" rel="noreferrer">{label}</a>{onPreview&&/^https?:/i.test(href)&&<button className="inline-preview" aria-label={t('Открыть ссылку в просмотре')} title={t('Открыть ссылку в просмотре')} onClick={()=>onPreview(href)}><PanelRightOpen size={11}/></button>}</span>;
}
function LinkText({text,files,onPreview}){
 const parts=String(text).split(/((?:https?:\/\/|www\.)[^\s<>"`]+|[A-Za-z]:[\\/][^\n\r<>"`]*?\.(?:png|jpe?g|webp|gif|mp4|webm|mov|html|pdf|txt|py)(?=[\s,;)]|$))/gi);
 return parts.map((part,i)=>{const trimmed=part.replace(/[.,;!?\]})]+$/,'');const href=target(trimmed,files);return href?<React.Fragment key={i}><Link href={href} label={trimmed} onPreview={onPreview}/>{part.slice(trimmed.length)}</React.Fragment>:<React.Fragment key={i}>{part}</React.Fragment>});
}
export function RichInline({text,files=[],onPreview}){
 const parts=String(text).split(/(`[^`]+`|\*\*[^*]+\*\*|!?\[[^\]]*\]\([^\n]+?\))/g);
 return parts.map((part,i)=>{
  if(part.startsWith('`')){const content=part.slice(1,-1),href=target(content,files);return <code key={i}>{href?<Link href={href} label={content} onPreview={onPreview}/>:content}</code>}
  if(part.startsWith('**'))return <strong key={i}><LinkText text={part.slice(2,-2)} files={files} onPreview={onPreview}/></strong>;
  const match=part.match(/^(!?)\[([^\]]*)\]\(([^\n]+)\)$/);
  if(match){const href=target(match[3],files);return <Link key={i} href={href} label={match[2]||t('Изображение')} onPreview={onPreview}/>}
  return <LinkText key={i} text={part} files={files} onPreview={onPreview}/>;
 });
}
export function referencedMedia(content,files){
 const text=norm(content);return files.filter(file=>media(file)&&((file.path&&text.includes(norm(file.path)))||text.includes(norm(file.url))||(files.filter(other=>other.name===file.name).length===1&&text.includes(norm(file.name)))));
}
export function MediaCards({files=[],label}){
 if(!files.length)return null;
 return <section className="message-media" aria-label={t('Превью файлов')}>{label&&<div className="message-media-label">{label}</div>}{files.map(file=><figure key={file.id} className="message-media-card">
  {file.mime?.startsWith('video/')?<video src={file.url} controls preload="metadata" playsInline aria-label={file.name}/>:<a href={file.url} target="_blank" rel="noreferrer"><img src={file.url} alt={file.name} loading="lazy"/></a>}
  <figcaption><span>{file.mime?.startsWith('video/')?<Play size={12}/>:<ImageIcon size={12}/>}<strong>{file.name}</strong></span><a href={file.url} download title={t('Скачать файл')} aria-label={t('Скачать файл')+': '+file.name}><Download size={13}/></a><a href={file.url} target="_blank" rel="noreferrer" title={t('Открыть полностью')} aria-label={t('Открыть полностью')}><ExternalLink size={12}/></a></figcaption>
 </figure>)}</section>;
}
export function UnreferencedMedia({files=[],messages=[]}){
 const[showAll,setShowAll]=React.useState(false);
 const referenced=new Set(messages.filter(m=>m.role==='assistant').flatMap(m=>referencedMedia(typeof m.content==='string'?m.content:Array.isArray(m.content)?m.content.filter(p=>p.type==='text').map(p=>p.text||'').join('\n'):'',files)).map(f=>f.id));
 const generated=files.filter(file=>media(file)&&!referenced.has(file.id)&&/\/(?:output\/(?:images|videos|cloud-images|cloud-videos)\/|creative-kit\/output\/)/.test(norm(file.path)));
 if(!generated.length)return null;
 return <><MediaCards files={showAll?generated:generated.slice(-6)} label={t('Изображения и видео этого чата')}/>{generated.length>6&&<button className="older-media-toggle" onClick={()=>setShowAll(value=>!value)}>{showAll?t('Свернуть'):t('Показать ещё')+' '+(generated.length-6)}</button>}</>;
}
