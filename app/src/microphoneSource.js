export const virtualMicrophone=label=>/CABLE|virtual|loopback|stereo mix|стерео микшер/i.test(label||'');
export async function openMicrophone(choice='auto',devices=navigator.mediaDevices){
 const options={echoCancellation:true,noiseSuppression:true,autoGainControl:true};
 if(choice&&choice!=='auto'&&choice!=='default')options.deviceId={exact:choice};
 let stream=await devices.getUserMedia({audio:options,video:false});
 if(choice==='auto'&&virtualMicrophone(stream.getAudioTracks()[0]?.label)){
  let inputs=[];try{inputs=await devices.enumerateDevices()}catch{}
  const physical=inputs.find(d=>d.kind==='audioinput'&&!['default','communications'].includes(d.deviceId)&&d.label&&!virtualMicrophone(d.label));
  if(physical){stream.getTracks().forEach(t=>t.stop());stream=await devices.getUserMedia({audio:{...options,deviceId:{exact:physical.deviceId}},video:false})}
 }
 return stream;
}
