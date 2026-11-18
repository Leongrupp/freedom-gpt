import React,{useEffect,useState} from 'react';
import {ShieldCheck,RefreshCw,Wrench} from 'lucide-react';
import {api} from './api.js';
import './self-repair.css';

export default function SelfRepairSettings(){
 const [state,setState]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let gone=false;const load=()=>api('/self-repair').then(v=>!gone&&setState(v)).catch(e=>!gone&&setError(e.message));load();const timer=setInterval(load,5000);return()=>{gone=true;clearInterval(timer)}},[]);
 async function action(path,body={}){setBusy(true);setError('');try{setState(await api('/self-repair/'+path,{method:'POST',body:JSON.stringify(body)}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <section className="self-repair-settings"><div className="self-repair-heading"><ShieldCheck size={20}/><div><h3>Самодиагностика и восстановление</h3><p>Freedom проверяет связь, модель и службы. После повторяющегося сбоя пробует штатное восстановление и ограничивает число попыток.</p></div></div>
  {state&&<><label className="self-repair-toggle"><input type="checkbox" checked={state.automatic} disabled={busy} onChange={e=>action('settings',{automatic:e.target.checked})}/> Автоматическое безопасное восстановление</label><div className="self-repair-actions"><button disabled={busy||state.phase==='repairing'} onClick={()=>action('diagnose')}><RefreshCw size={14}/> Проверить</button><button disabled={busy||state.phase==='repairing'} onClick={()=>action('repair')}><Wrench size={14}/>{state.phase==='repairing'?'Восстанавливаем…':'Попробовать восстановить'}</button></div>
  <small>Чаты и неопределённые задания не перезапускаются. При занятой модели восстановление её службы откладывается. Python-компоненты при запуске проверяет существующее офлайн-восстановление.</small>
  {state.checked_at&&<p className="self-repair-time">Проверено: {new Date(state.checked_at*1000).toLocaleString('ru-RU')}</p>}
  <div className="self-repair-checks">{state.checks?.map(c=><div key={c.id} data-state={c.state}><i/><span><strong>{c.name}</strong><small>{c.detail}</small></span></div>)}</div>
  {state.busy_reason&&<p className="self-repair-time">{state.busy_reason}</p>}
  {!!state.history?.length&&<details><summary>Журнал восстановления · {state.history.length}</summary>{[...state.history].reverse().map((r,i)=><div className="self-repair-event" key={i}><strong>{r.action}</strong><time>{new Date(r.at*1000).toLocaleString('ru-RU')}</time><p>{r.message}</p></div>)}</details>}</>}
  {error&&<p role="alert" className="self-repair-error">{error}</p>}
 </section>;
}
