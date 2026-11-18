export async function cameraDevices(mediaDevices=globalThis.navigator?.mediaDevices){
  if(!mediaDevices?.enumerateDevices)return [];
  return (await mediaDevices.enumerateDevices()).filter(device=>device.kind==='videoinput');
}

export function preferredCamera(devices,saved=''){
  if(saved&&devices.some(device=>device.deviceId===saved))return saved;
  // PS4/OV580 is already decoded and cropped by OBS; avoid opening its
  // exclusive raw driver a second time when the OBS bridge is available.
  if(devices.some(device=>/OV580|PS4|PlayStation/i.test(device.label||''))){
    const obs=devices.find(device=>/OBS.*Virtual.*Camera/i.test(device.label||''));
    if(obs)return obs.deviceId;
  }
  return '';
}

export async function captureCamera({phone=false,deviceId='',mediaDevices=globalThis.navigator?.mediaDevices}={}){
  let selected=phone?'':preferredCamera(await cameraDevices(mediaDevices),deviceId);
  const constraints=()=>({audio:false,video:{width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30},...(phone?{facingMode:'user'}:selected?{deviceId:{exact:selected}}:{})}});
  try{return {stream:await mediaDevices.getUserMedia(constraints()),deviceId:selected}}
  catch(error){
    // A failed first request can reveal device names after permission was
    // granted. Permit one distinct OBS retry, never a capture retry loop.
    if(!phone&&!deviceId&&!selected&&['NotReadableError','AbortError'].includes(error.name)){
      selected=preferredCamera(await cameraDevices(mediaDevices));
      if(selected)return {stream:await mediaDevices.getUserMedia(constraints()),deviceId:selected};
    }
    throw error;
  }
}

export function cameraFailure(error){
  if(['NotReadableError','AbortError'].includes(error?.name))return 'Камера занята другой программой. Если она открыта в OBS, включите виртуальную камеру OBS и выберите «OBS Virtual Camera».';
  if(['NotAllowedError','SecurityError'].includes(error?.name))return 'Разрешите доступ к камере в настройках браузера и Windows.';
  if(error?.name==='NotFoundError')return 'Камера не найдена. Подключите её и обновите список.';
  if(error?.name==='OverconstrainedError')return 'Камера не поддерживает выбранный режим. Выберите другое устройство.';
  return error?.message||'Не удалось включить камеру.';
}
