import React, {useEffect, useState} from 'react';
import {Clock3, Check, X, ListOrdered, CornerDownRight, ShieldCheck, Shield, BookOpen, Plus, Search, Save, Cpu, ChevronRight, Sparkles, GitBranch} from 'lucide-react';
import {api} from './api.js';
import {t, getLocale} from './i18n.js';

const asDate=value=>{const date=new Date(typeof value==='number'?value*1000:value);return value&&Number.isFinite(date.getTime())?date:null};
export const formatTime = value => {
  const date=asDate(value);if(!date)return '';
  return new Intl.DateTimeFormat(getLocale()==='ru'?'ru-RU':'en-GB', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(date);
};
export function duration(value) {
  const seconds=Math.max(0,Math.floor(value||0));
  const hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60);
  const [h,m,s]=getLocale()==='ru'?['ч','м','с']:['h','m','s'];
  return hours ? `${hours}${h} ${minutes}${m}` : minutes ? `${minutes}${m} ${seconds%60}${s}` : `${seconds}${s}`;
}
export function RunClock({started, label}) {
  const [now,setNow]=useState(Date.now()/1000);
  useEffect(()=>{setNow(Date.now()/1000);const timer=setInterval(()=>setNow(Date.now()/1000),1000);return()=>clearInterval(timer)},[started]);
  return started ? <span className="run-clock"><Clock3 size={12}/>{label||t('В работе')} {duration(now-started)}</span> : null;
}
export function MessageTiming({message,onBranch,branchDisabled=false}) {
  const timing=message.work_timing;
  const date=asDate(timing?.finished||message.timestamp);
  return <div className="message-timing">
    {date&&<time dateTime={date.toISOString()} title={date.toLocaleString()}>{timing?t('Завершено')+' ':''}{formatTime(timing?.finished||message.timestamp)}</time>}
    {onBranch&&<button type="button" className="message-branch-button" aria-label={t('Создать ветку чата')} title={branchDisabled?t('Дождитесь завершения ответа и очереди'):t('Создать ветку чата')} disabled={branchDisabled} onClick={onBranch}><GitBranch size={12}/></button>}
    {timing?.elapsed_seconds!=null&&<><span>·</span><span><Check size={11}/>{t('Завершено за')} {duration(timing.elapsed_seconds)}</span></>}
    {timing?.first_output_seconds!=null&&<span title={t('Время до первого вывода, включая обработку контекста')}>· {t('До ответа')} {duration(timing.first_output_seconds)}</span>}
    {timing?.model&&<span className="turn-model">{timing.model}</span>}
  </div>;
}
export function AccessPanel({value,onChange,onClose}) {
  const [working,setWorking]=useState(false),[error,setError]=useState('');
  async function select(mode){setWorking(true);try{await onChange(mode);onClose()}catch(e){setError(e.message)}finally{setWorking(false)}}
  return <div className="access-options"><p className="panel-intro">{t('Выберите, как агент выполняет действия в этом чате. Режим можно изменить в любой момент.')}</p>
    {[['manual',Shield,t('С подтверждениями'),t('Агент спрашивает разрешение на действия, для которых оно требуется.')],['full',ShieldCheck,t('Полный доступ'),t('Файлы, терминал и сеть без запросов подтверждения от агента. Доступ ограничен правами запущенного процесса Windows.')]].map(([mode,Icon,title,copy])=><button key={mode} disabled={working} className={'access-option '+(value===mode?'selected':'')} onClick={()=>select(mode)}><Icon size={22}/><div><strong>{title}</strong><p>{copy}</p></div>{value===mode&&<Check size={17}/>}</button>)}
    <p className="panel-footnote">{t('Уточнения по самому заданию могут появляться в обоих режимах.')}</p>{error&&<p role="alert" className="panel-error">{t(error)}</p>}</div>;
}
export function ChatModelPanel({sid,current,onChanged,onLibrary,onApi}) {
  const [models,setModels]=useState([]),[url,setUrl]=useState(''),[error,setError]=useState(''),[working,setWorking]=useState(false),[confirmation,setConfirmation]=useState(null);
  useEffect(()=>{api('/session-models').then(data=>{setModels(data.models);setUrl(data.url)}).catch(e=>setError(e.message))},[]);
  async function select(model,confirm) {
    setWorking(true);setError('');
    try {
      const result=await api('/sessions/'+sid+'/model',{method:'POST',body:JSON.stringify({model,confirm})});
      if(result.status==='confirmation_required')setConfirmation({model,result});else await onChanged();
    }catch(e){setError(e.message)}finally{setWorking(false)}
  }
  return <div className="chat-models"><div className="continuity-banner"><BookOpen size={17}/><div><strong>{t('Один чат, общая история')}</strong><p>{t('При смене модели сохраняются сообщения, файлы и память проекта. Размер рабочего контекста зависит от выбранной модели.')}</p></div></div>
    <p className="panel-intro">{t('Локальные и подключённые API-модели')}</p>{models.map(model=><button key={model.id} className={'chat-model-option '+(current===model.id?'selected':'')} disabled={working||!sid} onClick={()=>select(model.id)}><Cpu size={20}/><div><strong>{model.name}</strong><span>{model.kind==='cloud'?t('API · нужен интернет')+' · '+model.provider_name:t('На этом компьютере')} · {current===model.id?t('Используется в этом чате'):t('Переключить в этом чате')}</span></div>{current===model.id?<Check size={17}/>:<ChevronRight size={17}/>}</button>)}
    <p className="panel-footnote">{models.length===1?t('Сейчас API предоставляет одну модель. После подключения других моделей они появятся здесь.'):''}</p><code className="endpoint-caption">{url}</code><button className="secondary-panel-button" onClick={onLibrary}><Plus size={14}/>{t('Подключить или скачать другую модель')}</button>
    {confirmation&&<div className="warning-card"><div><p>{confirmation.result.confirm_message||confirmation.result.message||t('Агент запросил подтверждение смены модели. История сохранится, но меньший контекст может потребовать сжатия.')}</p><button className="primary-button" onClick={()=>select(confirmation.model,confirmation.result.confirm||confirmation.result.confirmation?.confirm)}>{t('Подтвердить переключение')}</button></div></div>}
    <button className="secondary-panel-button" onClick={onApi}><Plus size={14}/>{t('Подключить по API')}</button>
    {error&&<p className="panel-error" role="alert">{t(error)}</p>}</div>;
}
export function SkillsPanel({sid,learning,onLearning,onTeach,onUse}) {
  const [skills,setSkills]=useState([]),[search,setSearch]=useState(''),[editing,setEditing]=useState(false),[name,setName]=useState(''),[description,setDescription]=useState(''),[instructions,setInstructions]=useState(''),[error,setError]=useState(''),[saved,setSaved]=useState(''),[working,setWorking]=useState(false);
  const load=()=>api('/skills').then(data=>setSkills(data.skills)).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);
  async function save(e){e.preventDefault();setWorking(true);setError('');try{const result=await api('/skills',{method:'POST',body:JSON.stringify({name,description,instructions})});setSaved(result.name);setEditing(false);await load()}catch(e){setError(e.message)}finally{setWorking(false)}}
  const filtered=skills.filter(skill=>(skill.name+' '+skill.description).toLowerCase().includes(search.toLowerCase()));
  return <div className="skills-panel"><div className="continuity-banner"><Sparkles size={19}/><div><strong>{t('Опыт, который остаётся с вами')}</strong><p>{t('Навыки хранят инструкции и проверенные приёмы на вашем диске. Они помогают агенту в следующих задачах и не изменяют веса модели.')}</p></div></div>
    {sid&&<div className="settings-row"><div><strong>{t('Сохранять полезный опыт')}</strong><p>{t('Просить агента записывать новые проверенные приёмы в навыки, без паролей и личных данных.')}</p></div><button className={'toggle '+(learning?'on':'')} role="switch" aria-label={t('Сохранять полезный опыт')} aria-checked={!!learning} onClick={()=>onLearning(!learning)}><span/></button></div>}
    <div className="skills-toolbar"><span>{skills.length} {t('навыков доступно')}</span><button className="secondary-panel-button" onClick={()=>setEditing(!editing)}><Plus size={14}/>{t('Научить агента')}</button>{sid&&<button className="secondary-panel-button" onClick={onTeach}><BookOpen size={14}/>{t('Из опыта этого чата')}</button>}</div>
    {saved&&<p className="skill-saved" role="status"><Check size={14}/>{t('Навык сохранён:')} {saved}. {t('Его можно использовать в следующих задачах.')}</p>}
    {editing&&<form className="skill-editor" onSubmit={save}><label>{t('Короткое имя латиницей')}<input required pattern="[a-z0-9][a-z0-9-]{1,63}" placeholder="my-coding-workflow" value={name} onChange={e=>setName(e.target.value)}/></label><label>{t('Когда применять')}<input required maxLength={600} placeholder={t('Например: при создании сайтов на Django')} value={description} onChange={e=>setDescription(e.target.value)}/></label><label>{t('Чему научить')}<textarea required rows={7} maxLength={60000} placeholder={t('Опишите шаги, ваши предпочтения, пример результата и способ проверки…')} value={instructions} onChange={e=>setInstructions(e.target.value)}/></label><button className="primary-button" disabled={working}><Save size={14}/>{t('Сохранить навык')}</button></form>}
    <div className="modal-search"><Search size={15}/><input placeholder={t('Найти навык…')} value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="skills-list">{filtered.map(skill=><div className="skill-row" key={skill.id}><BookOpen size={16}/><div><strong>{skill.name}</strong><p>{skill.description}</p></div>{sid&&<button className="icon-button" title={t('Использовать в чате')} aria-label={t('Использовать в чате')+' '+skill.name} onClick={()=>onUse(skill.name)}><CornerDownRight size={16}/></button>}</div>)}{!filtered.length&&<p className="panel-footnote">{t('Навыки не найдены')}</p>}</div>{error&&<p className="panel-error" role="alert">{t(error)}</p>}</div>;
}
