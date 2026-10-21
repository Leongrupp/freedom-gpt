import React, {useEffect, useRef, useState} from 'react';
import {Target, Check, RefreshCw, Save, CircleCheck, Flag, History, RotateCcw, Plus} from 'lucide-react';
import {api} from './api.js';
import {t, getLocale} from './i18n.js';
import {formatTime} from './WorkspacePanels.jsx';
import './goal.css';

const stepCount=value=>{
  const n=Number(value)||0;
  if(getLocale()==='en')return `${n} ${n===1?'step':'steps'}`;
  const unit=n%10===1&&n%100!==11?'шаг':n%10>=2&&n%10<=4&&(n%100<12||n%100>14)?'шага':'шагов';
  return `${n} ${unit}`;
};
const empty={objective:'',verification:'',constraints:''};
const liveGoal=state=>['active','paused'].includes(state?.goal?.status)?state.goal:null;
const statusLabel=goal=>!goal?t('Не включена'):goal.status==='paused'?t('На паузе'):goal.wait_barrier?t('Ожидает результат'):t('Активна');
const nativeFields=goal=>goal?{objective:goal.title.replace(/^Задание владельца (?:--|—|-)\s*/,''),verification:goal.contract?.verification||'',constraints:goal.contract?.constraints||''}:empty;
const editorFields=state=>state?.goal?.status==='active'?nativeFields(state.goal):state?.draft?.fields?.objective?state.draft.fields:nativeFields(liveGoal(state));
const formKey=state=>[state?.goal?.created_at||'',state?.goal?.status||'',state?.draft?.revision||0].join(':');

export function GoalButton({state,onClick}) {
  const goal=liveGoal(state),active=goal?.status==='active',count=state?.history?.length||0;
  return <button className={'goal-button '+(active?'is-active':'')} onClick={onClick} title={t('Цель проекта: результат и самостоятельное продолжение')}>
    <Target size={13}/><span>{t('Цель')}</span>{goal?<><i className={'goal-dot '+goal.status}/><span className="goal-chip-status">{statusLabel(goal)}</span></>:count>0?<><History size={11}/><span className="goal-chip-status">{count}</span></>:null}
  </button>;
}

