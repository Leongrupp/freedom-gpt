import React,{useState,useEffect} from 'react';
import {Zap,Scale,Layers,Brain,Check,LoaderCircle,ChevronRight} from 'lucide-react';
import {api} from './api.js';
import {t,useLocale,getIntlLocale} from './i18n.js';
import './run-settings.css';

const levels=[['none','Сразу','Прямой ответ без отдельного обдумывания.'],['low','Кратко','Быстрое обдумывание обычных вопросов.'],['medium','Стандартно','Больше внимания плану и проверке решения.'],['high','Глубоко','Для сложной логики, архитектуры и анализа. Может занять заметно больше времени.'],['xhigh','Глубоко','Для сложной логики, архитектуры и анализа. Может занять заметно больше времени.']];
export function RunSettings({sid,reasoning,onReasoning,onChanged,cloud=false,agentBusy=false}){
 useLocale();
 const[state,setState]=useState(null),[error,setError]=useState(''),[working,setWorking]=useState(false);
 async function load(){const value=await api('/run-settings'+(sid?'?sid='+encodeURIComponent(sid):''));setState(value);return value}
 useEffect(()=>{let stop=false;const refresh=()=>api('/run-settings'+(sid?'?sid='+encodeURIComponent(sid):'')).then(v=>{if(!stop)setState(v)}).catch(e=>{if(!stop)setError(e.message)});refresh();const timer=setInterval(refresh,2500);return()=>{stop=true;clearInterval(timer)}},[sid]);
 async function context(value){setWorking(true);setError('');try{setState(await api('/context',{method:'POST',body:JSON.stringify({context:value,sid})}));onChanged?.()}catch(e){setError(e.message)}finally{setWorking(false)}}
 async function think(value){setWorking(true);setError('');try{if(sid)await api('/sessions/'+sid+'/run-settings',{method:'POST',body:JSON.stringify({reasoning:value})});onReasoning(value);await load();onChanged?.()}catch(e){setError(e.message)}finally{setWorking(false)}}
 async function cancel(){setWorking(true);try{setState(await api('/context',{method:'POST',body:JSON.stringify({action:'cancel',sid})}))}catch(e){setError(e.message)}finally{setWorking(false)}}
 if(!state)return <div className="run-loading"><LoaderCircle className="spin" size={18}/>{t('Читаем настройки модели…')}</div>;
 const perf=state.performance||{},pending=perf.pending,waiting=perf.phase==='waiting',busy=['applying','calibrating','restoring'].includes(perf.phase);
 const selected=pending&&typeof pending==='object'?pending.context:state.context;
 const fmt=value=>new Intl.NumberFormat(getIntlLocale()).format(value);
 return <div className="run-settings">
  <div className="run-explainer"><Brain size={20}/><p>{t('Контекст — сколько истории и файлов модель может учитывать. Обдумывание — сколько усилий она тратит перед ответом.')}</p></div>
  {cloud?<p className="run-notice">{t('Для API размер окна и обдумывание определяет выбранный провайдер.')}</p>:<>
   <div className="run-section-heading"><strong>{t('Объём контекста')}</strong><span>{t('Предел модели')}: {fmt(state.native_context)}</span></div>
   <div className="context-options">{state.choices.map((value,index)=>{
    const Icon=index===0?Zap:index===state.choices.length-1?Layers:Scale;
    const title=index===0?'Быстрый':index===state.choices.length-1?'Максимальный':'Сбалансированный';
    const copy=index===0?'Для повседневных задач и высокой скорости.':index===state.choices.length-1?'Длинные документы, большой проект и объёмная переписка.':'Больше истории для задач с несколькими файлами.';
    return <button key={value} className={'context-option '+(selected===value?'selected':'')} disabled={working||busy||!!pending||!state.available} onClick={()=>context(value)} aria-pressed={selected===value}>
     <Icon size={19}/><div><strong>{t(title)}<span>{fmt(value)}</span></strong><p>{t(copy)}</p></div>{selected===value?<Check size={16}/>:<ChevronRight size={14}/>}</button>
   })}</div>
   <div className="run-context-note"><span className={'placement-dot '+(state.gpu_only?'gpu':'')}/><p>{t('Рабочее окно')}: <strong>{fmt(state.context)}</strong> · {t(state.gpu_only?'Модель целиком на GPU':'Распределение между GPU и RAM')}<br/>{t('При увеличении окна проверяем запуск и подбираем размещение в памяти. Если памяти недостаточно, прежний режим восстановится.')}</p></div>
   {(waiting||busy)&&<div className="run-operation" role="status"><LoaderCircle className="spin" size={15}/><div><strong>{t(waiting?'Изменение запланировано':'Настраиваем локальную модель…')}</strong><p>{t(waiting?'Применим после окончания текущего ответа и очереди.':perf.message||'Это может занять несколько минут.')}</p></div><button onClick={cancel} disabled={working}>{t('Отменить')}</button></div>}
   {!waiting&&!busy&&perf.message&&<p className="run-notice">{t(perf.message)}</p>}
   <p className="run-global">{t('Окно общее для локального движка и всех его чатов. При уменьшении длинная история может сжиматься; файлы и память проекта остаются на диске.')}</p>
   <div className="run-section-heading thinking-heading"><strong>{t('Глубина обдумывания')}</strong><span>{t('Для этого чата')}</span></div>
   <div className="thinking-options">{levels.filter(row=>state.reasoning_levels.includes(row[0])).map(([value,title,copy])=><button key={value} className={(reasoning||state.reasoning)===value?'selected':''} onClick={()=>think(value)} disabled={working||busy||!!pending||agentBusy} aria-pressed={(reasoning||state.reasoning)===value}><span>{t(title)}</span><i>{(reasoning||state.reasoning)===value&&<Check size={12}/>}</i></button>)}</div>
   <p className="thinking-description">{t(levels.find(row=>row[0]===(reasoning||state.reasoning))?.[2]||levels[1][2])}</p>
   <p className="run-global">{t('Турбо ускоряет вычисления отдельно от обдумывания. После смены окна для него подбирается профиль под новый объём.')}</p>
  </>}
  {(error||perf.phase==='error')&&<p className="panel-error" role="alert">{t(error||perf.message)}</p>}
 </div>;
}
