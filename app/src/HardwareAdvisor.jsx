import React,{useEffect,useRef,useState} from 'react';
import {Cpu,Monitor,HardDrive,RefreshCw,Code2,MessageSquare,Image as ImageIcon,Video,Check,Download,ExternalLink,ChevronRight,Cloud,LoaderCircle,Search,Info} from 'lucide-react';
import {api,CONNECTION_ERROR} from './api.js';
import {t,getLocale} from './i18n.js';
import './hardware-advisor.css';

const gb=value=>Number.isFinite(value)?(value/1024**3).toFixed(1)+t(' ГБ'):'—';
const tasks=[['code','Код',Code2],['chat','Чат',MessageSquare],['image','Изображения',ImageIcon],['video','Видео',Video]];
const fitLabels={recommended:'Подходит для вашего ПК',cpu:'GPU + RAM / CPU',limited:'Есть ограничения'};

export function HardwareAdvisor({onLibrary}){
 const[data,setData]=useState(null),[task,setTask]=useState('code'),[error,setError]=useState(''),[busy,setBusy]=useState('');
 const[secret,setSecret]=useState(''),[persist,setPersist]=useState(false);
 const alive=useRef(true);
 useEffect(()=>{alive.current=true;let stopped=false,requestedScan=false;
  async function load(){try{const next=await api('/advisor');if(stopped)return;setData(next);setError(prior=>prior===CONNECTION_ERROR?'':prior);if(!requestedScan){requestedScan=true;const scanned=await api('/advisor/scan',{method:'POST',body:'{}'});if(!stopped)setData(scanned)}}catch(e){if(!stopped)setError(e.message)}}
  load();const timer=setInterval(load,2000);return()=>{stopped=true;alive.current=false;clearInterval(timer)};
 },[]);
 async function action(path,payload={},key=path){
  setBusy(key);setError('');
  try{await api(path,{method:'POST',body:JSON.stringify(payload)});if(path.includes('/huggingface/connect'))setSecret('');const next=await api('/advisor');if(alive.current)setData(next)}
  catch(e){if(alive.current)setError(e.message)}finally{if(alive.current)setBusy('')}
 }
 const hw=data?.hardware||{},account=data?.huggingface||{},checking=!data||data.state==='checking';
 const rows=data?.recommendations?.[task]||[];
 const ready=data?.state==='complete';
 return <div className="hardware-advisor">
  <div className="advisor-intro"><div><span className="advisor-eyebrow">{t('ВАШ ПК · ВАШИ ВОЗМОЖНОСТИ')}</span><p>{t('Выберите задачу. Подберём поддерживаемые модели с учётом памяти, движка и места на диске.')}</p></div><button className="advisor-scan" disabled={checking||!!busy} onClick={()=>action('/advisor/scan')}><RefreshCw size={14} className={checking?'spin':''}/>{checking?t('Проверяем ПК…'):t('Проверить снова')}</button></div>
  <div className="advisor-hardware"><div><Cpu size={16}/><span>{t('Процессор')}</span><strong>{hw.cpu?.trim()||'—'}</strong><small>{hw.physical_cores||'—'} {t('ядер')} · {hw.threads||'—'} {t('потоков')}</small></div><div><Monitor size={16}/><span>{t('Видеокарта')}</span><strong>{hw.gpus?.map(g=>g.name).join(', ')||t('Не определена')}</strong><small>{hw.vram_gb||'—'} {t('ГБ VRAM')}{hw.unified_memory?' · '+t('Общая память'):''} · {hw.cuda?'CUDA':hw.metal?'Metal':hw.vulkan?'Vulkan':'CPU'}</small></div><div><HardDrive size={16}/><span>{t('Память и диск')}</span><strong>{hw.ram_gb||'—'} {t('ГБ RAM')}</strong><small>{hw.free_disk_gb??'—'} {t('ГБ свободно')}</small></div></div>
  <div className="advisor-scan-meta"><span>{hw.os} {hw.os_version} · {hw.architecture}</span>{Number.isFinite(hw.ram_available_gb)&&<span>{t('Сейчас свободно')}: RAM {hw.ram_available_gb} {t('ГБ')} · GPU {Math.max(0,...(hw.gpus||[]).map(g=>g.free_gb||0))} {t('ГБ')}</span>}{data?.checked_at&&<time>{t('Проверено')}: {new Date(data.checked_at*1000).toLocaleString(getLocale()==='ru'?'ru-RU':'en-GB')}</time>}</div>
  <div className="advisor-task-tabs" role="tablist" aria-label={t('Для чего нужна модель')}>{tasks.map(([id,label,Icon])=><button key={id} type="button" role="tab" aria-selected={task===id} className={task===id?'selected':''} onClick={()=>setTask(id)}><Icon size={14}/>{t(label)}</button>)}</div>
  {error&&<p className="advisor-error" role="alert">{t(error)}</p>}
  {data?.error&&<p className="advisor-error" role="alert">{t(data.error)}</p>}
  {checking&&<div className="advisor-loading" role="status"><LoaderCircle className="spin" size={18}/>{t('Определяем железо и доступные движки…')}</div>}
  {ready&&<><div className="advisor-result-heading"><h3>{t('Что установить для этой задачи')}</h3><button onClick={()=>onLibrary(task,'search')}><Search size={12}/>{t('Найти ещё')}</button></div>
   {!!rows.length&&!rows.some(row=>row.best)&&<p className="advisor-limit-note"><Info size={15}/>{t('Поддерживаемые комплекты для этой задачи превышают возможности ПК. Посмотрите требования или найдите более лёгкий вариант. Произвольные генераторы могут требовать отдельного подключения.')}</p>}
   <div className="advisor-models">{rows.map(row=>{
    const downloading=['downloading','verifying'].includes(row.job.state),percent=row.total?Math.round((row.total-row.remaining)/row.total*100):0;
    return <article key={row.id} className={'advisor-model '+(row.best?'best':'')}>
     <div className="advisor-model-header"><div><div className="advisor-badges">{row.best&&<span className="advisor-best">{t('ЛУЧШИЙ БАЛАНС ДЛЯ ПК')}</span>}<span className={'advisor-fit '+row.fit}>{t(fitLabels[row.fit])}</span>{row.installed&&<span className="advisor-installed"><Check size={10}/>{t('Установлена')}</span>}</div><h4>{row.name}</h4></div><span className="advisor-size">{gb(row.total)}</span></div>
     <p className="advisor-model-note">{t(row.note)}</p><div className="advisor-needs"><span>{t('RAM от')} <b>{row.needs_ram} {t('ГБ')}</b></span><span>{t('GPU от')} <b>{row.needs_vram} {t('ГБ')}</b></span>{row.context&&<span>{t('Контекст')} <b>{Math.round(row.context/1024)}K</b></span>}<span>{t('Нужно на диске')} <b>{gb(row.disk_required)}</b></span></div>
     <div className={'advisor-reasons '+row.fit}>{row.reasons.map(reason=><p key={reason}>{t(reason)}</p>)}</div>
     {downloading&&<div className="advisor-download-state" role="status"><div><span>{row.job.state==='verifying'?t('Проверяем SHA256'):t('Скачиваем модель…')}</span><b>{percent}%</b></div><div className="advisor-download-track"><i style={{width:percent+'%'}}/></div></div>}
     {row.job.error&&<p className="advisor-error">{t(row.job.error)}</p>}
     <div className="advisor-model-actions"><a href={row.source.startsWith('https://')?row.source:undefined} target="_blank" rel="noreferrer">{t('Карточка и лицензия')} <ExternalLink size={12}/></a>{row.installed||downloading?<button onClick={()=>onLibrary(task,'catalog')}>{t('Открыть мои модели')}<ChevronRight size={13}/></button>:<button className="primary-button" disabled={!row.can_download||!!busy} onClick={()=>action('/library/download',{id:row.id},row.id)}>{busy===row.id?<LoaderCircle className="spin" size={13}/>:<Download size={13}/>} {row.remaining<row.total?t('Продолжить загрузку'):t('Скачать модель')}</button>}</div>
    </article>;
   })}</div></>}
  <details className="advisor-hf"><summary><Cloud size={16}/><span>Hugging Face</span><small>{account.username?'@'+account.username:account.available?t('Обнаружен локальный вход'):t('Подключить аккаунт')}</small><ChevronRight size={13}/></summary><div className="advisor-hf-body">
   <p>{t('Открытые модели доступны без входа. Для ограниченных репозиториев подключите токен Read. Вход на сайте в браузере не передаёт доступ приложению.')}</p>
   <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noreferrer">{t('Получить токен Hugging Face')} <ExternalLink size={12}/></a>
   <ol><li>{t('Войдите в Hugging Face и создайте токен Read или Fine-grained с правом чтения выбранных моделей.')}</li><li>{t('Вставьте токен ниже. Если модель запрашивает доступ или согласие, откройте её карточку и подтвердите условия самостоятельно.')}</li></ol>
   {account.credential_error&&<p role="alert" className="advisor-error">{t('Локальное хранилище Hugging Face недоступно. Существующий файл сохранён.')}</p>}
   <form onSubmit={e=>{e.preventDefault();action('/advisor/huggingface/connect',{token:secret,persist})}}><label>{t('Токен Hugging Face')}<input type="password" autoComplete="off" spellCheck={false} aria-label={t('Токен Hugging Face')} value={secret} onChange={e=>setSecret(e.target.value)} placeholder="hf_…" maxLength={256}/></label>{account.persistent_supported&&<label className="advisor-remember"><input type="checkbox" checked={persist} onChange={e=>setPersist(e.target.checked)}/>{t('Запомнить на этом ПК с защитой Windows')}</label>}<p className="advisor-secret-note">{t('Без сохранения токен действует до закрытия приложения. Ключ не попадает в чаты и историю.')}</p><div className="advisor-hf-actions"><button className="primary-button" disabled={!secret.trim()||!!busy}>{busy==='/advisor/huggingface/connect'?<LoaderCircle className="spin" size={13}/>:<Check size={13}/>} {t('Подключить')}</button>{account.available&&<><button type="button" disabled={!!busy} onClick={()=>action('/advisor/huggingface/check')}>{t('Проверить вход')}</button><button type="button" disabled={!!busy} onClick={()=>action('/advisor/huggingface/disconnect')}>{t('Отключить')}</button></>}</div></form>
   <a className="advisor-hf-doc" href="https://huggingface.co/docs/hub/security-tokens" target="_blank" rel="noreferrer">{t('Инструкция Hugging Face')} <ExternalLink size={11}/></a>
  </div></details>
  <div className="advisor-footnote"><Info size={15}/><p>{t('Это оценка совместимости, а не замер скорости. Учтены память для контекста и запас на диске. Свободная RAM и VRAM меняются: перед генерацией может понадобиться освободить память. Код, изображения и видео используют GPU по очереди. Загрузка начинается только по вашей кнопке.')}</p></div>
 </div>;
}
