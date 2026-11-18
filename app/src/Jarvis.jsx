import React,{useEffect,useRef,useState} from 'react';
import {AudioLines,Mic,Volume2,X} from 'lucide-react';
import {api} from './api.js';
import {voiceReplyBaseline,readyVoiceReplies} from './voiceReplyRouting.js';
import {localStore,sessionStore} from './browserStorage.js';
import {jarvisSpeech,useSpeech} from './SpeechOutput.jsx';
import {JarvisAudio} from './jarvisAudio.js';
import {virtualMicrophone} from './microphoneSource.js';
import {command,spokenSummary,soundsLikeEcho,completedSentences,pronounce,assistantName,assistantVoice,assistantOptions,greeting,smallTalk,hoverRemark} from './jarvisPolicy.js';
import {useJarvisPreferences,changeJarvisPreferences} from './jarvisPreferences.js';
import {claimJarvisMicrophone,waitForJarvisMicrophone} from './jarvisMicLease.js';
import './jarvis.css';
const JarvisFace=React.lazy(()=>import('./JarvisFace.jsx'));
const labels={off:'Выключен',listening:'Слушаю',recognizing:'Распознаю',processing:'Обрабатываю',working:'Выполняю',speaking:'Отвечаю','sound-paused':'Разрешите звук',clarify:'Нужно уточнение',error:'Ошибка'};
const pause=ms=>new Promise(r=>setTimeout(r,ms));

