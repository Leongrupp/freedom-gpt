import React,{useEffect,useRef,useSyncExternalStore} from 'react';
import {Volume2,Play,Pause,Square,LoaderCircle,SlidersHorizontal,X,ChevronDown} from 'lucide-react';
import {api} from './api.js';
import {localStore} from './browserStorage.js';
import {t,getLocale} from './i18n.js';
import {serviceMessage} from './serviceMessages.js';
import {speechParts} from './speechText.js';
import './speech-output.css';
import VoiceCloneSettings from './VoiceCloneSettings.jsx';

const defaults={automatic:false,language:'auto',ru:'ru-xenia',en:'en-amy',rate:1};
function saved(){try{return {...defaults,...JSON.parse(localStore.getItem('freedom-speech-output')||'{}')}}catch{return {...defaults}}}
let state={status:'idle',owner:null,error:'',part:0,total:0,info:null,prefs:saved()};
const subscribers=new Set();
let sequence=0,audio=null,finish=null;
let meterContext=null,meterSource=null,meter=null,meterData=null,meterFrequency=null;
function detachMeter(){meterSource?.disconnect();meter?.disconnect();meterSource=null;meter=null;meterData=null;meterFrequency=null}
function unlockMeter(){try{const Context=window.AudioContext||window.webkitAudioContext;if(!Context)return;meterContext??=new Context();meterContext.resume().catch(()=>{})}catch{}}
function attachMeter(player){
  detachMeter();
  try{
    const Context=window.AudioContext||window.webkitAudioContext;if(!Context)return;
    meterContext??=new Context();
    if(meterContext.state!=='running'){meterContext.resume().then(()=>{if(audio===player&&!meterSource)attachMeter(player)}).catch(()=>{});return}
    meterSource=meterContext.createMediaElementSource(player);meter=meterContext.createAnalyser();meter.fftSize=512;meter.smoothingTimeConstant=.45;meterData=new Float32Array(512);meterFrequency=new Uint8Array(meter.frequencyBinCount);meterSource.connect(meter);meter.connect(meterContext.destination);
  }catch{if(meterSource)try{meterSource.connect(meterContext.destination)}catch{}meter=null;meterData=null}
}
function outputLevel(){if(state.status!=='playing'||!meter||!meterData)return 0;meter.getFloatTimeDomainData(meterData);return Math.min(1,Math.sqrt(meterData.reduce((s,v)=>s+v*v,0)/meterData.length)*4)}
function outputFeatures(){
 if(state.status!=='playing'||!String(state.owner).startsWith('jarvis:')||!meter||!meterData||!audio||audio.muted||audio.volume===0)return {speaking:false,rms:0,low:0,mid:0,high:0};
 const rms=outputLevel();meter.getByteFrequencyData(meterFrequency);const sums=[0,0,0],counts=[0,0,0],step=meterContext.sampleRate/meter.fftSize;
 for(let i=1;i<meterFrequency.length;i++){const hz=i*step;if(hz>6500)break;const band=hz<500?0:hz<2000?1:2;sums[band]+=meterFrequency[i]/255;counts[band]++}
 return {speaking:true,rms,low:sums[0]/Math.max(1,counts[0]),mid:sums[1]/Math.max(1,counts[1]),high:sums[2]/Math.max(1,counts[2])};
}
const cloneJobs=new Set();
const publish=patch=>{state={...state,...patch};for(const notify of subscribers)notify()};
const subscribe=notify=>{subscribers.add(notify);return()=>subscribers.delete(notify)};
export function useSpeech(){return useSyncExternalStore(subscribe,()=>state)}
function updateInfo(info){
  publish({info});
  const voice=info?.cloning?.ready&&info.cloning.default_voice;
  if(voice&&state.prefs.appliedVoiceDefault!==voice)preferences({ru:voice,en:voice,rate:1,appliedVoiceDefault:voice});
}
function stop(){
  detachMeter();
  sequence++;
  for(const job of cloneJobs)api('/speech/jobs/'+job+'/cancel',{method:'POST',body:'{}'}).catch(()=>{});
  cloneJobs.clear();
  if(audio){audio.pause();audio.removeAttribute('src');audio.load();audio=null}
  if(finish){finish();finish=null}
  publish({status:'idle',owner:null,error:'',part:0,total:0,phase:'',notice:'',spokenText:''});
}
function preferences(patch){
  const prefs={...state.prefs,...patch};prefs.rate=Math.min(1.5,Math.max(.7,Number(prefs.rate)||1));
  if(!['auto','ru','en'].includes(prefs.language))prefs.language='auto';
  localStore.setItem('freedom-speech-output',JSON.stringify(prefs));publish({prefs});
  if(audio)audio.playbackRate=prefs.rate;
  if(audio)audio.volume=Math.max(0,Math.min(1,Number(prefs.volume??1)));
}
async function resume(){
  if(!audio)return;
  unlockMeter();
  try{await audio.play();publish({status:'playing',error:''})}catch{publish({status:'paused',error:t('Нажмите воспроизвести, чтобы разрешить звук.')})}
}
function pause(){if(audio){audio.pause();publish({status:'paused'})}}
async function read(text,owner,languageOverride){
  stop();const ticket=sequence;
  try{
    const parts=speechParts(text);
    if(!parts.length)throw new Error(t('В этом ответе нет текста для озвучки.'));
    if(!state.info?.ready)throw new Error(t('Озвучка ещё не готова. Откройте настройки голоса.'));
    publish({status:'loading',owner,total:parts.length,part:1,error:'',phase:'',spokenText:parts[0]});
    const load=async index=>{
      const language=languageOverride||(state.prefs.language==='auto'?(/[а-яё]/i.test(parts[index])?'ru':'en'):state.prefs.language);
      try{
        let result=await api('/speech/synthesize',{method:'POST',body:JSON.stringify({text:parts[index],voice:state.prefs[language],language})});
        if(result.job){
          const job=result.job;cloneJobs.add(job);
          if(ticket!==sequence){cloneJobs.delete(job);await api('/speech/jobs/'+job+'/cancel',{method:'POST',body:'{}'});return {error:new Error('Озвучка остановлена')}}
          while(ticket===sequence){
            const progress=await api('/speech/jobs/'+job);
            if(progress.state==='ready'){result=progress.result;break}
            if(['error','cancelled'].includes(progress.state))throw new Error(progress.error||'Озвучка остановлена');
            if(state.status==='loading')publish({phase:progress.phase});
            await new Promise(resolve=>setTimeout(resolve,1300));
          }
          cloneJobs.delete(job);
        }
        return {result,language};
      }catch(error){return {error}}
    };
    let pending=load(0);
    for(let index=0;index<parts.length;index++){
      const prepared=await pending;
      if(ticket!==sequence)return;
      if(prepared.error)throw prepared.error;
      publish({part:index+1,language:prepared.language,status:'loading',phase:'',notice:prepared.result.notice||'',spokenText:parts[index]});
      const player=new Audio(prepared.result.url);audio=player;
      attachMeter(player);
      player.playbackRate=state.prefs.rate;
      player.volume=Math.max(0,Math.min(1,Number(state.prefs.volume??1)));
      // One fragment ahead, so reading can continue while the CPU prepares the next sentence.
      pending=index+1<parts.length?load(index+1):null;
      await new Promise((resolve,reject)=>{
        finish=resolve;player.onended=resolve;
        player.onerror=()=>reject(new Error(t('Не удалось воспроизвести звук.')));
        player.play().then(()=>{if(ticket===sequence)publish({status:'playing'})}).catch(()=>{
          if(ticket===sequence)publish({status:'paused',error:t('Нажмите воспроизвести, чтобы разрешить звук.')});
        });
      });
      if(ticket!==sequence)return;
      finish=null;audio=null;detachMeter();
    }
    if(ticket===sequence)publish({status:'idle',owner:null,error:''});
  }catch(error){if(ticket===sequence)publish({status:'error',error:error.message||t('Не удалось создать озвучку.')})}
}
export function readLatestResponse(messages){
  const message=[...messages].reverse().find(item=>item.role==='assistant'&&typeof item.content==='string'&&item.content.trim());
  if(message){read(serviceMessage(message.content,getLocale()),message.message_uid||'latest');return true}
  publish({status:'error',error:t('В чате пока нет ответа для озвучки.')});return false;
}

