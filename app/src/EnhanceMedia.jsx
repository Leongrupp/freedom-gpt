import React,{useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {createPortal} from 'react-dom';
import {Sparkles,X,Download,ArrowRight,LoaderCircle,Square,Check,Image as ImageIcon,Video} from 'lucide-react';
import {api} from './api.js';
import {t,useLocale} from './i18n.js';
import './enhance-media.css';

const active=new Set(['queued','preparing','waiting','upscaling','interpolating','encoding','verifying']);
const phases={queued:'В очереди',preparing:'Готовим файлы',waiting:'Ожидаем видеокарту',upscaling:'Улучшаем детали',interpolating:'Добавляем плавность',encoding:'Собираем видео',verifying:'Проверяем результат',complete:'Готово',cancelled:'Остановлено',interrupted:'Прервано',error:'Не удалось улучшить'};
let state={enabled:false,selection:null},currentSid='';
const listeners=new Set(),subscribe=fn=>{listeners.add(fn);return()=>listeners.delete(fn)},snapshot=()=>state;
const change=patch=>{state={...state,...patch};for(const fn of listeners)fn()};
function open(file,sid,jobId){change({selection:{file,sid:sid||currentSid,jobId,key:crypto.randomUUID()}})}
export function EnhanceButton({file,sid}){
 const {enabled}=useSyncExternalStore(subscribe,snapshot);
 if(!enabled||!file?.url||!(/^image\/(png|jpeg|webp|bmp|tiff)$|^video\//.test(file.mime||'')))return null;
 return <button type="button" className="enhance-button" onClick={()=>open(file,sid)} title={t('Улучшить качество локально')}><Sparkles size={13}/><span>{t('Улучшить')}</span></button>;
}
function Compare({job}){
 const[split,setSplit]=useState(50),left=useRef(null),right=useRef(null);
 const sync=()=>{if(left.current&&right.current&&Math.abs(left.current.currentTime-right.current.currentTime)>.12)right.current.currentTime=left.current.currentTime};
 if(job.kind==='video')return <div className="enhance-videos"><div><small>{t('До')}</small><video ref={left} src={job.before_url} controls playsInline preload="metadata" onPlay={()=>{sync();right.current?.play()?.catch(()=>{})}} onPause={()=>right.current?.pause()} onSeeking={sync} onTimeUpdate={sync}/></div><div><small>{t('После')}</small><video ref={right} src={job.url} muted playsInline preload="metadata"/><p>{t('Воспроизведение синхронизировано с оригиналом')}</p></div></div>;
 return <div className="enhance-compare"><div className="enhance-split" style={{aspectRatio:job.width+'/'+job.height}}><img src={job.url} alt={t('После улучшения')}/><div style={{clipPath:`inset(0 ${100-split}% 0 0)`}}><img src={job.before_url} alt={t('До улучшения')}/></div><i style={{left:split+'%'}}/><span className="enhance-before">{t('До')}</span><span className="enhance-after">{t('После')}</span></div><label className="enhance-compare-control">{t('Сравнить до и после')}<input type="range" min="0" max="100" value={split} onChange={e=>setSplit(Number(e.target.value))}/></label></div>;
}
function EnhanceDialog({selection,data,onRefresh,onClose,onEnsureChat}){
 useLocale();
 const dialog=useRef(null),intent=useRef(null),[info,setInfo]=useState(null),[error,setError]=useState(''),[scale,setScale]=useState(2),[profile,setProfile]=useState('photo'),[smooth,setSmooth]=useState(false),[pending,setPending]=useState(false),[selected,setSelected]=useState(selection.jobId||null);
 const jobs=(data?.jobs||[]).filter(j=>j.source_url===selection.file.url||j.id===selected),job=jobs.find(j=>j.id===selected)||jobs[0],working=job&&active.has(job.state),video=info?.kind==='video';
 useEffect(()=>{const node=dialog.current;node.showModal();return()=>node.close()},[]);
 useEffect(()=>{let off=false;setError('');api('/enhance/source?url='+encodeURIComponent(selection.file.url)).then(value=>{if(!off)setInfo(value)}).catch(e=>{if(!off)setError(e.message)});return()=>{off=true}},[selection.file.url]);
 async function start(preview){
  setPending(true);setError('');
  const params={url:selection.file.url,sid:selection.sid,scale,profile,smooth:video&&smooth,preview};
  const signature=JSON.stringify(params);
  if(intent.current?.signature!==signature)intent.current={signature,id:crypto.randomUUID()};
  try{if(!params.sid&&!preview)params.sid=await onEnsureChat?.()||'';const result=await api('/enhance/jobs',{method:'POST',body:JSON.stringify({...params,request_id:intent.current.id})});setSelected(result.id);intent.current=null;await onRefresh()}
  catch(e){setError(e.message);if(!e.uncertain)intent.current=null;await onRefresh().catch(()=>{})}
  finally{setPending(false)}
 }
 async function cancel(){setPending(true);setError('');try{await api('/enhance/jobs/'+job.id+'/cancel',{method:'POST',body:'{}'});await onRefresh()}catch(e){setError(e.message)}finally{setPending(false)}}
 const tooLargeSource=info?.kind==='image'&&info.width*info.height>10000000;
 const invalid=tooLargeSource||!!info&&((video&&info.width*info.height*scale*scale>3840*2160)||info.width*info.height*scale*scale>64000000||Math.max(info.width,info.height)*scale>16384);
 const tools=Object.entries(data?.tools||{}).filter(([name])=>name==='esrgan'||smooth),downloading=tools.filter(([,v])=>['downloading','installing'].includes(v.state));
 return createPortal(<dialog ref={dialog} className="enhance-dialog" aria-labelledby="enhance-title" onCancel={e=>{e.preventDefault();onClose()}} onClick={e=>{if(e.target===e.currentTarget)onClose()}}><header><div className="enhance-heading"><span><Sparkles size={21}/></span><div><small>FREEDOM · ENHANCE</small><h2 id="enhance-title">{t('Больше деталей. Та же история.')}</h2></div></div><button type="button" className="icon-button" onClick={onClose} aria-label={t('Закрыть')}><X size={18}/></button></header>
 <div className="enhance-body"><div className="enhance-source"><span>{video?<Video size={17}/>:<ImageIcon size={17}/>}</span><div><strong>{selection.file.name||job?.source_name||t('Готовый файл')}</strong><small>{info?`${info.width} × ${info.height}${video?' · '+info.duration.toFixed(1)+' '+t('сек'):''}`:t('Читаем параметры файла…')}</small></div><span className="enhance-local">{t('На вашем ПК')}</span></div>
 <div className="enhance-options"><fieldset><legend>{t('Размер результата')}</legend><div className="enhance-segments">{[2,4].map(n=><button type="button" key={n} aria-pressed={scale===n} onClick={()=>setScale(n)}>×{n}<small>{info?`${info.width*n} × ${info.height*n}`:'—'}</small></button>)}</div></fieldset><fieldset><legend>{t('Тип изображения')}</legend><div className="enhance-segments">{[['photo','Фото и реализм'],['illustration','Иллюстрация и аниме']].map(([id,label])=><button type="button" key={id} aria-pressed={profile===id} onClick={()=>setProfile(id)}>{t(label)}</button>)}</div></fieldset></div>
 {video&&<label className="enhance-smooth"><input type="checkbox" checked={smooth} onChange={e=>setSmooth(e.target.checked)}/><span><strong>{t('Плавнее движения')}</strong><small>{t('RIFE добавит промежуточные кадры. Длительность и звук сохранятся.')}</small></span><span>RIFE</span></label>}
 <p className="enhance-note">{t('Real-ESRGAN восстанавливает детали в ×4; для ×2 результат уменьшается. Обработка может занять время. Исходный файл сохраняется.')}</p>
 {invalid&&<p className="enhance-error" role="alert">{t(tooLargeSource?'Для полного улучшения выберите исходник до 10 мегапикселей. Можно проверить центральный фрагмент кнопкой «Проба».':video?'Результат превышает 4K. Выберите ×2 или меньший исходник.':'Результат превышает 64 мегапикселя или 16384 пикселя по стороне.')}</p>}
 {tools.some(([,v])=>!v.ready)&&<div className="enhance-download-note"><Download size={15}/><span>{t('Первое улучшение скачает бесплатные локальные модули. Дальше можно без интернета.')} {tools.filter(([,v])=>!v.ready).map(([name,v])=>`${name==='esrgan'?'Real-ESRGAN':'RIFE'} ≈ ${Math.ceil(v.bytes/1024**2)} ${t('МБ')}`).join(' · ')}</span></div>}
 {!!downloading.length&&<div className="enhance-progress" role="status">{downloading.map(([name,v])=><div key={name}><span>{name==='esrgan'?'Real-ESRGAN':'RIFE'} · {t(v.state==='installing'?'Устанавливаем':'Загружаем')} {v.percent||0}%</span><progress max="100" value={v.percent||0}/></div>)}</div>}
 {working&&<div className="enhance-progress" role="status"><div className="enhance-progress-head"><LoaderCircle className="spin" size={17}/><strong>{t(phases[job.state])}</strong><span>{Math.round(job.progress||0)}%</span></div><progress max="100" value={job.progress||0}/>{job.reason&&<p>{t(job.reason)}</p>}{job.kind==='video'&&!!job.total_frames&&<small>{job.processed_frames||0} / {job.total_frames} {t('кадров')}</small>}<button type="button" disabled={pending} onClick={cancel}><Square size={12}/>{t('Отменить улучшение')}</button></div>}
 {job&&['error','interrupted'].includes(job.state)&&<p className="enhance-error" role="alert">{t(job.error||phases[job.state])}</p>}
 {job?.state==='cancelled'&&<p className="enhance-note">{t('Улучшение отменено. Исходный файл сохранён.')}</p>}
 {job?.state==='complete'&&<section className="enhance-result"><div className="enhance-result-title"><Check size={16}/><strong>{t(job.preview?'Пробный фрагмент готов':'Улучшение готово')}</strong><span>{job.width} × {job.height} · ×{job.scale}</span></div><Compare key={job.id} job={job}/><div className="enhance-result-actions"><a href={job.url} download={'Freedom-enhanced-x'+job.scale+(job.kind==='image'?'.png':'.mp4')}><Download size={14}/>{t('Скачать результат')}</a><small>{t(job.preview?'Это пример. Полное улучшение запустите ниже.':'Новая копия сохранена в файлах чата.')}</small></div></section>}
 {error&&<p className="enhance-error" role="alert">{t(error)}</p>}
 {!!jobs.length&&<details className="enhance-history"><summary>{t('Предыдущие улучшения')} · {jobs.length}</summary>{jobs.map(item=><button type="button" key={item.id} onClick={()=>setSelected(item.id)} aria-pressed={job?.id===item.id}><span>×{item.scale} · {t(item.preview?'Проба':'Полный файл')}{item.smooth?' · RIFE':''}</span><small>{t(phases[item.state])}</small></button>)}</details>}
 </div><footer><p>{t('Чат имеет приоритет. Можно закрыть окно — улучшение продолжится.')}</p><div><button type="button" className="enhance-preview-button" disabled={!info||(video&&invalid)||pending||working} onClick={()=>start(true)}>{t(video?'Проба · до 3 секунд':'Проба · фрагмент фото')}</button><button type="button" className="enhance-start-button" disabled={!info||invalid||pending||working} onClick={()=>start(false)}>{pending?<LoaderCircle size={15} className="spin"/>:<Sparkles size={15}/>} {t('Улучшить')}<ArrowRight size={14}/></button></div></footer></dialog>,document.body);
}
export function EnhanceCoordinator({enabled,sid,onEnsureChat}){
 const {selection}=useSyncExternalStore(subscribe,snapshot),[data,setData]=useState(null),[connectionError,setConnectionError]=useState(false),[finished,setFinished]=useState(null),previous=useRef(null),alive=useRef(true);
 const load=async()=>{const value=await api('/enhance/status');if(alive.current){setData(value);setConnectionError(false)}return value};
 useEffect(()=>{change({enabled:!!enabled});return()=>change({enabled:false,selection:null})},[enabled]);
 useEffect(()=>{currentSid=sid||''},[sid]);
 const working=(data?.jobs||[]).filter(j=>active.has(j.state));
 useEffect(()=>{if(!data)return;const jobs=data.jobs||[];if(previous.current){const done=jobs.find(j=>j.state==='complete'&&active.has(previous.current[j.id]));if(done)setFinished(done)}previous.current=Object.fromEntries(jobs.map(j=>[j.id,j.state]))},[data]);
 useEffect(()=>{if(selection)setFinished(null)},[selection]);
 useEffect(()=>{alive.current=true;if(!enabled)return;let off=false,timer;async function poll(){try{await load()}catch{if(!off)setConnectionError(true)}if(!off)timer=setTimeout(poll,selection||working.length?1400:10000)}poll();return()=>{off=true;alive.current=false;clearTimeout(timer)}},[enabled,!!selection,!!working.length]);
 if(!enabled)return null;
 return <>{selection&&<EnhanceDialog key={selection.key} selection={selection} data={data} onRefresh={load} onEnsureChat={onEnsureChat} onClose={()=>change({selection:null})}/>} {!selection&&!!working.length&&<button type="button" className="enhance-floating" onClick={()=>open({url:working[0].source_url,name:working[0].source_name},working[0].sid,working[0].id)}><LoaderCircle size={15} className="spin"/><span>{t('Улучшение медиа')} · {working.length>1?working.length:Math.round(working[0].progress||0)+'%'}</span></button>}{!selection&&!working.length&&finished&&<div className="enhance-floating enhance-finished" role="status"><button type="button" onClick={()=>open({url:finished.source_url,name:finished.source_name},finished.sid,finished.id)}><Check size={16}/>{t('Улучшение готово')}</button><button type="button" aria-label={t('Закрыть')} onClick={()=>setFinished(null)}><X size={13}/></button></div>}{connectionError&&selection&&<div className="enhance-connection" role="status">{t('Переподключаемся. Задание остаётся на ПК.')}</div>}</>;
}
