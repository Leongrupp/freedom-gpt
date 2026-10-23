import React,{useEffect,useState} from 'react';
import {BookOpen,Clock3,Database,FileText,LoaderCircle,RefreshCw,Search} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
import {formatTime} from './WorkspacePanels.jsx';
import './project-memory.css';
const names={user_request:'Требование пользователя',agent_report:'Отчёт агента',decision:'Решение',constraint:'Ограничение',checkpoint:'Состояние работы',lesson:'Приём работы',question:'Открытый вопрос',document:'Документ проекта'};
export function ProjectMemoryPanel({sid}){
 const[data,setData]=useState(null),[query,setQuery]=useState(''),[working,setWorking]=useState(false),[error,setError]=useState('');
 async function load(value=''){setWorking(true);setError('');try{setData(await api('/sessions/'+sid+'/memory'+(value?'?query='+encodeURIComponent(value):'')))}catch(e){setError(e.message)}finally{setWorking(false)}}
 useEffect(()=>{load()},[sid]);
 return <div className="project-memory-panel"><div className="continuity-banner"><BookOpen size={20}/><div><strong>{t('Память остаётся в проекте')}</strong><p>{t('Требования, решения и этапы работы хранятся на диске. Агент подбирает нужные фрагменты после сжатия, перезапуска и смены модели.')}</p></div></div>
 {data?.needs_project?<p className="panel-intro">{t('Выберите отдельную папку проекта. Для общей папки всех проектов память не смешивается.')}</p>:<>
 <div className="project-memory-stats"><div><Database size={15}/><strong>{data?.records??'—'}</strong><span>{t('записей')}</span></div><div><FileText size={15}/><strong>{data?.documents??'—'}</strong><span>{t('документов')}</span></div><div><Clock3 size={15}/><span>{data?.updated?formatTime(data.updated):t('Начнёт заполняться при работе агента')}</span></div></div>
 {data?.project&&<code className="project-memory-path">{data.project}</code>}
 <form className="project-memory-search" onSubmit={e=>{e.preventDefault();load(query)}}><Search size={15}/><input aria-label={t('Поиск в памяти проекта')} placeholder={t('Найти старое решение, требование или этап…')} value={query} onChange={e=>setQuery(e.target.value)}/><button disabled={working}>{working?<LoaderCircle size={15} className="spin"/>:t('Найти')}</button><button type="button" disabled={working} title={t('Последние записи')} onClick={()=>{setQuery('');load()}}><RefreshCw size={14}/></button></form>
 <div className="project-memory-items">{(data?.items||[]).map(item=><article key={item.id}><header><span>{t(names[item.kind]||item.kind)}</span><time>{formatTime(item.updated)}</time></header><p>{item.excerpt}</p>{item.evidence&&<small>{t('Указанное подтверждение:')} {item.evidence}</small>}<code>{item.source}</code></article>)}{!working&&data&&!data.items?.length&&<p className="panel-footnote">{query?t('Совпадений нет. Подробности остаются в файлах и истории чата.'):t('Здесь появятся требования и заметки по мере работы. Существующая история чатов сохранена.')}</p>}</div></>}
 <p className="panel-footnote">{t('Контекст модели остаётся конечным. Память помогает восстановить детали; выводы агента нужно сверять с кодом и результатами проверок.')}</p>{error&&<p className="panel-error" role="alert">{error}</p>}</div>
}
