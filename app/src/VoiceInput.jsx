import React,{useEffect,useRef,useState} from 'react';
import {Mic,Square,X,LoaderCircle,Check,RotateCcw,FileText} from 'lucide-react';
import {api} from './api.js';
import {openMicrophone} from './microphoneSource.js';
import {localStore} from './browserStorage.js';
import {t} from './i18n.js';
import {saveVoice,clearVoice,loadVoice} from './voice-storage.js';
import './voice-input.css';

const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const clock=value=>Math.floor(value/60)+':'+String(value%60).padStart(2,'0');
export function VoiceInput({enabled,ready,busy,disabled,getContext,onTask,onInsert}){
 const[phase,setPhase]=useState('idle'),[open,setOpen]=useState(false),[seconds,setSeconds]=useState(0),[error,setError]=useState(''),[job,setJob]=useState(null);
 const alive=useRef(true),recorder=useRef(null),stream=useRef(null),chunks=useRef([]),startAt=useRef(0),holdAt=useRef(0),pointer=useRef(false),cancelled=useRef(false),operation=useRef(0),jobRef=useRef(null),callbacks=useRef(null),phaseRef=useRef('idle'),micClaimed=useRef(false);
 callbacks.current={getContext,onTask,onInsert};phaseRef.current=phase;
 function remember(value){jobRef.current=value;setJob(value);return saveVoice(value)}
 function release(){stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;if(micClaimed.current){micClaimed.current=false;window.dispatchEvent(new CustomEvent('freedom-mic-release',{detail:{owner:'dictation'}}))}}
 useEffect(()=>{const claimed=e=>{if(e.detail?.owner==='jarvis'&&['permission','recording'].includes(phaseRef.current))cancel().catch(()=>{})};window.addEventListener('freedom-mic-claim',claimed);return()=>window.removeEventListener('freedom-mic-claim',claimed)},[]);
 useEffect(()=>{alive.current=true;loadVoice().then(value=>{if(value&&alive.current&&phaseRef.current==='idle'&&!jobRef.current){jobRef.current=value;setJob(value);setPhase('saved')}});return()=>{
  alive.current=false;operation.current++;cancelled.current=true;
  if(recorder.current?.state==='recording')recorder.current.stop();release();
 }},[]);
 useEffect(()=>{if(phase!=='recording')return;const timer=setInterval(()=>{
  const value=Math.floor((Date.now()-startAt.current)/1000);setSeconds(value);if(value>=300)stop();
 },250);return()=>clearInterval(timer)},[phase]);
 useEffect(()=>{if(phase!=='sent')return;const timer=setTimeout(()=>{setOpen(false);setPhase('idle');setJob(null);jobRef.current=null},4500);return()=>clearTimeout(timer)},[phase]);

 async function process(value){
  const epoch=++operation.current;setError('');setPhase('processing');setOpen(true);
  try{
   const body=new FormData();body.append('audio',value.blob,'voice-recording');
   let result=await api('/voice/transcriptions/'+value.id,{method:'POST',body});
   const deadline=Date.now()+360000;
   while(['queued','working'].includes(result.state)){
    if(!alive.current||epoch!==operation.current)return;
    if(Date.now()>deadline)throw new Error(t('Запись сохранена. Повторите проверку распознавания.'));
    await pause(1200);result=await api('/voice/transcriptions/'+value.id);
   }
   if(!alive.current||epoch!==operation.current)return;
   if(result.state!=='ready')throw new Error(result.error||t('Запись отменена. Запишите задание ещё раз.'));
   value={...value,text:result.text};await remember(value);
   if(!alive.current||epoch!==operation.current)return;
   if(result.admission_id){await clearVoice(value.id);setPhase('sent');return}
   setPhase('sending');
   await callbacks.current.onTask({id:value.id,text:result.text,context:value.context,
    bind:async sid=>{value={...value,context:{...value.context,sid,chatKey:sid}};await remember(value)}});
   if(!alive.current)return;
   await clearVoice(value.id);setPhase('sent');
  }catch(e){if(alive.current&&epoch===operation.current){setError(e.message);setPhase('saved')}}
 }

 async function start(){
  if(!enabled||disabled||!['idle','sent'].includes(phaseRef.current))return;
  setOpen(true);setError('');
  if(!ready){setError(t('Локальное распознавание ещё не готово.'));return}
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){
   setError(t('Для микрофона откройте панель по HTTPS или на этом ПК через localhost.'));return;
  }
  cancelled.current=false;setPhase('permission');
  micClaimed.current=true;window.dispatchEvent(new CustomEvent('freedom-mic-claim',{detail:{owner:'dictation'}}));
  const context=callbacks.current.getContext();
  try{
   let microphone='auto';try{microphone=JSON.parse(localStore.getItem('freedom-jarvis')||'{}').microphone||'auto'}catch{}
   const audio=await openMicrophone(microphone);
   if(!alive.current||cancelled.current){audio.getTracks().forEach(track=>track.stop());return}
   stream.current=audio;chunks.current=[];
   const mime=['audio/webm;codecs=opus','audio/mp4','audio/webm'].find(value=>MediaRecorder.isTypeSupported(value));
   const device=new MediaRecorder(audio,mime?{mimeType:mime}:undefined);recorder.current=device;
   device.ondataavailable=event=>{if(event.data.size)chunks.current.push(event.data)};
   device.onerror=()=>{release();setPhase('idle');setError(t('Не удалось записать звук. Проверьте доступ к микрофону.'))};
   device.onstop=async()=>{
    release();if(cancelled.current||!alive.current)return;
    const blob=new Blob(chunks.current,{type:device.mimeType||mime||'audio/webm'});
    if(!blob.size){setPhase('idle');setError(t('Запись пустая. Повторите диктовку.'));return}
    const value={id:crypto.randomUUID().replaceAll('-',''),blob,context,created:Date.now()};
    await remember(value);if(alive.current)process(value);
   };
   startAt.current=Date.now();setSeconds(0);device.start(500);setPhase('recording');
  }catch(e){release();if(alive.current){setPhase('idle');setError(t(e.name==='NotAllowedError'?'Разрешите доступ к микрофону в браузере.':'Не удалось включить микрофон. Проверьте, подключён ли он.'))}}
 }
 function stop(){if(recorder.current?.state==='recording'){phaseRef.current='processing';setPhase('processing');recorder.current.stop()}}
 async function cancel(){
  if(phaseRef.current==='sending'){setOpen(false);return}
  cancelled.current=true;operation.current++;
  if(recorder.current?.state==='recording')recorder.current.stop();release();
  const value=jobRef.current;
  if(value){await clearVoice(value.id);api('/voice/transcriptions/'+value.id+'/discard',{method:'POST',body:'{}'}).catch(()=>{})}
  jobRef.current=null;setJob(null);setPhase('idle');setError('');setOpen(false);
 }
 function toggle(){if(phaseRef.current==='recording')stop();else if(['idle','sent'].includes(phaseRef.current))start();else setOpen(value=>!value)}
 if(!enabled)return null;
 const working=['processing','sending','permission'].includes(phase),recording=phase==='recording';
 const title=t(recording?'Остановить запись и отправить':busy?'Надиктовать следующее задание':'Надиктовать задание');
 return <div className={'voice-input'+(recording?' is-recording':'')}>
  <button className="icon-button voice-mic" disabled={disabled} aria-label={title} title={title+' · '+t('Нажмите или удерживайте микрофон')} aria-pressed={recording}
   onContextMenu={e=>e.preventDefault()}
   onPointerDown={e=>{if(e.button!==0)return;e.preventDefault();pointer.current=true;holdAt.current=Date.now();e.currentTarget.setPointerCapture?.(e.pointerId);if(['idle','sent'].includes(phaseRef.current))start();else if(phaseRef.current==='recording')stop();else setOpen(value=>!value)}}
   onPointerUp={()=>{if(Date.now()-holdAt.current>450&&phaseRef.current==='recording')stop()}}
   onPointerCancel={()=>{if(phaseRef.current==='recording')cancel()}}
   onClick={e=>{if(e.detail){pointer.current=false;return}toggle()}}>
   {working?<LoaderCircle size={18} className="spin"/>:phase==='sent'?<Check size={18}/>:<Mic size={19}/>}
  </button>
  {open&&<div className="voice-popover" role="region" aria-label={t('Голосовое задание')}>
   <header><strong>{t(recording?'Слушаю вас':phase==='sent'?'Задание отправлено':phase==='saved'?'Запись сохранена':'Голосовое задание')}</strong><button className="icon-button" aria-label={t('Скрыть голосовую панель')} onClick={()=>setOpen(false)}><X size={14}/></button></header>
   {recording?<><div className="voice-record-clock"><i/>{clock(seconds)}</div><p>{t('Говорите своими словами. После остановки задание отправится в этот чат.')}</p></>:
    working?<p className="voice-working"><LoaderCircle size={15} className="spin"/>{t(phase==='permission'?'Разрешите микрофон в браузере':phase==='sending'?'Передаю задание агенту…':'Расшифровываю на вашем ПК…')}</p>:
    !error&&phase==='idle'?<p>{t('Нажмите микрофон и говорите. Можно удерживать кнопку до конца фразы.')}</p>:null}
   {job?.text&&<p className="voice-transcript">{job.text}</p>}
   {error&&<p role="alert" className="voice-error">{t(error)}</p>}
   {phase==='saved'&&!error&&<p>{t('Можно продолжить распознавание и отправку. Повторного задания не появится.')}</p>}
   <div className="voice-actions">
    {recording&&<button className="voice-primary" onClick={stop}><Square size={12}/>{t('Стоп и отправить')}</button>}
    {phase==='saved'&&<button className="voice-primary" onClick={()=>process(jobRef.current)}><RotateCcw size={13}/>{t('Продолжить отправку')}</button>}
    {job?.text&&phase==='saved'&&<button onClick={async()=>{callbacks.current.onInsert(job.text);await cancel()}}><FileText size={13}/>{t('Вставить текст')}</button>}
    {phase!=='sent'&&<button onClick={cancel}>{t(phase==='sending'?'Скрыть':'Отмена')}</button>}
   </div>
   <small>{t('Локально · без оплаты за минуты')}</small>
  </div>}
 </div>;
}