export const jarvisSpeech={read,stop,resume,preferences,get:()=>state,level:outputLevel,features:outputFeatures,unlockMeter};
export function SpeechCoordinator({available,sid,snapshot,busy}){
  const watch=useRef({sid:null,baseline:null,working:false});
  useEffect(()=>{if(available)updateInfo(available)},[available]);
  useEffect(()=>{
    if(!available?.enabled)return;
    const messages=snapshot?.messages||[];
    const reply=[...messages].reverse().find(message=>message.role==='assistant'&&typeof message.content==='string'&&message.content.trim()&&!message.tool_calls?.length);
    const id=reply?.message_uid||null;
    if(watch.current.sid!==sid){watch.current={sid,baseline:id,working:!!busy};return}
    if(busy){watch.current.working=true;return}
    if(watch.current.working&&!snapshot?.running&&id&&id!==watch.current.baseline){
      watch.current={sid,baseline:id,working:false};
      if(state.prefs.automatic&&!window.__freedomJarvisActive)read(serviceMessage(reply.content,getLocale()),id);
    }else if(!watch.current.working)watch.current.baseline=id;
  },[available?.enabled,sid,busy,snapshot]);
  return null;
}

export function ReadAloudButton({text,id}){
  const speech=useSpeech(),current=speech.owner===id&&speech.status!=='idle'&&speech.status!=='error';
  return <button type="button" className={'icon-text speech-read-button '+(current?'active':'')} title={t('Прочитать вслух')} aria-label={t('Прочитать вслух')}
    onClick={()=>current?(speech.status==='playing'?pause():speech.status==='paused'?resume():stop()):read(text,id)}>
    {current&&speech.status==='loading'?<LoaderCircle size={14} className="spin"/>:current&&speech.status==='playing'?<Pause size={14}/>:<Volume2 size={14}/>}
    <span>{current?(speech.status==='loading'?t('Готовлю озвучку'):speech.status==='playing'?t('Пауза'):t('Продолжить')):t('Прочитать вслух')}</span>
  </button>;
}

