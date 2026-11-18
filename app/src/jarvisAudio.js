import {openMicrophone} from './microphoneSource.js';
export function wavBlob(parts,rate){
 const count=parts.reduce((n,p)=>n+p.length,0),buffer=new ArrayBuffer(44+count*2),view=new DataView(buffer);
 const word=(offset,s)=>[...s].forEach((c,i)=>view.setUint8(offset+i,c.charCodeAt(0)));
 word(0,'RIFF');view.setUint32(4,36+count*2,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,count*2,true);
 let at=44;for(const part of parts)for(const sample of part){view.setInt16(at,Math.max(-1,Math.min(1,sample))*(sample<0?32768:32767),true);at+=2}
 return new Blob([buffer],{type:'audio/wav'});
}
export class JarvisAudio{
 constructor(callbacks){this.callbacks=callbacks;this.parts=[];this.ring=[];this.closed=false;this.held=false;this.busy=false;this.active=false;this.noise=.004}
 async start(device='auto'){
  if(!navigator.mediaDevices?.getUserMedia)throw new Error('Разрешите микрофон: откройте Freedom на localhost или по HTTPS.');
  const stream=await openMicrophone(device);
  if(this.closed){stream.getTracks().forEach(t=>t.stop());return}
  this.callbacks.device?.(stream.getAudioTracks()[0]?.label||'Микрофон');
  stream.getAudioTracks().forEach(track=>track.addEventListener('ended',()=>{if(!this.closed)this.callbacks.disconnected?.()},{once:true}));
  this.stream=stream;this.context=new (window.AudioContext||window.webkitAudioContext)();
  let timer;try{await Promise.race([this.context.resume(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Для первого запуска голоса нажмите «Разрешить микрофон».')),2000)})])}finally{clearTimeout(timer)}
  if(this.closed)return;
  this.source=this.context.createMediaStreamSource(stream);this.processor=this.context.createScriptProcessor(2048,1,1);this.gain=this.context.createGain();this.gain.gain.value=0;
  this.processor.onaudioprocess=e=>this.samples(new Float32Array(e.inputBuffer.getChannelData(0)));
  this.source.connect(this.processor);this.processor.connect(this.gain);this.gain.connect(this.context.destination);
 }
 samples(samples){
  if(this.closed)return;
  const rms=Math.sqrt(samples.reduce((sum,v)=>sum+v*v,0)/samples.length),now=performance.now();this.callbacks.level?.(Math.min(1,rms*12));
  if(this.busy){this.ring=[];return}
  const speaking=this.callbacks.speaking?.();const threshold=Math.max(speaking?.045:.014,this.noise*3);
  const loud=rms>threshold;if(!loud&&!this.active)this.noise=this.noise*.98+Math.min(rms,.02)*.02;
  const allowed=this.held||this.callbacks.continuous?.();
  if(!allowed){this.ring=[];return}
  this.ring.push(samples);if(this.ring.length>7)this.ring.shift();
  if((this.held||loud)&&!this.active){
   this.active=true;this.started=now;this.lastSpeech=now;this.voiced=0;this.manual=this.held;this.parts=[...this.ring];this.ring=[];this.wasSpeaking=!!speaking;this.callbacks.onset?.(this.wasSpeaking);
  }else if(this.active)this.parts.push(samples);
  if(loud){this.lastSpeech=now;if(this.active)this.voiced+=samples.length}
  if(this.active&&(now-this.started>25000||!this.held&&now-this.lastSpeech>900))this.finish();
 }
 hold(value){this.held=value;if(value&&this.active)this.manual=true;if(!value&&this.active)this.finish()}
 cancelCapture(){this.held=false;this.active=false;this.parts=[];this.ring=[]}
 finish(){
  if(!this.active)return;this.active=false;const parts=this.parts;this.parts=[];this.ring=[];
  if(parts.reduce((n,p)=>n+p.length,0)<this.context.sampleRate*.35)return;
  if(!this.manual&&this.voiced<this.context.sampleRate*.18)return;
  this.busy=true;this.callbacks.utterance(wavBlob(parts,this.context.sampleRate),{barge:this.wasSpeaking,manual:this.manual}).finally(()=>{this.busy=false});
 }
 async close(){this.closed=true;this.active=false;this.parts=[];this.ring=[];this.stream?.getTracks().forEach(t=>t.stop());this.processor?.disconnect();this.source?.disconnect();this.gain?.disconnect();if(this.context&&this.context.state!=='closed')await this.context.close()}
}
