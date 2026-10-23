import React,{useEffect,useRef,useState} from 'react';
import {Video,ExternalLink,LoaderCircle,Download,RefreshCw,Square} from 'lucide-react';
import {api} from './api.js';
import {t} from './i18n.js';

const phases={queued:'В очереди',submitting:'Отправляем запрос',IN_QUEUE:'В очереди fal.ai',IN_PROGRESS:'Создаём видео',downloading:'Сохраняем MP4 на ПК',cancel_requested:'Остановка запрошена',paused:'Проверка статуса приостановлена',unknown:'Результат отправки неизвестен',failed:'Ошибка',cancelled:'Остановлено',completed:'Готово'};
export function FalVideoPanel({sid,onEnsureChat,onConnect}){
 const[data,setData]=useState(null),[prompt,setPrompt]=useState(''),[model,setModel]=useState('fal-ai/wan-25-preview/text-to-video'),[duration,setDuration]=useState('5'),[resolution,setResolution]=useState('480p'),[ratio,setRatio]=useState('16:9'),[confirm,setConfirm]=useState(false),[working,setWorking]=useState(false),[error,setError]=useState('');
 const intent=useRef(null),job=data?.current,selected=data?.models?.find(row=>row.id===model);
 const[sourceImage,setSourceImage]=useState('');
 async function load(){setData(await api('/cloud/videos'))}
 useEffect(()=>{let off=false;const poll=async()=>{try{const next=await api('/cloud/videos');if(!off)setData(next)}catch(e){if(!off)setError(e.message)}};poll();const timer=setInterval(poll,3000);return()=>{off=true;clearInterval(timer)}},[]);
 function change(setter,value){setter(value);setConfirm(false)}
 async function generate(e){e.preventDefault();setWorking(true);setError('');try{const targetSid=sid||await onEnsureChat?.();const body={sid:targetSid||'',model,prompt:prompt.trim(),duration,resolution,aspect_ratio:ratio,source_image:selected?.image_input?sourceImage:"",confirm_charge:confirm};const fingerprint=JSON.stringify(body);if(!intent.current||intent.current.fingerprint!==fingerprint)intent.current={fingerprint,id:crypto.randomUUID()};await api('/cloud/videos',{method:'POST',body:JSON.stringify({...body,input_id:intent.current.id})});setConfirm(false);await load()}catch(e){setError(e.message)}finally{setWorking(false)}}
 async function action(name){setWorking(true);setError('');try{await api('/cloud/videos/'+job.id+'/'+name,{method:'POST',body:'{}'});await load()}catch(e){setError(e.message)}finally{setWorking(false)}}
 const results=(data?.history||[]).filter(row=>row.state==='completed'),issues=(data?.history||[]).filter(row=>['unknown','failed'].includes(row.state));
 return <div className="fal-video-panel">
  <div className="api-quota"><Video size={17}/><p>{t('Видео создаётся на серверах fal.ai. Готовый MP4 сохраняется на вашем ПК и появляется в чате.')}</p></div>
  {!data?.connected&&<div className="fal-connect"><p>{t('Сначала подключите ключ fal.ai с пресетом API.')}</p>{onConnect&&<button className="primary-button" onClick={onConnect}>{t('Подключить fal.ai')}</button>}<a href="https://fal.ai/dashboard/keys" target="_blank" rel="noreferrer">{t('Получить API-ключ')} <ExternalLink size={12}/></a></div>}
  <form className="fal-video-form" onSubmit={generate}>
   <label>{t('Видеомодель')}<select value={model} onChange={e=>change(setModel,e.target.value)}>{(data?.models||[{id:model,name:'Wan 2.5'}]).map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
   {selected?.image_input&&<label>{t('Путь к исходному изображению на ПК')}<input value={sourceImage} onChange={e=>change(setSourceImage,e.target.value)} placeholder="A:\…\image.png"/></label>}
   <label>{t('Описание сцены')}<textarea aria-label={t('Описание видео fal.ai')} rows={4} maxLength={1500} value={prompt} onChange={e=>change(setPrompt,e.target.value)} placeholder={t('Опишите движение, сцену и положение камеры…')}/></label>
   <div className="fal-options"><label>{t('Длительность')}<select value={duration} onChange={e=>change(setDuration,e.target.value)}><option value="5">5 {t('сек')}</option><option value="10">10 {t('сек')}</option></select></label><label>{t('Разрешение')}<select value={resolution} onChange={e=>change(setResolution,e.target.value)}>{['480p','720p','1080p'].map(row=><option key={row}>{row}</option>)}</select></label><label>{t('Пропорции')}<select value={ratio} onChange={e=>change(setRatio,e.target.value)}>{['16:9','9:16','1:1'].map(row=><option key={row}>{row}</option>)}</select></label></div>
   <p className="api-privacy">{t('Стоимость зависит от параметров. Счётчик запросов не ограничивает расходы. Отмена уже начатой генерации не гарантирует возврат оплаты.')} <a href={selected?.pricing_url||'https://fal.ai/models/fal-ai/wan-25-preview/text-to-video'} target="_blank" rel="noreferrer">{t('Тариф модели')} ↗</a></p>
   <label className="api-checkbox"><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)}/><span>{t('Разрешаю один платный запуск с выбранными параметрами по тарифу fal.ai.')}</span></label>
   <button className="primary-button" disabled={!data?.connected||!prompt.trim()||selected?.image_input&&!sourceImage.trim()||!confirm||working||!!job}>{working?<LoaderCircle size={15} className="spin"/>:<Video size={15}/>} {t('Создать видео · платно')}</button>
   {intent.current&&<button type="button" className="api-refresh" disabled={working||!!job} onClick={()=>{intent.current=null;setConfirm(false)}}>{t('Новый запуск с тем же описанием')}</button>}
  </form>
  {job&&<section className="fal-job" aria-live="polite"><strong>{t(phases[job.state]||job.state)}</strong><p>{job.prompt}</p>{job.error&&<p className="api-error">{t(job.error)}</p>}<div>{job.state==='paused'&&<button disabled={working} onClick={()=>action('resume')}><RefreshCw size={13}/>{t('Проверить статус без нового запуска')}</button>}{!['queued','submitting'].includes(job.state)&&<button disabled={working} onClick={()=>action('cancel')}><Square size={13}/>{t('Запросить отмену')}</button>}</div></section>}
  {issues.map(row=><div className="api-error" key={row.id}><strong>{t(phases[row.state])}</strong><p>{row.error&&t(row.error)}</p>{row.state==='unknown'&&<p>{t('Не повторяйте запуск, пока не проверите запросы и списания в кабинете fal.ai.')}</p>}</div>)}
  {error&&<p className="api-error" role="alert">{t(error)}</p>}
  {!!results.length&&<section className="fal-results"><h4>{t('Готовые видео')}</h4>{results.map(row=><article key={row.id}><video src={row.url} controls playsInline preload="metadata"/><p>{row.prompt}</p><a href={row.url} download={'FreedomGPT-'+row.id.slice(0,8)+'.mp4'}><Download size={14}/>{t('Скачать MP4')}</a></article>)}</section>}
  <p className="api-privacy">{t('Описание отправляется fal.ai. Ссылки сервиса на готовые медиа могут быть публичными. Можно закрыть окно: задача и история сохраняются.')}{data?.usage&&<> · {data.usage.used} / {data.usage.cap} {t('запросов за день в приложении')}</>}</p>
 </div>;
}