export function SpeechPlayer(){
  const speech=useSpeech();if(speech.status==='idle')return null;
  return <div className="speech-player" role="region" aria-label={t('Озвучка ответа')}>
    {speech.status==='loading'?<LoaderCircle size={15} className="spin"/>:<Volume2 size={15}/>}
    <div className="speech-player-label"><strong>{speech.status==='error'?t('Озвучка недоступна'):speech.status==='loading'?t('Готовлю озвучку'):speech.status==='paused'?t('Озвучка на паузе'):t('Читаю ответ')}</strong>
      <small>{speech.error||(speech.status==='loading'&&speech.phase)||`${speech.language==='en'?'English':'Русский'} · ${speech.part} / ${speech.total}`}</small></div>
    {speech.status!=='error'&&<button className="icon-button" disabled={speech.status==='loading'} onClick={()=>speech.status==='playing'?pause():resume()} aria-label={speech.status==='playing'?t('Пауза'):t('Продолжить озвучку')}>{speech.status==='playing'?<Pause size={15}/>:<Play size={15}/>}</button>}
    <button className="icon-button" onClick={stop} aria-label={t('Остановить озвучку')}>{speech.status==='error'?<X size={15}/>:<Square size={13}/>}</button>
  </div>;
}

export function SpeechSettings({enabled}){
  const speech=useSpeech();if(!enabled)return null;
  const voices=speech.info?.voices||[];
  return <details className="speech-settings">
    <summary><Volume2 size={18}/><span className="speech-settings-title"><strong>{t('Голос Freedom GPT')}</strong><small>{t('Русский и английский · локально · без подписки')}</small></span><span className="speech-ready">{speech.info?.ready?t('Готово'):t('Подготовка')}</span><ChevronDown className="speech-settings-chevron" size={14}/></summary>
    <div className="speech-settings-body" role="region" aria-label={t('Настройки озвучки')}>
    <label className="speech-checkbox"><input type="checkbox" checked={!!speech.prefs.automatic} onChange={e=>preferences({automatic:e.target.checked})}/><span>{t('Читать новые ответы автоматически')}</span></label>
    <div className="speech-settings-grid">
      <label>{t('Язык чтения')}<select aria-label={t('Язык чтения')} value={speech.prefs.language} onChange={e=>preferences({language:e.target.value})}><option value="auto">{t('Определять автоматически')}</option><option value="ru">Русский</option><option value="en">English</option></select></label>
      <label>{t('Скорость чтения')}<select aria-label={t('Скорость чтения')} value={speech.prefs.rate} onChange={e=>preferences({rate:Number(e.target.value)})}>{[.75,.85,1,1.15,1.25,1.5].map(rate=><option key={rate} value={rate}>{rate}×</option>)}</select></label>
      <label>{t('Русский голос')}<select aria-label={t('Русский голос')} value={speech.prefs.ru} onChange={e=>preferences({ru:e.target.value})}>{voices.filter(voice=>voice.language==='ru').map(voice=><option value={voice.id} key={voice.id}>{voice.name}</option>)}</select></label>
      <label>{t('Английский голос')}<select aria-label={t('Английский голос')} value={speech.prefs.en} onChange={e=>preferences({en:e.target.value})}>{voices.filter(voice=>voice.language==='en').map(voice=><option value={voice.id} key={voice.id}>{voice.name}</option>)}</select></label>
    </div>
    <div className="speech-samples"><button type="button" onClick={()=>read('Привет! Я Freedom GPT. Я могу прочитать ответ вслух и помочь вам с работой.','sample-ru','ru')}>{t('Послушать русский')}</button><button type="button" onClick={()=>read('Hello! I am Freedom GPT. I can read my answers aloud and help you with your projects.','sample-en','en')}>{t('Послушать английский')}</button></div>
    {speech.status!=='idle'&&speech.status!=='error'&&<div className="speech-preview-controls"><span>{speech.status==='loading'?t('Готовлю озвучку'):speech.status==='paused'?t('Озвучка на паузе'):t('Читаю ответ')}</span><button type="button" disabled={speech.status==='loading'} onClick={()=>speech.status==='playing'?pause():resume()} aria-label={speech.status==='playing'?t('Пауза'):t('Продолжить озвучку')}>{speech.status==='playing'?<Pause size={13}/>:<Play size={13}/>}</button><button type="button" onClick={stop} aria-label={t('Остановить озвучку')}><Square size={12}/></button></div>}
    <p className="speech-settings-note">{t('Код и длинные ссылки пропускаются. Озвучка работает на процессоре. Можно написать: «прочитай предыдущий ответ».')}</p>
    <VoiceCloneSettings initial={speech.info?.cloning} onChange={cloning=>{
      const standard=(state.info?.voices||[]).filter(v=>!v.id.startsWith('clone-'));
      const custom=(cloning.profiles||[]).filter(p=>p.state==='ready').flatMap(p=>['ru','en'].map(language=>({id:'clone-'+p.id,name:p.name+' · мой голос',language,engine:'Qwen3-TTS'})));
      updateInfo({...state.info,cloning,voices:[...standard,...custom]});
    }} onUse={voice=>{preferences({ru:voice,en:voice,rate:1});stop()}} onPreview={voice=>{preferences({ru:voice,en:voice,rate:1});read('Привет! Я Фридом. Теперь я говорю вашим голосом.','sample-my-voice','ru')}}/>
    {speech.error&&<p className="error-text" role="alert">{speech.error}</p>}
    </div>
  </details>;
}
