// Web Locks keep same-profile tabs from creating duplicate automatic listeners.
let channel;try{channel=new BroadcastChannel('freedom-jarvis-microphone');channel.onmessage=event=>{if(event.data==='released')window.dispatchEvent(new Event('freedom-jarvis-mic-available'))}}catch{}
export async function claimJarvisMicrophone(){
 if(!navigator.locks?.request)return {release(){}};
 return new Promise((resolve,reject)=>navigator.locks.request('freedom-jarvis-microphone',{ifAvailable:true},lock=>{
  if(!lock){resolve(null);return}
  return new Promise(release=>{let closed=false;resolve({release(){if(closed)return;closed=true;release();channel?.postMessage('released')}})});
 }).catch(reject));
}
export async function waitForJarvisMicrophone(signal){
 await navigator.locks.request('freedom-jarvis-microphone',{signal},()=>{});
}
