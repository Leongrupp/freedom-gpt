import React,{useEffect,useRef,useState} from 'react';
import {Camera,ScanFace,UserRound,Smartphone,Monitor,ShieldCheck,Square,Play,Upload,ExternalLink,Copy,Check,RefreshCw,LoaderCircle,Video,ArrowLeft} from 'lucide-react';
import {api} from './api.js';
import {t,useLocale} from './i18n.js';
import {copyText} from './clipboard.js';
import {localStore} from './browserStorage.js';
import {cameraDevices,preferredCamera,captureCamera,cameraFailure} from './camera/capture.js';
import {createTracker,faceCrop,cropPortrait,gatherIce,rtcOptions} from './camera/tracking.js';
import {createLiveTracker} from './camera/liveTracking.js';
import {CameraIllumination} from './camera/illumination.js';
import './camera-studio.css';
import {LiveVoice,voiceEffects} from './camera/liveVoice.js';

const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function stopTracks(stream){stream?.getTracks().forEach(track=>track.stop())}
function localOutput(url){try{const key=new URL(url).pathname.split('/').pop();return '/api/camera/output.jpg?key='+encodeURIComponent(key)}catch{return ''}}

export function CameraStudioPanel(){
  const phoneBrowser=/iPhone|iPad|iPod|Android/i.test(globalThis.navigator?.userAgent||'')||(globalThis.navigator?.platform==='MacIntel'&&globalThis.navigator?.maxTouchPoints>1);
  const requestedCat=new URLSearchParams(location.search).get('avatar')==='cat';
  const [character,setCharacter]=useState(()=>requestedCat?'cat':localStore.getItem('freedom-camera-character')||'vrm');
  const [status,setStatus]=useState(null),[mode,setMode]=useState(requestedCat?'avatar':phoneBrowser?'photo':'avatar'),[input,setInput]=useState('pc'),[style,setStyle]=useState('swap');
  const sourceInput=phoneBrowser?'pc':input;
  const [devices,setDevices]=useState([]),[deviceId,setDeviceId]=useState(()=>localStore.getItem('freedom-camera-device')||'');
  const [error,setError]=useState(''),[working,setWorking]=useState(false),[loading,setLoading]=useState(''),[protectedView,setProtected]=useState(true),[copied,setCopied]=useState(false),[obs,setObs]=useState(null),[openingOBS,setOpeningOBS]=useState(false);
  const [avatarLoading,setAvatarLoading]=useState(false);
  const [voiceEffect,setVoiceEffect]=useState(()=>localStore.getItem('freedom-camera-voice')||'off'),[monitorVoice,setMonitorVoice]=useState(false),[recording,setRecording]=useState(false),[recordURL,setRecordURL]=useState('');
  const recordRef=useRef(null),recordURLRef=useRef('');
  useEffect(()=>()=>{if(recordURLRef.current)URL.revokeObjectURL(recordURLRef.current)},[]);
  const [framing,setFraming]=useState(requestedCat?'full':'waist'),[tint,setTint]=useState('original');
  const [light,setLight]=useState(()=>localStore.getItem('freedom-camera-light')||'auto'),[motion,setMotion]=useState(true),[tracked,setTracked]=useState({});
  const lightRef=useRef(light);lightRef.current=light;
  const video=useRef(null),canvas=useRef(null),preview=useRef(null),file=useRef(null),avatarFile=useRef(null);
  const runtime=useRef(null),renderer=useRef(null),mounted=useRef(true);
  const active=status&&status.state!=='stopped';
  const stageHint=loading||(mode==='avatar'&&avatarLoading?t('Загружаем 3D-персонажа…'):'');
  const sourceImage=status?.portrait?'/api/camera/assets/portrait.png?updated='+String(status.portrait_updated||0):null;
  async function refresh(){const value=await api('/camera/status');if(mounted.current){setStatus(value);setProtected(Boolean(value.protected))}return value}
  async function refreshDevices(){
    try{const list=await cameraDevices();if(mounted.current){setDevices(list);if(!phoneBrowser&&!active&&!working)setDeviceId(value=>preferredCamera(list,value))}}catch{}
  }
  useEffect(()=>{
    if(phoneBrowser)return;
    refreshDevices();navigator.mediaDevices?.addEventListener?.('devicechange',refreshDevices);
    return()=>navigator.mediaDevices?.removeEventListener?.('devicechange',refreshDevices);
  },[phoneBrowser,Boolean(active),working]);
  useEffect(()=>{
    const run=runtime.current;
    if(run?.session&&status?.session===run.session&&status.state==='stopped'){
      stopRuntime(true,false);
      if(status.error)setError(status.error);
    }
  },[status?.session,status?.state,status?.error]);
  useEffect(()=>{
    mounted.current=true;refresh().catch(e=>setError(e.message));const timer=setInterval(()=>refresh().catch(()=>{}),1000);
    return()=>{mounted.current=false;clearInterval(timer);stopRuntime(false);renderer.current?.dispose()};
  },[]);
  useEffect(()=>{
    if(mode!=='avatar'||!canvas.current){setAvatarLoading(false);return}
    let disposed=false;setAvatarLoading(true);
    (character==='archi'?import('./camera/archiRenderer.js'):import('./camera/avatarRenderer.js')).then(async({AvatarRenderer})=>{
      if(disposed)return;const view=new AvatarRenderer(canvas.current);renderer.current=view;view.audio=()=>runtime.current?.voice?.features()||{};
      await view.load('/api/camera/assets/avatar.vrm?revision='+encodeURIComponent(status?.avatar_revision||''),character);
      if(disposed){view.dispose();return}view.setFrame(framing);view.setTint(tint);setAvatarLoading(false);
    }).catch(e=>{if(!disposed){setError(t('Не удалось открыть VRM-персонажа')+': '+e.message);setAvatarLoading(false)}});
    return()=>{disposed=true;renderer.current?.dispose();renderer.current=null};
  },[mode,status?.avatar_revision,character]);
  useEffect(()=>{renderer.current?.setFrame(framing);renderer.current?.draw()},[framing]);
  useEffect(()=>{renderer.current?.setTint(tint);renderer.current?.draw()},[tint]);
  useEffect(()=>{
    if(mode!=='photo'||!status?.output_url||!preview.current)return;
    let disposed=false,currentUrl='';const endpoint=localOutput(status.output_url);
    async function poll(){while(!disposed){try{const response=await fetch(endpoint+'&t='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error();const url=URL.createObjectURL(await response.blob());if(disposed){URL.revokeObjectURL(url);break}const previous=currentUrl;currentUrl=url;if(preview.current)preview.current.src=url;if(previous)URL.revokeObjectURL(previous)}catch{}await delay(90)}}poll();
    return()=>{disposed=true;if(currentUrl)URL.revokeObjectURL(currentUrl)};
  },[mode,status?.output_url]);
  async function stopRuntime(update=true,notifyServer=true){
    const running=runtime.current;runtime.current=null;
    if(running){running.stopped=true;clearInterval(running.voiceWatch);finishRecording();running.voice?.close();running.peer?.close();stopTracks(running.stream);running.tracker?.close()}
    if(video.current){stopTracks(video.current.srcObject);video.current.srcObject=null}
    if(notifyServer&&(running||update)){try{const value=await api('/camera/stop',{method:'POST',body:'{}'});if(update&&mounted.current)setStatus(value)}catch(e){if(update&&mounted.current)setError(e.message)}}
    if(update&&mounted.current){setProtected(true);setLoading('');setWorking(false);setTracked({})}
  }
  async function phoneInput(run,state){
    const room=new URL(state.phone_url,location.origin).searchParams.get('camera_phone');
    const peer=new RTCPeerConnection(rtcOptions);run.peer=peer;
    peer.addTransceiver('video',{direction:'recvonly'});
    peer.ontrack=event=>{if(!run.stopped&&video.current){video.current.srcObject=event.streams[0]||new MediaStream([event.track]);video.current.play().catch(()=>{})}};
    peer.onconnectionstatechange=()=>{if(peer.connectionState==='failed'&&!run.stopped)setError(t('Не удалось соединить камеры напрямую. Для первой проверки подключите телефон и ПК к одной Wi-Fi сети.'))};
    await peer.setLocalDescription(await peer.createOffer());await gatherIce(peer);
    if(run.stopped)return;
    await api('/camera/signal',{method:'POST',body:JSON.stringify({room,role:'host',action:'offer',sdp:peer.localDescription.sdp})});
    while(!run.stopped&&!peer.currentRemoteDescription){
      const data=await api('/camera/signal',{method:'POST',body:JSON.stringify({room,role:'host',action:'poll'})});
      if(data.answer)await peer.setRemoteDescription(data.answer);else await delay(700);
    }
  }
  async function start(){
    setError('');setWorking(true);setLoading(t('Подключаем камеру…'));
    const run={stopped:false,sequence:0,stream:null,peer:null,tracker:null};runtime.current=run;
    try{
      if(mode==='avatar'&&!renderer.current?.vrm)throw Error(t('Дождитесь загрузки 3D-персонажа.'));
      if(mode==='avatar')renderer.current.calibrate();
      if(voiceEffect!=='off'){run.voice=new LiveVoice();await run.voice.start(voiceEffect);if(run.stopped){run.voice.close();return}run.voice.listen(monitorVoice);run.voiceWatch=setInterval(()=>{if(performance.now()-(run.faceSeen||0)>500)run.voice?.protect(false)},100)}
      if(sourceInput==='pc'){
        if(!navigator.mediaDevices?.getUserMedia)throw Error(t('Браузер не разрешает доступ к камере. Откройте Freedom на localhost или по HTTPS.'));
        let captured;
        try{captured=await captureCamera({phone:phoneBrowser,deviceId})}
        catch(error){await refreshDevices();throw Error(t(cameraFailure(error)))}
        run.stream=captured.stream;
        if(!phoneBrowser&&captured.deviceId){setDeviceId(captured.deviceId);localStore.setItem('freedom-camera-device',captured.deviceId)}
        if(run.stopped){stopTracks(run.stream);return}video.current.srcObject=run.stream;await video.current.play();
        for(const track of run.stream.getVideoTracks())track.addEventListener('ended',()=>{if(runtime.current===run&&!run.stopped){setError(t('Камера отключена. Подключите её и включите снова.'));stopRuntime()}},{once:true});
      }
      setLoading(t(mode==='avatar'&&character!=='archi'&&motion?'Загружаем распознавание тела и кистей…':'Загружаем распознавание мимики…'));run.tracker=await createLiveTracker(mode==='avatar'&&character!=='archi'&&motion);
      if(run.stopped){run.tracker.close();return}
      if(run.tracker.warnings?.length)setError(t('Трекеры тела или кистей недоступны. Мимика продолжает работать. Остановите камеру и повторите подключение.'));
      const state=await api('/camera/start',{method:'POST',body:JSON.stringify({mode,input:sourceInput,style})});run.session=state.session;
      if(run.stopped){await api('/camera/stop',{method:'POST',body:'{}'});return}setStatus(state);
      if(sourceInput==='phone')phoneInput(run,state).catch(e=>{if(!run.stopped)setError(e.message)});
      while(!run.stopped){const next=await refresh();if(next.state==='running')break;if(next.error||next.state==='stopped')throw Error(next.error||t('Видеорежим остановлен.'));setLoading(t('Готовим видеокарту для фоторежима…'));await delay(600)}
      if(run.stopped)return;
      setLoading(sourceInput==='phone'?t('Откройте подключение камеры на телефоне'):t('Камера готова'));setWorking(false);
      processFrames(run,mode).catch(async e=>{if(!run.stopped){setError(e.message);await stopRuntime()}});
    }catch(e){setError(e.message);await stopRuntime();setWorking(false)}
  }
  async function processFrames(run,selectedMode){
    const illumination=new CameraIllumination();let lastVideoTime=-1,lastStamp=0,lastUI=0;
    while(!run.stopped){
      const tracks=video.current?.srcObject?.getVideoTracks?.()||[];
      if(tracks.some(track=>track.readyState!=='live'||track.muted||!track.enabled)){
        if(!run.inputLost){run.voice?.protect(false);run.inputLost=true;await api('/camera/frame',{method:'POST',body:JSON.stringify({session:run.session,sequence:++run.sequence,faces:0})});if(mounted.current)setProtected(true)}
        await delay(100);continue;
      }
      run.inputLost=false;
      if(!video.current||video.current.readyState<2||video.current.currentTime===lastVideoTime){if(performance.now()-lastStamp>500)run.voice?.protect(false);await delay(20);continue}
      const videoSource=video.current;lastVideoTime=videoSource.currentTime;const stamp=Math.max(performance.now(),lastStamp+1);lastStamp=stamp;
      const source=illumination.process(videoSource,lightRef.current,stamp);
      const result=await run.tracker.detect(source,stamp);if(run.stopped)return;
      illumination.focusFace(result);
      const crop=faceCrop(result,source.width,source.height,selectedMode==='avatar'?.0007:.0015),faces=crop?1:0;
      run.voice?.protect(!!faces);run.faceSeen=faces?performance.now():0;
      if(mounted.current){setProtected(!faces);setLoading(faces?'':t('Лицо не найдено — выход защищён'))}
      const packet={session:run.session,sequence:++run.sequence,faces};
      if(faces){
        if(selectedMode==='avatar'){
          const parts=renderer.current?.update(result)||{};
          if(stamp-lastUI>250&&mounted.current){setTracked(parts);lastUI=stamp}
          packet.image=canvas.current.toDataURL('image/jpeg',.85);packet.rendered='vrm';
        }else{
          packet.image=source.toDataURL('image/jpeg',.88);packet.crop=crop;
        }
      }else if(mounted.current)setTracked({});
      const accepted=await api('/camera/frame',{method:'POST',body:JSON.stringify(packet)});
      if(mounted.current&&accepted.accepted)setProtected(Boolean(accepted.protected));
      await delay(10);
    }
  }
  function finishRecording(){const r=recordRef.current;if(r&&r.recorder.state!=='inactive')r.recorder.stop();if(r){clearInterval(r.timer);r.stream.getVideoTracks().forEach(t=>t.stop())}recordRef.current=null;if(mounted.current)setRecording(false)}
  function beginRecording(){
    if(!runtime.current||mode!=='avatar')return;
    try{
      const run=runtime.current,output=document.createElement('canvas');output.width=1280;output.height=720;const ctx=output.getContext('2d');
      const draw=()=>{ctx.fillStyle='#111318';ctx.fillRect(0,0,1280,720);const valid=!run.stopped&&performance.now()-(run.faceSeen||0)<500;if(valid)ctx.drawImage(canvas.current,0,0,1280,720);else run.voice?.protect(false)};draw();
      const stream=output.captureStream(25);for(const track of run.voice?.destination?.stream.getAudioTracks()||[])stream.addTrack(track);
      const mime=['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/mp4'].find(x=>MediaRecorder.isTypeSupported(x));
      const recorder=new MediaRecorder(stream,mime?{mimeType:mime}:{}),chunks=[];let bytes=0;
      recorder.ondataavailable=e=>{if(e.data.size){chunks.push(e.data);bytes+=e.data.size;if(bytes>256*1024*1024)finishRecording()}};
      recorder.onstop=()=>{if(recordURLRef.current)URL.revokeObjectURL(recordURLRef.current);const url=URL.createObjectURL(new Blob(chunks,{type:recorder.mimeType}));recordURLRef.current=url;if(mounted.current)setRecordURL(url);else URL.revokeObjectURL(url)};
      recordRef.current={recorder,stream,timer:setInterval(draw,40)};recorder.start(1000);setRecording(true);
    }catch(e){finishRecording();setError(e.message)}
  }
  async function uploadPortrait(event){
    const picked=event.target.files?.[0];event.target.value='';if(!picked)return;
    setWorking(true);setError('');setLoading(t('Находим лицо на фотографии…'));let tracker,url;
    try{
      if(picked.size>8*1024**2)throw Error(t('Выберите изображение до 8 МБ.'));
      url=URL.createObjectURL(picked);const image=new Image();image.src=url;await image.decode();tracker=await createTracker('IMAGE');
      const result=tracker.detect(image),crop=faceCrop(result,image.naturalWidth,image.naturalHeight);
      if(!crop)throw Error(t('На фотографии должно быть одно хорошо видимое лицо целиком.'));
      await api('/camera/portrait',{method:'POST',body:JSON.stringify({image:cropPortrait(image,crop)})});await refresh();
      if(mounted.current)setStatus(value=>({...value,portrait_updated:Date.now()}));
    }catch(e){setError(e.message)}finally{tracker?.close();if(url)URL.revokeObjectURL(url);setWorking(false);setLoading('')}
  }
  async function uploadAvatar(event){
    const picked=event.target.files?.[0];event.target.value='';if(!picked)return;setWorking(true);setError('');
    try{if(picked.size>50*1024**2)throw Error(t('Выберите VRM до 50 МБ.'));await api('/camera/avatar',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:await picked.arrayBuffer()});await refresh();setCharacter('vrm');localStore.setItem('freedom-camera-character','vrm')}
    catch(e){setError(e.message)}finally{setWorking(false)}
  }
  async function resetAvatar(){setWorking(true);try{await api('/camera/avatar',{method:'POST',body:JSON.stringify({action:'default'})});await refresh();setCharacter('vrm');localStore.setItem('freedom-camera-character','vrm')}catch(e){setError(e.message)}finally{setWorking(false)}}
  async function configureOBS(){try{setError('');setObs(await api('/camera/obs',{method:'POST',body:'{}'}))}catch(e){setError(e.message)}}
  async function openOBS(){setOpeningOBS(true);try{await api('/camera/obs/open',{method:'POST',body:'{}'});setObs(value=>({...value,opened:true}))}catch(e){setError(e.message)}finally{setOpeningOBS(false)}}
  async function copy(){try{await copyText(status.output_url);setCopied(true);setTimeout(()=>setCopied(false),1500)}catch(e){setError(e.message)}}
  return <div className="camera-studio">
    <header className="camera-intro"><div className="camera-brand-icon"><Camera size={25}/></div><div><h3>{t('Вы в кадре. Образ — ваш выбор.')}</h3><p>{t('Фотоперсонаж и 3D-аватар на вашем ПК · без подписки')}</p></div><span className="camera-local"><ShieldCheck size={12}/>{t('Локально')}</span></header>
    <div className="camera-mode-tabs" role="tablist" aria-label={t('Вид персонажа')}>
      <button role="tab" aria-selected={mode==='photo'} disabled={active||working} className={mode==='photo'?'selected':''} onClick={()=>setMode('photo')}><ScanFace size={20}/><div><strong>{t('Фото и замена лица')}</strong><small>{t('Внешность из одного портрета')}</small></div></button>
      <button role="tab" aria-selected={mode==='avatar'} disabled={active||working} className={mode==='avatar'?'selected':''} onClick={()=>setMode('avatar')}><UserRound size={20}/><div><strong>{t('3D-персонаж')}</strong><small>{t('Мимика, тело, руки и пальцы')}</small></div></button>
    </div>
    {mode==='avatar'&&<label className="camera-select camera-character-select"><span>{t('Персонаж')}</span><select aria-label={t('Персонаж')} disabled={active||working} value={character} onChange={event=>{setCharacter(event.target.value);localStore.setItem('freedom-camera-character',event.target.value)}}><option value="archi">{t('Арчи · белые частицы')}</option><option value="cat">{t('Дерзкий кот Freedom')}</option><option value="vrm">{t('VRM-персонаж')}</option></select></label>}
    <div className="camera-tracking-options"><label className="camera-select"><span>{t('Свет')}</span><select aria-label={t('Освещение камеры')} value={light} onChange={event=>{setLight(event.target.value);localStore.setItem('freedom-camera-light',event.target.value)}}><option value="auto">{t('Автоосветление')}</option><option value="boost">{t('Сильнее')}</option><option value="off">{t('Без коррекции')}</option></select></label>{mode==='avatar'&&character!=='archi'&&<label className="camera-select"><span>{t('Движения')}</span><select aria-label={t('Отслеживание движений')} value={motion?'full':'face'} disabled={active||working} onChange={event=>setMotion(event.target.value==='full')}><option value="full">{t('Тело и кисти')}</option><option value="face">{t('Только лицо')}</option></select></label>}</div>
    {mode==='avatar'&&<div className="camera-motion-info"><p>{t(character==='archi'?'Повороты головы — с камеры. Рот и частицы реагируют на обработанный микрофон. Выберите голос ниже.':character==='cat'?'Ваш кот из Blender. Модель пока без скелета и мимики; доступен статичный 3D-просмотр.':'Держите руки в кадре. Для ног отойдите от камеры и выберите «В полный рост». В полной темноте камера не различает движения.')}</p>{character==='vrm'&&active&&motion&&<div className="camera-motion-state" aria-label={t('Видимость частей тела')}>{[['body','Корпус'],['leftHand','Левая кисть'],['rightHand','Правая кисть'],['legs','Ноги']].map(([key,label])=><span key={key} className={tracked[key]?'detected':''}><i/>{t(label)}</span>)}</div>}</div>}
    <div className="camera-stage"><video ref={video} muted playsInline className="camera-input-video" aria-hidden="true"/>
      {mode==='avatar'?<canvas key={character} ref={canvas} width={1280} height={720} aria-label={t('Предпросмотр аватара')}/>:<img ref={preview} alt={t('Предпросмотр обработанного видео')}/>}
      <div className="camera-stage-label"><span className={'tiny-dot '+(active&&!protectedView?'green':'muted')}/>{active&&!protectedView?t('Обработанное видео'):t('Предпросмотр')}<span>{active&&status?.fps?status.fps+' FPS':''}</span></div>
      {stageHint&&<div className="camera-stage-hint">{working&&<LoaderCircle size={15} className="spin"/>}{stageHint}</div>}
      {active&&protectedView&&<div className="camera-protection"><ShieldCheck size={13}/>{t('В OBS — защитная заглушка')}</div>}
    </div>
    <div className="camera-options">
      <div className="camera-source-picker" role="group" aria-label={t('Источник камеры')}><button disabled={active||working} className={sourceInput==='pc'?'selected':''} onClick={()=>setInput('pc')}>{phoneBrowser?<Smartphone size={14}/>:<Monitor size={14}/>} {t(phoneBrowser?'Камера этого телефона':'Камера ПК')}</button>{!phoneBrowser&&<button disabled={active||working} className={input==='phone'?'selected':''} onClick={()=>setInput('phone')}><Smartphone size={14}/>{t('Камера телефона')}</button>}</div>
      {!phoneBrowser&&sourceInput==='pc'&&<><label className="camera-select"><span>{t('Устройство')}</span><select aria-label={t('Устройство камеры')} disabled={active||working} value={deviceId} onChange={event=>{setDeviceId(event.target.value);localStore.setItem('freedom-camera-device',event.target.value)}}><option value="">{t('Автоматически')}</option>{devices.map((device,index)=><option key={device.deviceId||index} value={device.deviceId}>{device.label||t('Камера')+' '+(index+1)}</option>)}</select></label><button className="camera-calibrate" disabled={active||working} title={t('Обновить список камер')} onClick={refreshDevices}><RefreshCw size={14}/></button></>}
      {mode==='photo'?<><button className="camera-upload" disabled={active||working} onClick={()=>file.current?.click()}>{sourceImage?<img src={sourceImage} alt=""/>:<Upload size={15}/>}<span>{t(status?.portrait?'Заменить портрет':'Выбрать портрет')}</span></button><label className="camera-select"><span>{t('Вывод')}</span><select disabled={active||working} value={style} onChange={e=>setStyle(e.target.value)}><option value="swap">{t('Заменить лицо в кадре')}</option><option value="portrait">{t('Оживить портрет целиком')}</option></select></label></>:<><button className="camera-upload" disabled={active||working} onClick={()=>avatarFile.current?.click()}><Upload size={15}/>{t('Свой VRM')}</button>{status?.custom_avatar&&<button className="camera-calibrate" disabled={active||working} title={t('Вернуть демоперсонажа')} onClick={resetAvatar}><RefreshCw size={15}/></button>}<label className="camera-select"><span>{t('Кадр')}</span><select value={framing} onChange={e=>setFraming(e.target.value)}><option value="head">{t('Портрет')}</option><option value="waist">{t('По пояс')}</option><option value="full">{t('В полный рост')}</option></select></label><label className="camera-select"><span>{t('Образ')}</span><select value={tint} onChange={e=>setTint(e.target.value)}><option value="original">{t('Оригинальный')}</option><option value="blue">{t('Синий персонаж')}</option></select></label><button className="camera-calibrate" title={t('Выровнять положение головы')} onClick={()=>renderer.current?.calibrate()}><RefreshCw size={15}/></button></>}
    </div>
    <div className="camera-options camera-voice-options">
      <label className="camera-select"><span>{t('Живой голос')}</span><select aria-label="Живой голос" disabled={active||working} value={voiceEffect} onChange={e=>{setVoiceEffect(e.target.value);localStore.setItem('freedom-camera-voice',e.target.value)}}>{voiceEffects.map(([id,label])=><option key={id} value={id}>{t(label)}</option>)}</select></label>
      <label className="camera-select"><input type="checkbox" checked={monitorVoice} onChange={e=>{setMonitorVoice(e.target.checked);runtime.current?.voice?.listen(e.target.checked)}}/>{t('Слышать себя · в наушниках')}</label>
      {mode==='avatar'&&<button className="secondary-panel-button" disabled={!active||working} onClick={recording?finishRecording:beginRecording}>{recording?t('Завершить запись'):t('Записать видео со звуком')}</button>}
      {recordURL&&<a className="secondary-panel-button" href={recordURL} download="Freedom-avatar.webm">{t('Скачать запись')}</a>}
    </div>
    <p className="camera-voice-help">{t('Голос меняется локально в реальном времени. Это эффекты микрофона, не копии голосов актёров. Запись сохраняет аватар и обработанный звук; до 256 МБ за запись.')}</p>
    <input type="file" ref={file} accept="image/png,image/jpeg,image/webp" className="hidden-input" onChange={uploadPortrait}/><input type="file" ref={avatarFile} accept=".vrm" className="hidden-input" onChange={uploadAvatar}/>
    {mode==='photo'&&<p className="camera-notice">{t('При замене лица одежда и фон остаются вашими. Для полностью виртуального кадра выберите оживление портрета или 3D-персонажа.')}</p>}
    <div className="camera-main-actions">{active||runtime.current?<button className="camera-stop" onClick={()=>stopRuntime()}><Square size={14}/>{t('Остановить камеру')}</button>:<button className="primary-button" disabled={working||!status?.ready||(mode==='photo'&&(!status?.portrait||!status?.photo_ready))||(mode==='avatar'&&(avatarLoading||!renderer.current?.vrm))||Boolean(loading)} onClick={start}>{working?<LoaderCircle size={15} className="spin"/>:<Play size={15}/>} {t('Включить камеру')}</button>}<button className="secondary-panel-button" disabled={!status} onClick={configureOBS}><Video size={15}/>{t('Подключить OBS')}</button></div>
    {!phoneBrowser&&input==='phone'&&status?.phone_url&&active&&<section className="camera-phone-pair"><img src={'/api/camera/phone-qr.svg?session='+status.session} alt={t('QR-код камеры телефона')}/><div><strong>{t('Откройте камеру на телефоне')}</strong><p>{t('Отсканируйте QR-код уже подключённым телефоном и разрешите камеру. Для первой проверки используйте общий Wi-Fi.')}</p><small>{t('Видео передаётся напрямую на этот ПК. Подключение телефона к агенту остаётся прежним.')}</small></div></section>}
    {obs&&<section className="camera-obs"><h4><Video size={16}/>{t('Готово для OBS')}</h4><p>{t('Откройте отдельный профиль с готовой сценой или добавьте источник «Браузер» в свой OBS: 1280 × 720. Передаётся только обработанный выход.')}</p><div className="camera-obs-actions">{status?.obs_found&&<button className="secondary-panel-button" disabled={openingOBS} onClick={openOBS}>{openingOBS?<LoaderCircle size={14} className="spin"/>:<Video size={14}/>} {t(obs.opened?'OBS открыт в трее':'Открыть OBS')}</button>}<button className="secondary-panel-button" onClick={copy}>{copied?<Check size={14}/>:<Copy size={14}/>} {t('Скопировать адрес')}</button><a className="secondary-panel-button" href={status?.output_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/>{t('Открыть выход')}</a><a className="secondary-panel-button" href={obs.download} download>{t('Скачать сцену OBS')}</a></div><small>{t('Для звука в OBS включите «Слышать себя» и захват аудио приложения Freedom. Отключите исходный микрофон в OBS, чтобы не было двойного голоса. Эфир автоматически не запускается.')}</small></section>}
    <footer className="camera-notes"><ShieldCheck size={15}/><p>{t('При потере лица, остановке камеры или сбое в OBS показывается заглушка. Исходное видео не используется как запасной выход.')}</p></footer>
    <details className="camera-license"><summary>{t('Модели и лицензии')}</summary><p>{t('Фоторежим: LivePortrait (MIT). Распознавание: MediaPipe (Apache-2.0). Веса InsightFace не используются. 3D-просмотр: Three.js и three-vrm (MIT).')}</p>{character==='cat'?<p>{t('Ваш Orange_Cat_3D.blend. Исходник сохранён без изменений; для просмотра используется отдельная копия GLB без скелета и анимации.')}</p>:<><p>{t('Демонстрационный VRM')}: {status?.avatar_name}. {!status?.custom_avatar&&'© pixiv Inc. · VRM Public License 1.0.'} {t('У собственного персонажа условия могут отличаться.')}</p><a href="https://vrm.dev/licenses/1.0/" target="_blank" rel="noreferrer">{t('Условия VRM')}</a></>}</details>
    {!status?.ready&&status&&<p className="camera-notice">{t('Компоненты видеорежима ещё устанавливаются. Камера появится после завершения подготовки.')}</p>}
    {mode==='photo'&&status?.ready&&!status.photo_ready&&<p className="camera-notice">{t('Компоненты фоторежима ещё устанавливаются. 3D-персонаж уже доступен.')}</p>}
    {error&&<p role="alert" className="panel-error">{error}</p>}
  </div>
}

export function CameraPhone({room}){
  useLocale();const [state,setState]=useState('ready'),[error,setError]=useState('');const peer=useRef(null),stream=useRef(null),mounted=useRef(true),generation=useRef(0),preview=useRef(null);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;peer.current?.close();stopTracks(stream.current)}},[]);
  useEffect(()=>{
    if(state!=='connected')return;let disposed=false,currentUrl='';
    const heartbeat=()=>api('/camera/signal',{method:'POST',body:JSON.stringify({room,role:'phone',action:'heartbeat'})}).catch(()=>{if(!disposed)stop()});
    heartbeat();const timer=setInterval(heartbeat,1000);
    async function poll(){
      try{const status=await api('/camera/status'),endpoint=localOutput(status.output_url);
        while(!disposed){const response=await fetch(endpoint+'&t='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error();const url=URL.createObjectURL(await response.blob());if(disposed){URL.revokeObjectURL(url);break}const previous=currentUrl;currentUrl=url;if(preview.current)preview.current.src=url;if(previous)URL.revokeObjectURL(previous);await delay(180)}
      }catch{if(preview.current)preview.current.removeAttribute('src')}
    }poll();return()=>{disposed=true;clearInterval(timer);if(currentUrl)URL.revokeObjectURL(currentUrl)};
  },[state]);
  async function start(){
    peer.current?.close();stopTracks(stream.current);const attempt=++generation.current;
    const current=()=>mounted.current&&attempt===generation.current;
    setError('');setState('connecting');let connection,live;
    try{
      await api('/bootstrap');
      if(!current())return;
      if(!navigator.mediaDevices?.getUserMedia)throw Error(t('Камера доступна только по HTTPS или на localhost.'));
      live=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30,max:30}},audio:false});
      if(!current()){stopTracks(live);return}stream.current=live;
      connection=new RTCPeerConnection(rtcOptions);peer.current=connection;
      live.getTracks().forEach(track=>connection.addTrack(track,live));
      connection.onconnectionstatechange=()=>{if(current()){if(connection.connectionState==='connected')setState('connected');if(connection.connectionState==='failed'){setError(t('Прямое соединение не установлено. Подключите телефон и ПК к одной Wi-Fi сети и повторите.'));stop()}}};
      let offer;
      for(let n=0;n<60&&current();n++){const data=await api('/camera/signal',{method:'POST',body:JSON.stringify({room,role:'phone',action:'poll'})});if(data.offer){offer=data.offer;break}await delay(500)}
      if(!current()){connection.close();stopTracks(live);return}
      if(!offer)throw Error(t('На ПК ещё не готово подключение. Включите режим камеры телефона в Freedom.'));
      await connection.setRemoteDescription(offer);await connection.setLocalDescription(await connection.createAnswer());await gatherIce(connection);
      if(!current()){connection.close();stopTracks(live);return}
      await api('/camera/signal',{method:'POST',body:JSON.stringify({room,role:'phone',action:'answer',sdp:connection.localDescription.sdp})});
    }catch(e){connection?.close();stopTracks(live);if(current()){setError(e.message);setState('ready')}}
  }
  function stop(){generation.current++;peer.current?.close();peer.current=null;stopTracks(stream.current);stream.current=null;api('/camera/signal',{method:'POST',body:JSON.stringify({room,role:'phone',action:'stop'})}).catch(()=>{});if(mounted.current)setState('stopped')}
  return <main className="camera-phone-screen"><div className="camera-phone-card"><div className="camera-brand-icon"><Camera size={32}/></div><h1>Freedom Avatar</h1><p>{t('Телефон — камера. Ваш ПК — видеостудия.')}</p><div className={'camera-phone-state '+state}><span className={'tiny-dot '+(state==='connected'?'green':'muted')}/>{t(state==='connected'?'Камера подключена к ПК':state==='connecting'?'Устанавливаем прямое соединение…':state==='stopped'?'Камера остановлена':'Готово к подключению')}</div>{state==='connected'&&<img className="camera-phone-preview" ref={preview} alt={t('Предпросмотр обработанного видео')}/>} {state==='ready'?<button className="primary-button" onClick={start}><Camera size={17}/>{t('Подключить камеру')}</button>:state!=='stopped'&&<button className="camera-stop" onClick={stop}><Square size={15}/>{t('Остановить камеру')}</button>}{state==='stopped'&&<p>{t('Для нового подключения включите камеру на ПК и откройте новый QR-код.')}</p>}<p className="camera-phone-private"><ShieldCheck size={16}/>{t('Исходное видео направляется на ваш ПК для обработки. В OBS отправляется только защищённый результат.')}</p>{error&&<p className="panel-error" role="alert">{error}</p>}<a href={location.pathname}><ArrowLeft size={14}/>{t('Вернуться к агенту')}</a></div></main>
}
