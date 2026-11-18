import React,{useState,useEffect} from 'react';
import {Zap,LoaderCircle,X,Check} from 'lucide-react';
import {api} from './api.js';
import {t,useLocale,getIntlLocale} from './i18n.js';
import './turbo.css';

export function useTurbo(metrics){
 const[state,setState]=useState(null),[error,setError]=useState(''),[sending,setSending]=useState(false);
 useEffect(()=>{if(metrics)setState(metrics)},[metrics]);
 useEffect(()=>{let stopped=false;api('/performance').then(v=>{if(!stopped)setState(v)}).catch(()=>{});return()=>{stopped=true}},[]);
 async function toggle(){
  if(sending)return;
  setSending(true);setError('');
  const pending=state?.phase==='waiting'||['calibrating','applying','restoring'].includes(state?.phase);
  try{setState(await api('/performance',{method:'POST',body:JSON.stringify({enabled:!pending&&!state?.active})}))}
  catch(e){setError(e.message)}finally{setSending(false)}
 }
 return {state,error,sending,toggle};
}
export function TurboControl({control,compact=false,cloud=false}){
 useLocale();
 const{state,error,sending,toggle}=control;
 const waiting=state?.phase==='waiting',working=['calibrating','applying','restoring'].includes(state?.phase);
 const on=state?.active&&!working&&!cloud,available=state?.available&&!cloud;
 const contextChange=state?.operation==='context';
 const label=contextChange?'Контекст':working?'Замер':waiting?'Ожидание':'Турбо';
 const title=cloud?'Скорость API зависит от провайдера':working||waiting?'Отменить настройку Турбо':on?'Вернуть обычный режим':'Подобрать самые быстрые настройки для этой модели и ПК';
 const Icon=working?LoaderCircle:waiting?LoaderCircle:Zap;
 const button=<button className={'turbo-button '+(on?'is-on ':'')+(working||waiting?'is-working ':'')}
  disabled={!available||sending||contextChange} onClick={toggle} title={t(title)} aria-label={t(title)} aria-pressed={on}>
  <Icon size={compact?13:15} className={working||waiting?'spin':''}/><span>{t(label)}</span>{!compact&&on&&<Check size={13}/>}<span className="sr-only">{on?t('Включено'):t('Выключено')}</span>
 </button>;
 if(compact)return <div className="turbo-compact">{button}</div>;
 const measure=state?.measured;
 const fmt=n=>new Intl.NumberFormat(getIntlLocale(),{maximumFractionDigits:1}).format(n);
 return <div className="turbo-card">
  <div className="turbo-heading"><span><Zap size={13}/>{t('Ускорение модели')}</span>{button}</div>
  {cloud?<p>{t('Скорость API зависит от провайдера')}</p>:<>
   {working?<><div className="turbo-progress"><i style={{width:(state?.progress||5)+'%'}}/></div><p role="status">{t(state?.message||'Применяем настройки двигателя…')}</p></>:
    waiting?<p role="status">{t('Включится после завершения ответа и очереди. Можно отменить повторным нажатием.')}</p>:
    measure?.turbo_tok_s?<div className="turbo-result"><strong>+{fmt(measure.gain_percent)}%</strong><span>{fmt(measure.baseline_tok_s)} → {fmt(measure.turbo_tok_s)} {t('ток/с')}<small>{t('В контрольном замере на этом ПК')}</small></span></div>:
    <p>{t('Первый запуск: короткий замер нескольких профилей, около 2–4 минут. Сохраняем только подтверждённое ускорение.')}</p>}
   <p className="turbo-footnote">{t('Оптимизация потоков CPU, пакетов GPU и MTP. Модель и окно контекста сохраняются. Результат зависит от задачи.')}</p>
   {on&&<div className="turbo-active"><i/>{t('Работает с ускоренными настройками')}</div>}
   {(error||state?.phase==='error'||(!working&&!waiting&&state?.message))&&<p className="turbo-notice" role="status">{t(error||state.message)}</p>}
   {working&&<button className="turbo-cancel" onClick={toggle} disabled={sending}><X size={12}/>{t('Отменить замер')}</button>}
  </>}
 </div>;
}
