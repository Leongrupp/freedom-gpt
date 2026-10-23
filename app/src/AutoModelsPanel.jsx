import React,{useEffect,useState} from 'react';
import {WandSparkles,ChevronDown,Check,LoaderCircle} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';
import './auto-models.css';
export const roleName=role=>t(({planning:'План и сценарий',code:'Написание кода',review:'Проверка результата',image:'Изображения',video:'Видео'})[role]||role);
export function AutoModelsPanel({sid,current,onChanged}){
 const[data,setData]=useState(null),[open,setOpen]=useState(current?.startsWith('freedom-auto-')),[policy,setPolicy]=useState(null),[working,setWorking]=useState(false),[error,setError]=useState(''),[confirm,setConfirm]=useState(null);
 useEffect(()=>{if(sid)api('/sessions/'+sid+'/auto').then(value=>{setData(value);setPolicy(value.policy)}).catch(e=>setError(e.message))},[sid]);
 const models=data?.models||[],active=current?.startsWith('freedom-auto-');
 function changePool(id,checked){setPolicy(value=>{const allowed=checked?[...value.allowed,id]:value.allowed.filter(x=>x!==id);return {...value,allowed,roles:Object.fromEntries(Object.entries(value.roles).map(([role,model])=>[role,model==='auto'||allowed.includes(model)?model:'auto']))}})}
 function paidChange(checked){setPolicy(value=>{const allowed=checked?value.allowed:value.allowed.filter(id=>!models.find(x=>x.id===id)?.paid);return {...value,allow_paid:checked,allowed,roles:Object.fromEntries(Object.entries(value.roles).map(([role,model])=>[role,model==='auto'||allowed.includes(model)?model:'auto']))}})}
 async function save(enabled,confirmation){setWorking(true);setError('');try{const result=await api('/sessions/'+sid+'/auto',{method:'POST',body:JSON.stringify({enabled,policy,confirm:confirmation})});if(result.status==='confirmation_required')setConfirm({enabled,result});else await onChanged()}catch(e){setError(e.message)}finally{setWorking(false)}}
 return <section className={'auto-models-panel '+(active?'selected':'')}>
  <button className="auto-models-choice" onClick={()=>setOpen(!open)} aria-expanded={!!open}><WandSparkles size={21}/><span><strong>{t('Авто · агент выбирает модели')}</strong><small>{t('План, код, изображения и видео в одном чате')}</small></span>{active?<Check size={16}/>:<ChevronDown size={15}/>}</button>
  {open&&<div className="auto-models-settings"><p>{t('Агент выбирает модель для этапа. Можно закрепить свои модели по ролям. Переписка, файлы и цель остаются общими.')}</p>
   {policy&&<><div className="auto-role-grid">{Object.entries(policy.roles).map(([role,model])=><label key={role}>{roleName(role)}<select value={model} onChange={e=>setPolicy({...policy,roles:{...policy.roles,[role]:e.target.value}})}><option value="auto">{t('На усмотрение агента')}</option>{models.filter(x=>x.roles.includes(role)&&x.available&&policy.allowed.includes(x.id)).map(x=><option key={x.id} value={x.id}>{x.name}{x.paid?' · '+t('Платный API'):''}</option>)}</select></label>)}</div>
   <label className="auto-paid-consent"><input type="checkbox" checked={policy.allow_paid} onChange={e=>paidChange(e.target.checked)}/><span>{t('Разрешить агенту платные API из выбранного списка')}<small>{t('Полный доступ сам по себе не разрешает оплату. Запросы оплачиваются по тарифам провайдера.')}</small></span></label>
   <details className="auto-pool"><summary>{t('Разрешённые модели')} <span>{policy.allowed.length}</span></summary><div>{models.map(model=><label key={model.id}><input type="checkbox" checked={policy.allowed.includes(model.id)} disabled={!model.available||model.paid&&!policy.allow_paid} onChange={e=>changePool(model.id,e.target.checked)}/><span>{model.name}<small>{model.paid?t('Платный API'):model.kind==='local'?t('На этом компьютере'):t('Бесплатный лимит')}{!model.available?' · '+t('Модель не скачана'):''}</small></span></label>)}</div></details>
   <label className="auto-media-limit">{t('Медиагенераций в этом чате, максимум')}<input type="number" min="1" max="100" value={policy.media_limit} onChange={e=>setPolicy({...policy,media_limit:Number(e.target.value)})}/></label>
   <p className="auto-footnote">{t('Для самостоятельной смены ролей и создания медиа нужен Полный доступ. В режиме с подтверждениями выбирайте этапы вручную. Подбор использует возможности и доступность моделей; скорость и качество зависят от задачи.')}</p>
   <div className="auto-save-actions"><button className="primary-button" disabled={working||!sid||data?.running} onClick={()=>save(true)}>{working?<LoaderCircle size={14} className="spin"/>:<WandSparkles size={14}/>} {t(active?'Сохранить настройки Авто':'Включить Авто')}</button>{active&&<button disabled={working||data?.running} onClick={()=>save(false)}>{t('Вернуться к ручному выбору')}</button>}</div>
   {!!data?.events?.length&&<details className="auto-stage-history"><summary>{t("История выбора моделей")}</summary>{data.events.map((event,i)=><div key={i}><strong>{roleName(event.role)}</strong> · {models.find(x=>x.id===event.model)?.name||event.model}<time>{new Date(event.created*1000).toLocaleString()}</time>{event.detail}</div>)}</details>}
   {confirm&&<div className="warning-card"><p>{confirm.result.confirm_message||confirm.result.message}</p><button onClick={()=>save(confirm.enabled,confirm.result.confirm||confirm.result.confirmation?.confirm)}>{t('Подтвердить переключение')}</button></div>}</>}
  </div>}
  {error&&<p role="alert" className="panel-error">{t(error)}</p>}
 </section>;
}
