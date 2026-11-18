import {openMicrophone} from '../microphoneSource.js';
export const voiceEffects=[['off','Без микрофона'],['natural','Чистый голос'],['archi','Арчи · цифровой'],['tars','ТАРС · робот'],['radio','Радиосвязь']];
// Live DSP effects, not cloned voices or text-to-speech.
export class LiveVoice{
 constructor(){this.closed=false;this.allowed=false}
 async start(effect,device='auto'){
  window.dispatchEvent(new CustomEvent('freedom-mic-claim',{detail:{owner:'camera-voice'}}));
  try{
   this.context=new AudioContext();await this.context.resume();this.stream=await openMicrophone(device);
   if(this.closed){this.stream.getTracks().forEach(t=>t.stop());return}
   const c=this.context;this.source=c.createMediaStreamSource(this.stream);this.filter=c.createBiquadFilter();this.filter.type='bandpass';this.filter.frequency.value=effect==='radio'?1700:1200;this.filter.Q.value=effect==='radio'?1.1:.25;
   this.mod=c.createGain();this.mod.gain.value=effect==='archi'?.75:effect==='tars'?.65:1;
   this.osc=c.createOscillator();this.osc.frequency.value=effect==='tars'?55:90;this.depth=c.createGain();this.depth.gain.value=['archi','tars'].includes(effect)?.35:0;this.osc.connect(this.depth).connect(this.mod.gain);this.osc.start();
   this.limiter=c.createDynamicsCompressor();this.limiter.threshold.value=-15;this.limiter.ratio.value=5;this.gate=c.createGain();this.gate.gain.value=0;
   this.analyser=c.createAnalyser();this.analyser.fftSize=1024;this.samples=new Float32Array(1024);this.spectrum=new Uint8Array(512);this.destination=c.createMediaStreamDestination();
   this.source.connect(this.filter).connect(this.mod).connect(this.limiter).connect(this.gate).connect(this.analyser).connect(this.destination);
   this.monitor=c.createGain();this.monitor.gain.value=0;this.analyser.connect(this.monitor).connect(c.destination);
  }catch(e){this.close();throw e}
 }
 protect(allowed){this.allowed=allowed;if(this.gate&&this.context.state!=='closed')this.gate.gain.setTargetAtTime(allowed?1:0,this.context.currentTime,.015)}
 listen(enabled){if(this.monitor)this.monitor.gain.value=enabled?1:0}
 features(){if(!this.analyser||this.closed||!this.allowed)return {};this.analyser.getFloatTimeDomainData(this.samples);this.analyser.getByteFrequencyData(this.spectrum);const rms=Math.sqrt(this.samples.reduce((s,v)=>s+v*v,0)/this.samples.length);return {speaking:rms>.012,rms:Math.min(1,rms*4),low:this.spectrum[4]/255,high:this.spectrum[80]/255}}
 close(){this.closed=true;this.stream?.getTracks().forEach(t=>t.stop());this.destination?.stream.getTracks().forEach(t=>t.stop());try{this.osc?.stop()}catch{}this.context?.close().catch(()=>{});window.dispatchEvent(new CustomEvent('freedom-mic-release',{detail:{owner:'camera-voice'}}))}
}
