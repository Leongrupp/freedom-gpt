const clamp=(v,lo=0,hi=1)=>Math.max(lo,Math.min(hi,Number(v)||0));
const damp=(from,to,speed,dt)=>from+(to-from)*(1-Math.exp(-speed*dt));
export class FaceMotion{
 constructor(){this.awake=.06;this.jaw=0;this.round=0;this.mic=0;this.token=0;this.wakeAt=-100;this.disabledAt=-100;this.enabled=false}
 step(signal,now,dt){
  dt=clamp(dt,0,.12);
  if(signal.activation!==this.token){this.token=signal.activation;this.wakeAt=now}
  if(this.enabled&&!signal.enabled)this.disabledAt=now;
  this.enabled=!!signal.enabled;
  const sinceWake=now-this.wakeAt,fade=now-this.disabledAt;
  const engaged=signal.enabled&&(signal.phase!=='standby'||sinceWake<9);
  this.awake=damp(this.awake,signal.enabled?(engaged?1:.3):.055,signal.enabled?4:3.5,dt);
  const audio=signal.output||{},voiced=signal.enabled&&signal.phase==='speaking'&&audio.speaking===true;
  const energy=voiced?clamp((audio.rms-.012)*1.6):0;
  this.jaw=damp(this.jaw,energy,energy>this.jaw?25:22,dt);
  if(!voiced&&this.jaw<.002)this.jaw=0;
  this.round=damp(this.round,voiced?clamp((audio.low||0)*1.6-(audio.high||0)*.9):0,12,dt);
  this.mic=damp(this.mic,signal.enabled&&signal.phase==='listening'?clamp(signal.mic):0,14,dt);
  const cycle=(now%4.7),blink=signal.enabled&&cycle>4.46?Math.sin((cycle-4.46)/.24*Math.PI):0;
  return {awake:this.awake,jaw:this.jaw,round:this.round,mic:this.mic,blink:clamp(blink),thinking:signal.enabled&&signal.phase==='thinking',
   assembly:signal.enabled&&sinceWake<1.35?clamp(sinceWake/1.35):!signal.enabled&&fade<.9?1-clamp(fade/.9):1,
   bursting:signal.enabled&&sinceWake<1.35||!signal.enabled&&fade<.9,enabled:signal.enabled};
 }
}
