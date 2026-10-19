import React,{useEffect,useState} from 'react';
import {Check,AlertCircle,Cpu,RefreshCw,Package} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
export function SystemSetup(){
 const[data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let disposed=false;async function load(){try{const value=await api('/system');if(!disposed){setData(value);setError('')}}catch(e){if(!disposed)setError(e.message)}}load();const timer=setInterval(load,3000);return()=>{disposed=true;clearInterval(timer)}},[]);
 async function run(action){setBusy(true);setError('');try{setData(await api('/system/'+action,{method:'POST',body:'{}'}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 const checking=busy||['idle','checking','repairing'].includes(data?.state),device=data?.hardware||{};
 return <details className="system-setup"><summary><Package size={16}/><strong>{t('Компоненты и готовность ПК')}</strong><span className={data?.ready?'system-ready':''}>{checking?t('Проверяем…'):data?.ready?t('Основные компоненты готовы'):t('Нужна проверка')}</span></summary>
 <div className="system-setup-body"><p>{t('Python, агент и локальные движки входят в сборку. Глобальная установка Python и Ollama не нужна.')}</p>{device.os&&<small>{device.os} · {device.architecture} · {t('Движок чата')}: {data.text_backend||'—'}</small>}
 {error&&<div className="library-error" role="alert">{t(error)}</div>}{data?.error&&<div className="library-error" role="alert">{t(data.error)}</div>}
 <div className="system-components">{data?.components?.map(item=><div key={item.id}>{item.state==='ready'?<Check size={14}/>:item.required?<AlertCircle size={14}/>:<Cpu size={14}/>}<span>{t(item.name)}<small>{t(item.detail)}</small></span><b>{t(item.state==='ready'?'Готово':item.state==='optional'?'По необходимости':'Не найдено')}</b></div>)}</div>
 {data?.driver_note&&<p>{t(data.driver_note)}</p>}<div className="system-actions"><button disabled={checking} onClick={()=>run('check')}><RefreshCw size={13} className={checking?'spin':''}/>{t('Проверить ещё раз')}</button><button disabled={checking} onClick={()=>run('repair')}>{t('Восстановить библиотеки Python')}</button></div></div></details>
}