export function GoalPanel({sid,state,onChanged,workBusy}) {
  const [current,setCurrent]=useState(state),[fields,setFields]=useState(()=>editorFields(state));
  const [working,setWorking]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [composing,setComposing]=useState(false);
  const mounted=useRef(true),dirty=useRef(false),stateKey=useRef('');
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[]);
  useEffect(()=>{
    if(!state)return;
    const key=formKey(state);
    setCurrent(state);
    if(key!==stateKey.current&&!dirty.current){setFields(editorFields(state));if(state.goal?.status==='done')setComposing(false)}
    stateKey.current=key;
  },[state]);
  const goal=liveGoal(current),active=goal?.status==='active',draft=current?.draft,history=current?.history||[];
  const showEditor=!!goal||!history.length||composing||!!fields.objective;
  const length=Object.values(fields).reduce((n,s)=>n+s.length,0);
  const changed=dirty.current||JSON.stringify(fields)!==JSON.stringify(draft?.fields?.objective?draft.fields:nativeFields(goal));
  function adopt(data,syncFields=false){
    if(!mounted.current)return;
    setCurrent(data);onChanged(data);
    if(syncFields||!dirty.current){setFields(editorFields(data));dirty.current=false}
    stateKey.current=formKey(data);
  }
  async function refresh(){setWorking(true);setError('');try{adopt(await api('/sessions/'+sid+'/goal'))}catch(e){if(mounted.current)setError(e.message)}finally{if(mounted.current)setWorking(false)}}
  useEffect(()=>{refresh()},[sid]);
  async function action(name,historyId) {
    setWorking(true);setError('');setNotice('');
    try {
      let data=current;
      if(name==='save'||name==='activate') {
        data=await api('/sessions/'+sid+'/goal',{method:'POST',body:JSON.stringify({action:'save',fields,draft_revision:draft?.revision||0})});
        dirty.current=false;adopt(data,true);
      }
      if(name!=='save')data=await api('/sessions/'+sid+'/goal',{method:'POST',body:JSON.stringify({action:name,revision:data?.revision||'',draft_revision:data?.draft?.revision||0,history_id:historyId})});
      adopt(data,['activate','repeat','resume'].includes(name));
      if(['activate','repeat','resume'].includes(name))setComposing(false);
      if(mounted.current)setNotice(name==='save'?t('Описание сохранено. Цель пока выключена.'):name==='pause'?t('Пауза включена. Уже принятое задание может завершиться; новых шагов по цели не будет.'):name==='recover'?t('Подтверждение исходного запуска восстановлено. Цель остаётся на паузе.'):name==='apply_engine'?t('Обновление движка применено. Можно включать цель.'):name==='repeat'?t('Цель активирована повторно. Агент заново проверит результат в этом чате.'):t('Цель включена. Прогресс появится в этом чате.'));
    }catch(e){
      if(mounted.current){setError(e.message);try{adopt(await api('/sessions/'+sid+'/goal'))}catch{}}
    }finally{if(mounted.current)setWorking(false)}
  }
  const edit=(key,value)=>{setFields(old=>({...old,[key]:value}));dirty.current=true;setNotice('')};
  return <div className="goal-panel">
    <div className="goal-intro"><div className="goal-mark"><Target size={26}/></div><div><h3>{t('Задайте результат. Агент продолжит сам.')}</h3><p>{t('После каждого шага он сверяется с целью, проверяет готовность и берёт следующий шаг.')}</p></div></div>
    {!showEditor&&<button className="goal-new-button" type="button" onClick={()=>setComposing(true)}><Plus size={15}/>{t('Новая цель')}</button>}
    {current?.engine&&!current.engine.ready&&<div className="goal-engine-note"><div><RefreshCw size={16}/><strong>{t('Осталось применить обновление движка')}</strong></div><p>{t('Текущие задания продолжаются. Для надёжной паузы цели нужен штатный перезапуск свободного агента. Модель остаётся загруженной.')}</p><button type="button" className="secondary-panel-button" disabled={working||current.engine.pending!==0} onClick={()=>action('apply_engine')}><RefreshCw size={14}/>{t('Применить обновление движка')}</button>{current.engine.pending>0&&<small>{t('Агент занят. Завершите текущие задания и обновите состояние.')}</small>}</div>}
    {showEditor&&<>
    <div className="goal-activation"><div><strong>{t('Работать по цели')}</strong><span>{statusLabel(goal)}</span></div><button type="button" className={'toggle '+(active?'on':'')} role="switch" aria-label={t('Работать по цели')} aria-checked={active} disabled={working||(!active&&(workBusy||!fields.objective.trim()||length>1900||current?.unavailable||!current?.engine?.ready))} onClick={()=>action(active?'pause':goal?.status==='paused'&&!changed?'resume':'activate')}><span/></button></div>
    <div className="goal-fields">
      <label>{t('К чему нужно прийти')}<textarea autoFocus rows={3} disabled={active||working} placeholder={t('Например: закончить локальный планировщик задач и подготовить его к использованию.')} value={fields.objective} maxLength={1900} onChange={e=>edit('objective',e.target.value)}/></label>
      <label>{t('Как понять, что всё готово')}<textarea rows={2} disabled={active||working} placeholder={t('Перечислите проверяемые результаты: что должно открываться, работать и быть сохранено.')} value={fields.verification} maxLength={1900} onChange={e=>edit('verification',e.target.value)}/></label>
      <details><summary>{t('Ограничения и важные условия')}</summary><textarea aria-label={t('Ограничения и важные условия')} rows={2} disabled={active||working} placeholder={t('Например: работать только в папке проекта, сохранять существующие данные.')} value={fields.constraints} maxLength={1900} onChange={e=>edit('constraints',e.target.value)}/></details>
      <span className={'goal-length '+(length>1900?'over':'')}>{length} / 1900</span>
    </div>
    {goal&&<section className="goal-progress" aria-label={t('Состояние цели')}><div><span><Flag size={14}/>{statusLabel(goal)}</span><strong>{stepCount(goal.turns_used)}</strong></div><p>{t('Количество шагов не ограничено.')}</p>{(goal.paused_reason||goal.last_reason||goal.wait_barrier?.reason)&&<div className="goal-verdict"><Target size={15}/><span>{goal.wait_barrier?.reason||goal.last_reason||goal.paused_reason}</span></div>}{goal.paused_reason&&goal.last_reason&&<small>{goal.paused_reason}</small>}{!!goal.subgoals?.length&&<ul>{goal.subgoals.map((item,index)=><li key={index}>{item}</li>)}</ul>}{goal.updated_at&&<time>{t('Обновлено')} {formatTime(goal.updated_at)}</time>}</section>}
    <details className="goal-help"><summary>{t('Как работает цель')}</summary><div><p>{t('Цель и прогресс хранятся на этом ПК и переживают сжатие контекста. Можно закрыть окно панели; компьютер и локальный движок должны оставаться включёнными.')}</p><p>{t('Агент продолжает до достижения цели, ручной паузы или препятствия. Лимита шагов нет. После завершения цель появляется в истории — её можно повторить.')}</p><p>{t('Используется текущий режим доступа чата. Для изменения активной цели сначала выключите переключатель.')}</p>{workBusy&&!active&&<p className="goal-busy-hint">{t('Включить цель можно после завершения текущего задания и очереди.')}</p>}</div></details>
    </>}
    <div className="goal-actions"><button type="button" className="secondary-panel-button" disabled={working} onClick={refresh}><RefreshCw size={14}/>{t('Обновить состояние')}</button>{!active&&showEditor&&<button type="button" className="primary-button" disabled={working||!fields.objective.trim()||length>1900} onClick={()=>action('save')}><Save size={14}/>{t('Сохранить описание')}</button>}</div>
    {!!history.length&&<section className="goal-history" aria-label={t('История целей')}><header><History size={15}/><h3>{t('История целей')}</h3><span>{history.length}</span></header><p>{t('Если результат не готов, нажмите «Повторить». Агент вернётся к цели с сохранённым контекстом.')}</p>{history.map(item=><article className="goal-history-item" key={item.id}><div className="goal-history-main"><CircleCheck size={17}/><div><strong>{item.title}</strong><div className="goal-history-meta"><span>{formatTime(item.goal.updated_at||item.completed)}</span><span>·</span><span>{stepCount(item.goal.turns_used)}</span>{item.reopen_count>0&&<span>· {t('Повторов:')} {item.reopen_count}</span>}</div></div><button type="button" className="goal-repeat" disabled={working||workBusy||!!goal||!current?.engine?.ready} onClick={()=>action('repeat',item.id)} aria-label={t('Повторить цель')+' '+item.title}><RotateCcw size={13}/>{t('Повторить')}</button></div><details><summary>{t('Подробнее')}</summary><p>{item.fields.objective}</p>{item.fields.verification&&<p>{item.fields.verification}</p>}{item.fields.constraints&&<p>{item.fields.constraints}</p>}{item.goal.last_reason&&<p className="goal-history-reason">{item.goal.last_reason}</p>}</details></article>)}</section>}
    {notice&&<p className="goal-notice" role="status"><Check size={14}/>{notice}</p>}{error&&<p className="panel-error" role="alert">{t(error)}</p>}{current?.start_uncertain&&<div className="panel-error"><p>{t('Запуск не подтверждён. Повтор заблокирован, чтобы не создать две одинаковые задачи.')}</p><button className="secondary-panel-button" disabled={working} onClick={()=>action('recover')}>{t('Восстановить подтверждение запуска')}</button></div>}
  </div>;
}