export function Jarvis({available,speechInfo,sid,busy,snapshot,live,getContext,onTask,onStop,onQueue,onStatus,onNewChat,onOpenSettings,settingsOpen,disabled}){
 const prefs=useJarvisPreferences(),name=assistantName(prefs);
 const[inputName,setInputName]=useState('');
 const[open,setOpen]=useState(false),[needsPermission,setNeedsPermission]=useState(false),[enabled,setEnabled]=useState(false),[phase,setPhase]=useState('off'),[awaiting,setAwaiting]=useState(false),[faceActivation,setFaceActivation]=useState(0),[faceError,setFaceError]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[level,setLevel]=useState(0),[recent,setRecent]=useState([]),[pending,setPending]=useState(()=>{try{return JSON.parse(sessionStore.getItem('freedom-jarvis-pending')||'null')}catch{return null}});
 const voiceQuestions=useRef(new Map()),hoverVoice=useRef(false),hoverAt=useRef(0),lastHeardAt=useRef(0);
 const speech=useSpeech(),ref=useRef({}),engine=useRef(null),alive=useRef(true),epoch=useRef(0),capture=useRef(null),hold=useRef(false),speechChain=useRef(Promise.resolve()),speechEpoch=useRef(0),lastSpoken=useRef(''),echoUntil=useRef(0),watch=useRef({sid,wasBusy:false,baseline:null,streamed:''}),processing=useRef(false),wakeWindow=useRef({until:0,timer:null}),micLease=useRef(null),activating=useRef(null),micEpoch=useRef(0),micBlocked=useRef(false),autoAttempt=useRef(null),autoBlocked=useRef(false),leaseWait=useRef(null),chatGreeting=useRef(false);
 ref.current={prefs,enabled,sid,busy,snapshot,live,getContext,onTask,onStop,onQueue,onStatus,onNewChat,disabled,pending,speechInfo,available,settingsOpen,phase,awaiting,level};
 const change=changeJarvisPreferences;
 useEffect(()=>{
  const restoreRecorded=!prefs.recordedRussianVoicesV1&&speechInfo?.cloning?.profiles?.length;
  const patch=restoreRecorded?{language:'ru',recognitionLanguage:'ru',recordedRussianVoicesV1:true}:{};
  for(const [assistant,voiceKey,appliedKey] of [['tars','tarsRu','tarsVoiceProfileApplied'],['archi','ru','archiVoiceProfileApplied'],['alpo','alpoRu','alpoVoiceProfileApplied']]){
   const profile=speechInfo?.cloning?.profiles?.find(p=>(p.assistant===assistant||(assistant==='alpo'&&p.name==='Альпо'))&&p.state==='ready');
   if(profile&&(restoreRecorded||prefs[appliedKey]!==profile.id)){patch[voiceKey]='clone-'+profile.id;patch[appliedKey]=profile.id}
  }
  if(Object.keys(patch).length)changeJarvisPreferences(patch);
 },[speechInfo,prefs.recordedRussianVoicesV1,prefs.tarsVoiceProfileApplied,prefs.archiVoiceProfileApplied,prefs.alpoVoiceProfileApplied]);

 function clearWake(){clearTimeout(wakeWindow.current.timer);wakeWindow.current.until=0;setAwaiting(false)}
 function armWake(){clearWake();wakeWindow.current.until=Date.now()+15000;setAwaiting(true);wakeWindow.current.timer=setTimeout(()=>{wakeWindow.current.until=0;if(alive.current){setAwaiting(false);setNotice('Ожидаю обращение «'+assistantName(ref.current.prefs)+'».')}},15000)}
 function stopSpeech(){hoverVoice.current=false;speechEpoch.current++;speechChain.current=Promise.resolve();jarvisSpeech.stop();echoUntil.current=Date.now()+1500}
 function remember(value){setPending(value);if(value)sessionStore.setItem('freedom-jarvis-pending',JSON.stringify(value));else sessionStore.removeItem('freedom-jarvis-pending')}
 function add(text,kind='heard'){setRecent(rows=>[...rows,{id:crypto.randomUUID(),text,kind,at:Date.now()}].slice(-12))}
 function touchFace(){
  const r=ref.current,now=Date.now();
  if(!r.enabled||r.busy||r.pending||r.awaiting||r.settingsOpen||processing.current||hold.current||engine.current?.active||r.level>.015||['error','clarify','recognizing','processing'].includes(r.phase)||['loading','playing','paused'].includes(jarvisSpeech.get().status)||now-hoverAt.current<120000||now-lastHeardAt.current<5000||r.prefs.humor===0)return;
  hoverAt.current=now;say(hoverRemark(r.prefs,r.prefs.language==='en'),undefined,true);
 }
 function say(text,language,playful=false){
  const ticket=speechEpoch.current;const p=ref.current.prefs;const words=spokenSummary(text,p.brief);if(!words)return;
  speechChain.current=speechChain.current.catch(()=>{}).then(async()=>{
   if(!alive.current||ticket!==speechEpoch.current||!ref.current.enabled)return;
   hoverVoice.current=playful;lastSpoken.current=pronounce(words,language||p.language);echoUntil.current=Date.now()+3000;
   jarvisSpeech.preferences({ru:assistantVoice(p),en:p.en,language:p.language,rate:p.rate,volume:p.volume});
   await jarvisSpeech.read(pronounce(words,language||p.language),'jarvis:'+crypto.randomUUID(),language||(p.language==='auto'?undefined:p.language));echoUntil.current=Date.now()+1500;hoverVoice.current=false;
  });
 }
 async function deactivate({keepLease=false}={}){leaseWait.current?.abort();leaseWait.current=null;micEpoch.current++;clearWake();epoch.current++;hold.current=false;setEnabled(false);ref.current.enabled=false;window.__freedomJarvisActive=false;setPhase('off');setLevel(0);stopSpeech();const current=engine.current;engine.current=null;await current?.close();if(!keepLease){micLease.current?.release();micLease.current=null}}
 async function activate(){
  jarvisSpeech.unlockMeter();
  if(engine.current&&ref.current.enabled)return engine.current;
  if(activating.current)return activating.current;
  if(!ref.current.available?.ready)throw new Error('Локальное распознавание недоступно. Проверьте настройки микрофона и компонентов Freedom.');
  const ticket=micEpoch.current;
  const operation=(async()=>{
   const lease=micLease.current||await claimJarvisMicrophone();
   if(!lease){setNotice('Арчи уже слушает в другом окне Freedom.');if(ref.current.prefs.autoStart&&!leaseWait.current){const controller=new AbortController();leaseWait.current=controller;waitForJarvisMicrophone(controller.signal).then(()=>{if(leaseWait.current===controller){leaseWait.current=null;if(alive.current&&ref.current.prefs.autoStart&&!micBlocked.current)autoAttempt.current?.()}}).catch(()=>{if(leaseWait.current===controller)leaseWait.current=null})}return null}
   if(!alive.current||ticket!==micEpoch.current){lease.release();return null}micLease.current=lease;
   window.dispatchEvent(new CustomEvent('freedom-mic-claim',{detail:{owner:'jarvis'}}));
   const audio=new JarvisAudio({device:name=>alive.current&&setInputName(name),level:value=>alive.current&&setLevel(value),speaking:()=>['loading','playing'].includes(jarvisSpeech.get().status),continuous:()=>ref.current.enabled&&ref.current.prefs.continuous&&!ref.current.pending,
    disconnected:async()=>{await deactivate();if(ref.current.prefs.autoStart)autoAttempt.current?.()},
    onset:()=>{if(hoverVoice.current)stopSpeech();lastHeardAt.current=Date.now();capture.current={...ref.current.getContext(),echoText:jarvisSpeech.get().spokenText||lastSpoken.current};if(hold.current)stopSpeech();setPhase('listening')},utterance:recognize});
   engine.current=audio;setPhase('listening');setError('');
   try{await audio.start(ref.current.prefs.microphone);if(audio.closed||!alive.current||ticket!==micEpoch.current){await audio.close();lease.release();if(micLease.current===lease)micLease.current=null;return null}
    audio.hold(hold.current);setEnabled(true);ref.current.enabled=true;window.__freedomJarvisActive=true;localStore.setItem('freedom-jarvis-mic-approved','yes');setNeedsPermission(false);setNotice('Ожидаю обращение «'+assistantName(ref.current.prefs)+'».');return audio;
   }catch(error){await audio.close();if(engine.current===audio)engine.current=null;lease.release();if(micLease.current===lease)micLease.current=null;setEnabled(false);setPhase('error');throw error}
  })();activating.current=operation;try{return await operation}finally{if(activating.current===operation)activating.current=null}
 }
 function microphoneError(error){if(!alive.current)return;autoBlocked.current=true;setNeedsPermission(true);if(error.name==='NotAllowedError')localStore.removeItem('freedom-jarvis-mic-approved');setError(error.name==='NotAllowedError'?'Разрешите доступ к микрофону для Freedom в браузере.':error.name==='NotFoundError'?'Микрофон не найден. Подключите его к компьютеру.':error.name==='NotReadableError'?'Не удалось открыть микрофон. Проверьте, не занят ли он другой программой.':error.message);setPhase('error')}
 async function startFromGesture(){autoBlocked.current=false;micBlocked.current=false;change({autoStart:true});try{await activate()}catch(error){microphoneError(error)}}
 async function submit(value){
  if((value.context.sid||null)!==(ref.current.sid||null))throw new Error('Чат изменился. Вернитесь в исходный чат перед повторной передачей.');
  setPhase('processing');setError('');
  if(value.jarvis?.interaction==='question'&&!voiceQuestions.current.has(value.id)){voiceQuestions.current.set(value.id,{text:value.text,sid:value.context.sid,before:voiceReplyBaseline(ref.current.snapshot?.messages)});if(voiceQuestions.current.size>64)voiceQuestions.current.delete(voiceQuestions.current.keys().next().value)}
  const receipt=await ref.current.onTask({id:value.id,text:value.text,context:value.context,jarvis:value.jarvis,
   bind:async bound=>{value={...value,context:{...value.context,sid:bound,chatKey:bound}};remember(value);if(voiceQuestions.current.has(value.id))voiceQuestions.current.get(value.id).sid=bound}} ,value.intent);
  if(!receipt)throw new Error('Передача не подтверждена. Проверьте чат перед повтором.');
  if(voiceQuestions.current.has(value.id))voiceQuestions.current.get(value.id).owner=receipt.admission_id;
  remember(null);setNotice(value.intent==='steer'?'Поправка передана агенту.':'Задание передано в текущий чат.');setPhase('working');
 }
 async function recognize(blob,meta={}){
  const ticket=epoch.current,id=crypto.randomUUID().replaceAll('-',''),context=capture.current||{...ref.current.getContext()};let transcribed=false;processing.current=true;setPhase('recognizing');setError('');
  try{
   const body=new FormData();body.append('audio',blob,'jarvis.wav');let result=await api('/jarvis/transcriptions/'+id+'?language='+encodeURIComponent(ref.current.prefs.recognitionLanguage),{method:'POST',body});
   const until=Date.now()+180000;
   while(['working','queued'].includes(result.state)){
    if(ticket!==epoch.current||!alive.current)return;
    if(Date.now()>until)throw new Error('Распознавание заняло слишком долго. Скажите фразу ещё раз.');
    await pause(350);result=await api('/jarvis/transcriptions/'+id);
   }
   if(ticket!==epoch.current||!alive.current)return;
   if(result.state!=='ready')throw new Error(result.error||'Не удалось разобрать речь. Повторите фразу.');
   transcribed=true;
   if((context.sid||null)!==(ref.current.sid||null))throw new Error('Чат изменился во время записи. Команда не отправлена.');
   const text=result.text;
   const english=ref.current.prefs.language==='en'||ref.current.prefs.language==='auto'&&!/[а-яё]/i.test(text);
   const answer=(ru,en)=>say(english?en:ru,english?'en':'ru');
   if(!meta.manual&&(meta.barge||Date.now()<echoUntil.current)&&(soundsLikeEcho(text,context.echoText)||soundsLikeEcho(text,lastSpoken.current)||soundsLikeEcho(text,jarvisSpeech.get().spokenText))){setNotice('Отзвук озвучки пропущен.');return}
   const intent=command(text,{wake:ref.current.prefs.wake&&!meta.manual&&Date.now()>=wakeWindow.current.until});
   if(intent.kind==='ignore'){setNotice('Ожидаю обращение «'+assistantName(ref.current.prefs)+'».');return}
   if(intent.called){setFaceActivation(value=>value+1);if(ref.current.prefs.showOnWake&&!ref.current.settingsOpen)setOpen(true)}
   // A short proper name may score poorly. It can only open listening, never run a task.
   const wakeOnly=intent.kind==='wake'&&result.recognition?.mean_token_probability>=.30;
   if(result.recognition?.low_confidence&&!wakeOnly){add(text,'uncertain');setPhase('clarify');setNotice('Речь распознана неуверенно. Повторите или уточните команду — она ещё не отправлена.');answer('Не уверен, что правильно расслышал. Повторите команду.','I am not sure I heard you correctly. Please repeat your command.');return}
   if(intent.assistant&&intent.assistant!==ref.current.prefs.assistant){change({assistant:intent.assistant});ref.current.prefs={...ref.current.prefs,assistant:intent.assistant}}
   stopSpeech();add(text);setPhase('processing');
   if(intent.kind==='wake'){armWake();setNotice('Слушаю вашу команду. Можно говорить без повторения имени.');answer('Я на связи. Слушаю вас.','I am here. Listening.');return}
   clearWake();
   if(intent.kind==='smalltalk'){armWake();answer(smallTalk(intent.value,ref.current.prefs),smallTalk(intent.value,ref.current.prefs,true));return}
   if(intent.kind==='greet'){armWake();setNotice('На связи. Слушаю вашу команду.');answer(greeting(ref.current.prefs),greeting(ref.current.prefs,true));return}
   if(intent.kind==='new-chat'){
    if(!ref.current.onNewChat)throw new Error('Сейчас не удалось открыть новый чат.');
    chatGreeting.current=!!ref.current.sid;
    ref.current.onNewChat();
    if(!chatGreeting.current){setNotice('Новый чат открыт. Слушаю вашу команду.');armWake();answer('Новый чат открыт. Слушаю вас.','New chat opened. I am listening.')}
    return;
   }
   if(intent.kind==='clarify'){setPhase('clarify');setNotice('Уточните, что нужно сделать.');answer('Уточните, что нужно сделать.','Please clarify what you want me to do.');return}
   if(intent.kind==='stop-speech'){stopSpeech();setNotice('Озвучка остановлена. Задача продолжает выполняться.');return}
   if(intent.kind==='stop-task'){stopSpeech();if(ref.current.sid)await ref.current.onStop();setNotice('Остановка задачи запрошена.');return}
   if(intent.kind==='humor'){change({humor:intent.value});ref.current.prefs={...ref.current.prefs,humor:intent.value};setNotice('Уровень юмора: '+intent.value+'%.');answer('Уровень юмора — '+intent.value+' процентов.','Humor set to '+intent.value+' percent.');return}
   if(intent.kind==='humor-invalid'){answer('Назовите уровень юмора от нуля до ста.','Choose a humor level from zero to one hundred.');return}
   if(intent.kind==='brief'){change({brief:true});answer('Хорошо, буду отвечать кратко.',"Okay, I will keep my answers brief.");return}
   if(intent.kind==='repeat'){const reply=[...(ref.current.snapshot?.messages||[])].reverse().find(m=>m.role==='assistant'&&m.content&&!m.tool_calls?.length);if(reply)say(reply.content);else setNotice('В этом чате ещё нет ответа.');return}
   if(intent.kind==='status'){ref.current.onStatus?.();if(ref.current.busy)answer('Сейчас выполняю задачу. Подробности видны в чате.','I am working on your task. You can see the progress in the chat.');else answer('Сейчас активных задач в этом чате нет.','There are no active tasks in this chat.');return}
   const value={id,text,context,jarvis:{...assistantOptions(ref.current.prefs),interaction:intent.kind==='question'?'question':'task'},intent:intent.kind==='steer'?'steer':'queue'};
   remember(value);await submit(value);
  }catch(e){if(ticket===epoch.current&&alive.current){setError(e.message);setPhase('error')}}
  finally{processing.current=false;if(!transcribed)api('/jarvis/transcriptions/'+id+'/discard',{method:'POST',body:'{}'}).catch(()=>{});if(ticket===epoch.current&&alive.current)setPhase(p=>['error','clarify','working'].includes(p)?p:ref.current.enabled?'listening':'off')}
 }
 async function press(){if(ref.current.disabled||processing.current||ref.current.pending)return;hold.current=true;stopSpeech();try{const audio=await activate();audio?.hold(hold.current)}catch(e){setError(e.name==='NotAllowedError'?'Разрешите доступ к микрофону в браузере.':e.message);setPhase('error')}}
 function release(){hold.current=false;engine.current?.hold(false)}
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;leaseWait.current?.abort();leaseWait.current=null;clearTimeout(wakeWindow.current.timer);epoch.current++;micEpoch.current++;window.__freedomJarvisActive=false;engine.current?.close();micLease.current?.release();micLease.current=null;stopSpeech()}},[]);
 useEffect(()=>{
  const claimed=e=>{if(e.detail?.owner!=='jarvis'){micBlocked.current=true;deactivate({keepLease:true});setNotice('Микрофон занят диктовкой. Помощник возобновится автоматически.')}};
  const released=e=>{if(e.detail?.owner!=='jarvis'){micBlocked.current=false;if(ref.current.prefs.autoStart)autoAttempt.current?.();else{micLease.current?.release();micLease.current=null}}};
  window.addEventListener('freedom-mic-claim',claimed);window.addEventListener('freedom-mic-release',released);return()=>{window.removeEventListener('freedom-mic-claim',claimed);window.removeEventListener('freedom-mic-release',released)};
 },[]);
 useEffect(()=>{
  if(!available?.enabled||!available?.ready)return;
  if(!prefs.autoStart){deactivate();setNeedsPermission(false);return}
  let stopped=false,permission;
  async function attempt(){
   if(stopped||autoBlocked.current||micBlocked.current||engine.current||activating.current||!ref.current.prefs.autoStart)return;
   let state='unknown';try{permission=await navigator.permissions?.query({name:'microphone'});state=permission?.state||'unknown';if(permission)permission.onchange=()=>{if(permission.state==='granted'){autoBlocked.current=false;setNeedsPermission(false);attempt()}else if(permission.state==='denied'){deactivate();setNeedsPermission(true)}}}catch{}
   if(stopped)return;
   if(state==='granted'||state==='unknown'&&localStore.getItem('freedom-jarvis-mic-approved')==='yes'){try{await activate()}catch(error){microphoneError(error)}}
   else {setNeedsPermission(true);setNotice(state==='denied'?'Разрешите микрофон для Freedom в настройках браузера.':'Для первого запуска разрешите микрофон. После этого помощник запускается сам.')}
  }
  autoAttempt.current=attempt;attempt();const deviceChanged=async()=>{if(ref.current.prefs.microphone==='auto'&&engine.current&&!engine.current.active&&!processing.current&&virtualMicrophone(engine.current.stream?.getAudioTracks()[0]?.label)){const list=await navigator.mediaDevices.enumerateDevices().catch(()=>[]);if(list.some(d=>d.kind==='audioinput'&&d.label&&!['default','communications'].includes(d.deviceId)&&!virtualMicrophone(d.label)))await deactivate()}autoBlocked.current=false;attempt()};const visible=()=>{if(!document.hidden)attempt()};window.addEventListener('focus',attempt);document.addEventListener('visibilitychange',visible);window.addEventListener('freedom-jarvis-mic-available',attempt);navigator.mediaDevices?.addEventListener?.('devicechange',deviceChanged);
  return()=>{stopped=true;autoAttempt.current=null;if(permission)permission.onchange=null;window.removeEventListener('focus',attempt);document.removeEventListener('visibilitychange',visible);window.removeEventListener('freedom-jarvis-mic-available',attempt);navigator.mediaDevices?.removeEventListener?.('devicechange',deviceChanged)};
 },[available?.enabled,available?.ready,prefs.autoStart]);
 useEffect(()=>{if(!engine.current)return;deactivate().then(()=>{if(alive.current&&ref.current.prefs.autoStart)autoAttempt.current?.()})},[prefs.microphone]);
 useEffect(()=>{if(!prefs.continuous&&!hold.current){engine.current?.cancelCapture();capture.current=null;clearWake()}},[prefs.continuous]);
 useEffect(()=>{if(String(jarvisSpeech.get().owner).startsWith('jarvis:'))jarvisSpeech.preferences({rate:prefs.rate,volume:prefs.volume})},[prefs.rate,prefs.volume]);
 useEffect(()=>{if(settingsOpen)setOpen(false)},[settingsOpen]);
 useEffect(()=>{setFaceError('')},[prefs.portrait3d,prefs.portraitQuality]);
 useEffect(()=>{
  const control=e=>{const action=e.detail?.action;if(action==='start')startFromGesture();else if(action==='stop'){change({autoStart:false});deactivate()}else if(action==='stop-speech')stopSpeech();else if(action==='resume-speech')jarvisSpeech.resume();else if(action==='stop-task'){stopSpeech();Promise.resolve(ref.current.onStop()).catch(error=>{setError(error.message);setPhase('error')})}else if(action==='retry'&&ref.current.pending)submit(ref.current.pending).catch(error=>{setError(error.message);setPhase('error')});else if(action==='discard')remember(null);else if(action==='open')setOpen(true)};
  window.addEventListener('freedom-jarvis-control',control);return()=>window.removeEventListener('freedom-jarvis-control',control);
 },[]);
 useEffect(()=>{const old=watch.current.sid;if(old!==sid){watch.current={sid,wasBusy:busy,baseline:null,streamed:''};if(old||!processing.current){epoch.current++;hold.current=false;capture.current=null;engine.current?.cancelCapture();clearWake();stopSpeech();setPhase(ref.current.enabled?'listening':'off');setNotice(ref.current.enabled?'Перешёл в выбранный чат. Ожидаю обращение «'+assistantName(ref.current.prefs)+'».':'Чат изменён.');if(chatGreeting.current){chatGreeting.current=false;armWake();setNotice('Новый чат открыт. Слушаю вашу команду.');say(ref.current.prefs.language==='en'?'New chat opened. I am listening.':'Новый чат открыт. Слушаю вас.')}}}},[sid]);
 useEffect(()=>{
  function matches(e){const key=ref.current.prefs.hotkey;return key==='Alt+J'?e.altKey&&e.code==='KeyJ':key==='Control+Space'?e.ctrlKey&&e.code==='Space':e.altKey&&e.code==='Space'}
  const down=e=>{if(matches(e)&&!e.repeat){e.preventDefault();if(!ref.current.settingsOpen)setOpen(true);press()}},up=e=>{if(hold.current&&(e.code==='KeyJ'||e.code==='Space')){e.preventDefault();release()}};
  const blur=()=>release();window.addEventListener('keydown',down);window.addEventListener('keyup',up);window.addEventListener('blur',blur);
  return()=>{window.removeEventListener('keydown',down);window.removeEventListener('keyup',up);window.removeEventListener('blur',blur)};
 },[]);
 useEffect(()=>{
  if(!enabled)return;
  const w=watch.current,reply=[...(snapshot?.messages||[])].reverse().find(m=>m.role==='assistant'&&m.content&&!m.tool_calls?.length),id=reply?.message_uid||reply?.message_id||reply?.row_id||reply?.content||null;
  if(busy&&!w.wasBusy){w.wasBusy=true;w.baseline=id;w.streamed=''}
  const messages=snapshot?.messages||[],lastUser=[...messages].reverse().find(m=>m.role==='user'),question=[...voiceQuestions.current.entries()].find(([,q])=>q.sid===sid&&String(lastUser?.content||'').trim()===q.text.trim());
  if(question&&prefs.stream&&busy&&live){const complete=completedSentences(live);if(complete.startsWith(w.streamed)&&complete.length>w.streamed.length&&(!prefs.brief||w.streamed.length<520)){
    const next=complete.slice(w.streamed.length).trim();w.streamed=complete;if(next.length>4)say(next);
  }}
  for(const result of readyVoiceReplies(messages,voiceQuestions.current,sid,busy)){
   voiceQuestions.current.delete(result.id);const final=spokenSummary(result.reply.content,true);
   if(!w.streamed||!final.startsWith(w.streamed))say(final);else if(final.length>w.streamed.length)say(final.slice(w.streamed.length));w.streamed='';
  }
  if(!busy&&reply&&id!==w.baseline){w.wasBusy=false;w.baseline=id}

 },[enabled,busy,snapshot,live]);
 const speechOwned=String(speech.owner).startsWith('jarvis:'),soundBlocked=speechOwned&&speech.status==='paused',visibleError=error||(speechOwned?speech.error:'');
 const state=phase==='error'||phase==='clarify'?phase:!enabled?'off':soundBlocked?'sound-paused':['loading','playing'].includes(speech.status)&&speechOwned?'speaking':processing.current?phase:busy?'working':'listening';
 useEffect(()=>{const detail={enabled,engaged:enabled&&(open||busy||state==='speaking'),phase:state,level,inputName,sid,error:error||(String(speech.owner).startsWith('jarvis:')?speech.error:''),notice:notice||(String(speech.owner).startsWith('jarvis:')?speech.notice:''),heard:recent.at(-1)?.text||'',pending:pending?{id:pending.id,text:pending.text}:null,needsPermission,busy};window.__freedomJarvisState=detail;window.dispatchEvent(new CustomEvent('freedom-jarvis-state',{detail}))},[enabled,state,level,inputName,sid,open,busy,error,notice,pending,needsPermission,speech.error,speech.notice,recent]);
 if(!available?.enabled)return null;
 return <><button className={'jarvis-launch '+(enabled?'active':'')} title={name+' · голосовой помощник'} aria-label={'Открыть '+name} onClick={()=>{setOpen(v=>!v);if(!open&&prefs.autoStart&&!enabled)startFromGesture()}}><AudioLines size={13}/><span>{name}</span>{enabled&&<i/>}</button>
 {open&&!settingsOpen&&<aside className={'jarvis-panel jarvis-minimal state-'+state} role="region" aria-label={name+' — голосовой помощник'}>
 <header><div><span className="jarvis-kicker">FREEDOM · ГОЛОСОВОЙ ПОМОЩНИК</span><h2>{name}<span>{prefs.assistant==='tars'?'T.A.R.S.':prefs.assistant==='alpo'?'A.L.P.O.':'A.R.C.H.I.'}</span></h2></div><div><button className="icon-button" aria-label={'Скрыть '+name} title={'Скрыть '+name} onClick={()=>setOpen(false)}><X size={17}/></button></div></header>
 <div className={'jarvis-reactor'+(prefs.portrait3d&&!faceError?' has-face':'')} style={{'--voice-level':level}}>
 {prefs.portrait3d&&!faceError?<React.Suspense fallback={<div className="jarvis-matrix-loading" aria-label="Загрузка визуализации"/>}><JarvisFace name={name} enabled={enabled} phase={!enabled?'off':state==='speaking'?'speaking':busy||state==='processing'?'thinking':'standby'} mood={state} mic={level} activation={faceActivation} quality={prefs.portraitQuality} output={jarvisSpeech.features} onFallback={setFaceError} onTouch={touchFace}/></React.Suspense>:<><div className="jarvis-orbit"/><div className="jarvis-orbit second"/><div className="jarvis-core"><AudioLines size={38}/></div></>}
 <span className="jarvis-state"><i/>{state==='listening'&&prefs.continuous&&prefs.wake?(awaiting?'Слушаю команду':'Жду «'+name+'»'):labels[state]}</span></div>
 {needsPermission&&prefs.autoStart&&!enabled&&<button className="jarvis-permission" onClick={startFromGesture}><Mic size={15}/>Разрешить микрофон</button>}
 {soundBlocked&&<button className="jarvis-permission" onClick={()=>jarvisSpeech.resume()}><Volume2 size={15}/>Включить звук</button>}
 {(visibleError||faceError)&&<p className="jarvis-minimal-error" role="alert">{visibleError||faceError}{onOpenSettings&&<button onClick={onOpenSettings}>Настройки</button>}</p>}
 </aside>}</>;
}
