import React,{useEffect,useState} from 'react';
import {Globe,ImagePlus,LoaderCircle} from 'lucide-react';
import {t} from './i18n.js';
import './research-buttons.css';
import {api} from './api.js';

export default function ResearchButtons({web,image,sending,working,onWeb,onImage,sid,browser='builtin',engine='auto',onSelection}){
 const[choices,setChoices]=useState([]),[changing,setChanging]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let closed=false;Promise.all([api('/browser/choices'),api('/browser/'+(sid||'workspace')+'/preferences')]).then(([list,value])=>{if(!closed){setChoices(list.browsers||[]);onSelection?.(value)}}).catch(e=>{if(!closed)setError(e.message)});return()=>{closed=true}},[sid]);
 async function select(nextBrowser,nextEngine){setChanging(true);setError('');try{const choice=await api('/browser/'+(sid||'workspace')+'/preferences',{method:'POST',body:JSON.stringify({browser:nextBrowser,engine:nextEngine})});onSelection?.(choice)}catch(e){setError(e.message)}finally{setChanging(false)}}
 return <div className="mode-switch research-buttons" role="group" aria-label={t('Поиск и изображения')}>
  <button type="button" disabled={sending} className={web&&!image?'selected':''} aria-pressed={web&&!image} onClick={onWeb} title="Поиск в выбранном браузере">{sending&&web&&!image?<LoaderCircle size={13} className="spin"/>:<Globe size={13}/>}<span>{t('Веб-поиск')}</span></button>
  {web&&!image&&<><select className="research-browser-choice" aria-label="Браузер веб-поиска" disabled={sending||working||changing||!choices.length} value={browser} title="Мой профиль — обычное окно выбранного браузера с текущими входами. Профиль Freedom — отдельная сессия. Капчи подтверждаются вручную." onChange={e=>select(e.target.value,({'yandex':'yandex','yandex-personal':'yandex','chrome':'google','chrome-personal':'google','edge-personal':'bing','tor-personal':'duckduckgo'}[e.target.value]||'auto'))}>{choices.map(item=><option key={item.id} value={item.id} disabled={!item.available}>{item.name}{!item.available?' · не установлен':''}</option>)}</select><select className="research-engine-choice" aria-label="Поисковик веб-поиска" disabled={sending||working||changing} value={engine} onChange={e=>select(browser,e.target.value)}><option value="auto">Поисковик: авто</option><option value="google">Google</option><option value="yandex">Яндекс</option><option value="bing">Bing</option><option value="duckduckgo">DuckDuckGo</option></select></>}
  <button type="button" disabled={sending} className={image?'selected':''} aria-pressed={image} onClick={onImage} title={t('Создать изображение по описанию')}><ImagePlus size={13}/>{t('Изображение')}</button>
  {web&&!image&&error&&<small className="research-choice-error" role="alert">{error}</small>}
 </div>;
}
