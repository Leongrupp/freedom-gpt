import * as THREE from 'three';
import {matrixGrid} from './archiMatrixGeometry.js';
import {FaceMotion} from './jarvisFaceMotion.js';
const vertex=`
uniform float uTime,uReveal,uJaw,uLevel;attribute vec4 aFace;attribute float aSeed;
varying vec2 vUv;varying float vSeed,vLight,vMask,vMouth,vSide;varying vec3 vWorld;
void main(){
 vec4 p=instanceMatrix*vec4(position,1.0);vec3 center=instanceMatrix[3].xyz;
 vec2 facial=vec2(center.x/1.58,center.y/1.55);
 float lower=1.0-smoothstep(-.80,-.35,facial.y);
 p.y-=uJaw*.085*lower*aFace.w*uReveal;
 p.z+=aFace.x*uReveal;
 p.z+=sin(center.x*3.2+center.y*2.1-uTime*.55)*.009;
 p.z+=sin(center.y*4.0-uTime*.8+aSeed*.18)*.004*(1.0-uReveal);
 vec3 faceNormal=normalize(vec3(-aFace.y*uReveal,-aFace.z*uReveal,1.0));
 vLight=max(.08,dot(faceNormal,normalize(vec3(-.4,.62,1.0))));
 float lipY=-.49+.045*pow(facial.x/.34,2.0)-uJaw*.026;
 vMouth=(1.0-smoothstep(.24,.35,abs(facial.x)))*(1.0-smoothstep(.012+uJaw*.025,.030+uJaw*.035,abs(facial.y-lipY)))*uReveal;
 vSide=normal.z<.5?.42:1.0;vUv=uv;vSeed=aSeed;vMask=aFace.w;vWorld=center;
 gl_Position=projectionMatrix*modelViewMatrix*p;
}`;
const fragment=`
uniform float uTime,uReveal,uLevel,uEnabled;varying vec2 vUv;varying float vSeed,vLight,vMask,vMouth,vSide;varying vec3 vWorld;
void main(){
 vec2 p=abs(vUv-.5)*2.0;float box=length(max(p-vec2(.72),0.0));float rim=smoothstep(.08,.23,box);
 float wave=.5+.5*sin(vWorld.y*3.6+vWorld.x*1.9-uTime*.52);
 float spark=pow(max(0.0,sin(vSeed*179.0+uTime*(.36+vSeed*.28))),28.0)*step(.82,vSeed);
 float scan=exp(-pow((vWorld.y-(mod(uTime*.19,4.4)-2.2))/.045,2.0));
 float face=mix(1.0,.24+1.25*vLight,uReveal*vMask);
 float value=(.045+rim*.17+wave*.025+scan*.065+spark*.48)*face;
 value+=uReveal*vMask*pow(vLight,5.0)*.11;
 value*=1.0-vMouth*.90;
 vec3 color=mix(vec3(.015,.35,.48),vec3(.26,.86,1.0),rim*.48+spark*.45+uReveal*vMask*.16);
 gl_FragColor=vec4(color*value*2.3*vSide*(.22+.78*uEnabled),1.0);
 #include <colorspace_fragment>
}`;
export class JarvisFaceScene{
 constructor(host,{signal,quality='auto',onError,onQuality}){
  this.host=host;this.signal=signal;this.quality=quality;this.onError=onError;this.onQuality=onQuality;this.closed=false;this.motion=new FaceMotion();this.clock=performance.now();this.last=0;this.reveal=0;this.enabled=0;this.target={x:0,y:0};this.voiceAt=-10;this.frames=[];
  this.renderer=new THREE.WebGLRenderer({alpha:false,antialias:true,powerPreference:'low-power'});this.renderer.setClearColor(0x02080d);this.renderer.outputColorSpace=THREE.SRGBColorSpace;
  const gl=this.renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');this.device=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):'WebGL';this.software=/swiftshader|llvmpipe|software/i.test(this.device);this.low=quality==='low'||this.software;this.ratio=this.low?1:Math.min(devicePixelRatio,1.5);this.renderer.setPixelRatio(this.ratio);host.appendChild(this.renderer.domElement);this.renderer.domElement.setAttribute('aria-label','Живая матрица Арчи: лицо появляется во время речи');
  this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(35,1,.1,20);this.camera.position.set(0,0,6.35);this.camera.lookAt(0,0,0);this.wall=new THREE.Group();this.scene.add(this.wall);
  this.u={uTime:{value:0},uReveal:{value:0},uJaw:{value:0},uLevel:{value:0},uEnabled:{value:0}};
  const data=matrixGrid(this.low);this.cells=data.count;const g=new THREE.BoxGeometry(data.tile,data.tile,.026);g.setAttribute('aFace',new THREE.InstancedBufferAttribute(data.face,4));g.setAttribute('aSeed',new THREE.InstancedBufferAttribute(data.seed,1));
  this.material=new THREE.ShaderMaterial({uniforms:this.u,vertexShader:vertex,fragmentShader:fragment});this.tiles=new THREE.InstancedMesh(g,this.material,data.count);const transform=new THREE.Matrix4();for(let i=0;i<data.count;i++){transform.makeTranslation(...data.positions.slice(i*3,i*3+3));this.tiles.setMatrixAt(i,transform)}this.tiles.frustumCulled=false;this.wall.add(this.tiles);
  const line=[];for(const side of [-1,1])for(const y of [-1.68,1.68]){line.push(side*1.36,y,-.02,side*1.18,y,-.02);line.push(side*1.36,y,-.02,side*1.36,y-Math.sign(y)*.20,-.02)}
  const frame=new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(line,3)),new THREE.LineBasicMaterial({color:0x26758e,transparent:true,opacity:.5}));this.wall.add(frame);
  this.pointer=e=>{const r=host.getBoundingClientRect();this.target={x:THREE.MathUtils.clamp((e.clientX-r.left)/r.width*2-1,-1,1),y:THREE.MathUtils.clamp((e.clientY-r.top)/r.height*2-1,-1,1)}};this.leave=()=>{this.target={x:0,y:0}};host.addEventListener('pointermove',this.pointer);host.addEventListener('pointerleave',this.leave);
  this.lost=e=>{e.preventDefault();onError?.('3D недоступно. Голосовое управление продолжает работать.')};this.renderer.domElement.addEventListener('webglcontextlost',this.lost);this.resize=new ResizeObserver(()=>this.size());this.resize.observe(host);this.size();host.dataset.faceReady='true';this.loop=this.loop.bind(this);this.raf=requestAnimationFrame(this.loop);
 }
 size(){if(this.closed)return;const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h);this.camera.aspect=w/h;this.camera.position.z=this.camera.aspect<.75?7.0:6.35;this.camera.updateProjectionMatrix();this.changed=true}
 loop(now){if(this.closed)return;this.raf=requestAnimationFrame(this.loop);if(document.hidden)return;const signal=this.signal(),fps=!signal.enabled?8:this.low||this.economy?16:28;if(now-this.last<1000/fps&&!this.changed)return;const start=performance.now(),dt=Math.min(.12,(now-this.last)/1000),t=(now-this.clock)/1000;this.last=now;
  try{
   const output=signal.output?.()||{},m=this.motion.step({...signal,output},t,dt);
   if(signal.enabled&&signal.phase==='speaking'&&output.speaking&&output.rms>.003)this.voiceAt=t;
   const speaking=signal.enabled&&signal.phase==='speaking'&&output.speaking&&t-this.voiceAt<.48;
   this.reveal=THREE.MathUtils.damp(this.reveal,speaking?1:0,speaking?5.5:3.3,dt);this.enabled=THREE.MathUtils.damp(this.enabled,signal.enabled?1:0,4,dt);
   this.u.uTime.value=t;this.u.uReveal.value=this.reveal;this.u.uJaw.value=m.jaw;this.u.uLevel.value=output.rms||0;this.u.uEnabled.value=this.enabled;
   this.wall.rotation.y=THREE.MathUtils.damp(this.wall.rotation.y,this.target.x*.035+Math.sin(t*.19)*.006,3,dt);this.wall.rotation.x=THREE.MathUtils.damp(this.wall.rotation.x,-this.target.y*.025,3,dt);
   this.renderer.render(this.scene,this.camera);this.changed=false;const elapsed=performance.now()-start;this.frames.push(elapsed);if(this.frames.length>40)this.frames.shift();
   if(qualityAuto(this)&&!this.economy&&this.frames.length===40&&this.frames.reduce((a,b)=>a+b,0)/40>14){this.economy=true;this.renderer.setPixelRatio(1);this.onQuality?.('Экономный режим');this.size()}
   this.host.__faceDiagnostics={style:'archi-living-matrix-relief',phase:signal.phase,reveal:this.reveal,wallOnly:this.reveal<.02,actualAudio:!!output.speaking,audioRms:output.rms||0,jaw:m.jaw,eyes:false,cells:this.cells,drawCalls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles,renderMs:elapsed,fpsLimit:fps,device:this.device,frames:(this.host.__faceDiagnostics?.frames||0)+1};
  }catch{this.onError?.('Не удалось отрисовать 3D. Голосовое управление продолжает работать.');this.close()}
 }
 close(){if(this.closed)return;this.closed=true;cancelAnimationFrame(this.raf);this.resize.disconnect();this.host.removeEventListener('pointermove',this.pointer);this.host.removeEventListener('pointerleave',this.leave);this.renderer.domElement.removeEventListener('webglcontextlost',this.lost);this.scene.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});this.renderer.dispose();this.renderer.forceContextLoss();this.renderer.domElement.remove();delete this.host.dataset.faceReady}
}
const qualityAuto=scene=>scene.quality==='auto';
