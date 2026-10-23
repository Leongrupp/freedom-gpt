import {localStore} from './browserStorage.js';

const PREFS_KEY='freedom-completion-notifications-v1';
const PREFS_EVENT='freedom-notification-preferences';
export const COMPLETION_EVENT='freedom-answer-complete';
export const PREVIEW_EVENT='freedom-notification-preview';
const defaults={enabled:true,sound:true};

export function notificationPreferences(){
  try{
    const saved=JSON.parse(localStore.getItem(PREFS_KEY)||'null');
    return {enabled:typeof saved?.enabled==='boolean'?saved.enabled:defaults.enabled,
      sound:typeof saved?.sound==='boolean'?saved.sound:defaults.sound};
  }catch{return {...defaults}}
}
export function saveNotificationPreferences(change){
  const value={...notificationPreferences(),...change};
  localStore.setItem(PREFS_KEY,JSON.stringify(value));
  window.dispatchEvent(new Event(PREFS_EVENT));
}
export function watchNotificationPreferences(listener){
  const storage=event=>{if(event.key===null||event.key?.endsWith(PREFS_KEY))listener()};
  window.addEventListener(PREFS_EVENT,listener);
  window.addEventListener('storage',storage);
  return()=>{window.removeEventListener(PREFS_EVENT,listener);window.removeEventListener('storage',storage)};
}

// Only live terminal events enter here. Loading history or reconnecting never
// announces old replies. No answer body is copied into a notification or storage.
export function publishCompletionFrame(frame){
  if(frame?.type!=='gateway.event'||frame.event_type!=='message.complete'||!frame.session_id)return;
  const p=frame.payload||{};
  if(p.error||p.failure_reason||p.partial||
    (p.status&&p.status!=='complete')||
    (p.outcome&&!['complete','completed','settled','success'].includes(p.outcome)))return;
  // Child watch mirrors have text only. A real completed turn has a status or
  // execution identity; do not notify about those intermediate mirrors.
  if(!p.status&&frame.execution_generation==null)return;
  const receipt=p.persisted_turn||{};
  const identity=receipt.submission_id||receipt.final_assistant_row_id||
    (frame.execution_generation!=null?'generation:'+frame.execution_generation:
      frame.activity_revision!=null?'revision:'+frame.activity_revision:null);
  if(identity==null)return;
  const key=[frame.activity_epoch||'',frame.session_id,identity].join(':');
  window.dispatchEvent(new CustomEvent(COMPLETION_EVENT,{detail:{key,sid:frame.session_id}}));
}

let audioContext=null,unlocked=false,lastSound=0;
function context(){
  if(!audioContext||audioContext.state==='closed'){
    const Audio=window.AudioContext||window.webkitAudioContext;
    if(!Audio)return null;
    audioContext=new Audio();
  }
  return audioContext;
}
// Unlock on a real interaction, including Safari touch, without playing a tone.
// Autoplay restrictions or a muted phone must never interrupt a chat.
export function unlockNotificationAudio(){
  try{
    const audio=context();if(!audio)return;
    if(unlocked&&audio.state==='running')return;
    const ready=()=>{if(audio.state==='running')unlocked=true};
    audio.resume().then(ready).catch(()=>{});
    const silent=audio.createBufferSource();silent.buffer=audio.createBuffer(1,1,audio.sampleRate);
    silent.connect(audio.destination);silent.start(0);ready();
  }catch{}
}
async function chime(){
  try{
    if(!unlocked||!audioContext||Date.now()-lastSound<1200)return false;
    if(audioContext.state!=='running'){
      let timer;
      try{await Promise.race([audioContext.resume(),new Promise(resolve=>{timer=setTimeout(resolve,600)})])}
      finally{clearTimeout(timer)}
    }
    if(audioContext.state!=='running')return false;
    if(!notificationPreferences().enabled||!notificationPreferences().sound)return false;
    const start=audioContext.currentTime+.015;
    // A soft rising two-note bell, under half a second, with no downloaded audio.
    for(const [frequency,delay] of [[659.25,0],[880,.13]]){
      const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();
      oscillator.type='sine';oscillator.frequency.value=frequency;
      gain.gain.setValueAtTime(0,start+delay);
      gain.gain.linearRampToValueAtTime(.065,start+delay+.012);
      gain.gain.exponentialRampToValueAtTime(.0001,start+delay+.25);
      oscillator.connect(gain);gain.connect(audioContext.destination);
      oscillator.start(start+delay);oscillator.stop(start+delay+.27);
      oscillator.onended=()=>{oscillator.disconnect();gain.disconnect()};
    }
    lastSound=Date.now();return true;
  }catch{return false}
}
const SOUND_KEY='freedom-completion-sounds-v1';
const scope=typeof document!=='undefined'?document.documentElement.dataset.freedomRemote||'local':'local';
export async function playNotificationSound(key,{preview=false}={}){
  const prefs=notificationPreferences();
  if(!prefs.enabled||!prefs.sound)return;
  if(preview){unlockNotificationAudio();await Promise.resolve();return chime()}
  if(!unlocked)return;
  // Give the visible tab first chance to play, then serialize sound across tabs
  // where Web Locks is available. Devices retain their own independent settings.
  await new Promise(resolve=>setTimeout(resolve,document.visibilityState==='visible'?30:350));
  const play=async()=>{
    if(!notificationPreferences().enabled||!notificationPreferences().sound)return;
    let recent=[];
    try{recent=JSON.parse(localStore.getItem(SOUND_KEY)||'[]');if(!Array.isArray(recent))recent=[]}catch{}
    recent=recent.filter(entry=>Array.isArray(entry)&&Date.now()-entry[1]<86400000).slice(-63);
    if(recent.some(entry=>entry[0]===key))return;
    if(await chime())localStore.setItem(SOUND_KEY,JSON.stringify([...recent,[key,Date.now()]]));
  };
  try{
    if(navigator.locks?.request)await navigator.locks.request('freedom-notification-sound:'+scope,play);
    else await play();
  }catch{}
}
