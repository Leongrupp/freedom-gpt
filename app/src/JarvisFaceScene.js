import * as THREE from 'three';
import {portraitCells,portraitOccluder} from './lidarPortraitGeometry.js';
import {cellVertex,cellFragment,occluderVertex,occluderFragment} from './lidarPortraitShaders.js';
import {FaceMotion} from './jarvisFaceMotion.js';
export class JarvisFaceScene{
 constructor(host,{signal,quality='auto',onError,onQuality,canvas=null}){
  this.externalCanvas=canvas;this.host=host;this.signal=signal;this.quality=quality;this.onError=onError;this.onQuality=onQuality;this.closed=false;this.clock=performance.now();this.last=0;this.motion=new FaceMotion();this.gaze={x:0,y:0};this.target={x:0,y:0};this.frameTimes=[];
  this.renderer=new THREE.WebGLRenderer({canvas:canvas||undefined,alpha:true,antialias:false,preserveDrawingBuffer:!!canvas,powerPreference:'low-power'});this.renderer.setClearColor(0x000000,0);this.renderer.outputColorSpace=THREE.SRGBColorSpace;
  const gl=this.renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');this.device=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):'WebGL';this.software=/swiftshader|llvmpipe|software/i.test(this.device);this.low=quality==='low'||this.software;
  this.ratio=this.low?1:Math.min(devicePixelRatio,1.5);this.renderer.setPixelRatio(this.ratio);if(!canvas)host.appendChild(this.renderer.domElement);this.renderer.domElement.setAttribute('aria-label','Объёмное лицо Арчи из световых ячеек');
  this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(34,1,.1,30);this.camera.position.set(.035,.025,8.0);this.camera.lookAt(0,.02,0);
  this.head=new THREE.Group();this.scene.add(this.head);this.u={uTime:{value:0},uJaw:{value:0},uRound:{value:0},uAwake:{value:.055},uAssembly:{value:1},uDisperse:{value:0},uMic:{value:0},uBlink:{value:0},uThinking:{value:0},uGaze:{value:new THREE.Vector2()},uPixelRatio:{value:this.ratio}};
  this.makePortrait();this.makeAtmosphere();this.makeCube();
  this.lost=e=>{e.preventDefault();if(!this.closed)this.onError?.('3D недоступно. Голосовое управление продолжает работать.')};this.renderer.domElement.addEventListener('webglcontextlost',this.lost);
  this.pointer=e=>{if(e.pointerType==='touch')return;this.changed=true;this.hoverStarted??=performance.now();if(performance.now()-this.hoverStarted>1300)this.signal().onTouch?.();const r=host.getBoundingClientRect();this.target.x=THREE.MathUtils.clamp((e.clientX-r.left)/r.width*2-1,-1,1);this.target.y=THREE.MathUtils.clamp((e.clientY-r.top)/r.height*2-1,-1,1)};this.leave=()=>{this.target={x:0,y:0};this.hoverStarted=null;this.changed=true};host.addEventListener('pointermove',this.pointer);host.addEventListener('pointerleave',this.leave);
  this.resize=new ResizeObserver(()=>this.size());this.resize.observe(host);this.size();host.dataset.faceReady='true';this.loop=this.loop.bind(this);this.raf=requestAnimationFrame(this.loop);
 }
 makePortrait(){
  const data=portraitCells(this.low?'low':this.quality);this.cellCount=data.count;this.volumeCount=data.volumeCount;
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(data.position,3));g.setAttribute('aEdge',new THREE.BufferAttribute(data.edge,1));g.setAttribute('aTone',new THREE.BufferAttribute(data.tone,1));g.setAttribute('aSeed',new THREE.BufferAttribute(data.seed,1));g.setAttribute('aLayer',new THREE.BufferAttribute(data.layer,1));
  const options={transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,vertexShader:cellVertex,fragmentShader:cellFragment};
  this.cellsMaterial=new THREE.ShaderMaterial({...options,uniforms:{...this.u,uGlow:{value:0},uSize:{value:this.low?3.3:this.quality==='high'?2.0:2.6}}});g.setDrawRange(0,data.count-data.volumeCount);const background=new THREE.BufferGeometry();for(const [name,attribute] of Object.entries(g.attributes))background.setAttribute(name,attribute);background.setDrawRange(data.count-data.volumeCount,data.volumeCount);this.fieldMaterial=this.cellsMaterial.clone();this.fieldMaterial.depthTest=false;this.fieldMaterial.uniforms={...this.u,uGlow:{value:0},uSize:{value:this.low?3.3:2.6}};const field=new THREE.Points(background,this.fieldMaterial);field.renderOrder=-2;this.head.add(field);this.cells=new THREE.Points(g,this.cellsMaterial);this.cells.renderOrder=2;this.head.add(this.cells);
  if(!this.low){this.glowMaterial=new THREE.ShaderMaterial({...options,uniforms:{...this.u,uGlow:{value:1},uSize:{value:3}}});this.glow=new THREE.Points(g,this.glowMaterial);this.glow.renderOrder=1;this.head.add(this.glow)}
  const cover=portraitOccluder();const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(cover.position,3));geometry.setIndex(cover.indices);
  this.coverMaterial=new THREE.ShaderMaterial({uniforms:this.u,vertexShader:occluderVertex,fragmentShader:occluderFragment,transparent:true,depthWrite:true,side:THREE.DoubleSide});this.cover=new THREE.Mesh(geometry,this.coverMaterial);this.cover.renderOrder=0;this.head.add(this.cover);
 }
 makeAtmosphere(){
  // A faint optical field supports the volume, without a flat portrait texture.
  this.haloMaterial=new THREE.ShaderMaterial({uniforms:this.u,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,fragmentShader:`varying vec2 vUv;uniform float uAwake,uTime,uMic;void main(){vec2 p=(vUv-.5)*2.0;float halo=exp(-dot(p*vec2(1.0,.8),p*vec2(1.0,.8))*3.5);float scan=.85+.15*sin(vUv.y*280.0);gl_FragColor=vec4(.20,.20,.23,halo*scan*uAwake*(.20+uMic*.05));}`});
  const halo=new THREE.Mesh(new THREE.PlaneGeometry(4.2,3.5),this.haloMaterial);halo.position.z=-1.5;halo.renderOrder=-1;this.scene.add(halo);
 }
 makeCube(){
  this.cube=new THREE.Group();this.cube.rotation.set(-.07,.26,0);this.scene.add(this.cube);this.cube.add(this.head);
  const positions=[],steps=this.low?18:26,half=1.58;
  for(let x=0;x<=steps;x++)for(let y=0;y<=steps;y++)for(let z=0;z<=steps;z++){
   const boundary=[x,y,z].filter(v=>v===0||v===steps).length;
   if(!boundary||boundary===1&&(x+y+z)%3!==0)continue;
   positions.push({p:[(x/steps*2-1)*half,(y/steps*2-1)*half,(z/steps*2-1)*half],edge:boundary>=2});
  }
  this.voxelCount=positions.length;
  this.cubeMaterial=new THREE.ShaderMaterial({uniforms:this.u,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
   vertexShader:`uniform float uTime;varying vec3 vColor;varying vec3 vNormal;void main(){vec4 p=instanceMatrix*vec4(position,1.0);p.x+=sin(p.y*3.0+uTime*.7)*.006;p.z+=sin(p.x*3.0-uTime*.6)*.004;vColor=instanceColor;vNormal=normalMatrix*normal;gl_Position=projectionMatrix*modelViewMatrix*p;}`,
   fragmentShader:`uniform float uAwake;varying vec3 vColor;varying vec3 vNormal;void main(){float light=.62+.38*max(0.0,dot(normalize(vNormal),normalize(vec3(-.4,.7,1.0))));gl_FragColor=vec4(vColor*light,.48*uAwake);}`});
  const voxels=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),this.cubeMaterial,positions.length),matrix=new THREE.Matrix4();
  for(let i=0;i<positions.length;i++){const item=positions[i],size=item.edge?.032:.016;matrix.compose(new THREE.Vector3(...item.p),new THREE.Quaternion(),new THREE.Vector3(size,size,size));voxels.setMatrixAt(i,matrix);voxels.setColorAt(i,new THREE.Color(item.edge?'#c6c5d6':'#77788a'))}
  voxels.renderOrder=4;this.cube.add(voxels);
 }
 size(){if(this.closed)return;const w=this.externalCanvas?1280:this.host.clientWidth,h=this.externalCanvas?720:this.host.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h,!this.externalCanvas);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.changed=true;this.renderFrame(performance.now())}
 loop(now){if(this.closed)return;this.raf=requestAnimationFrame(this.loop);try{this.renderFrame(now)}catch{this.onError?.('Не удалось отрисовать 3D. Голосовое управление продолжает работать.');this.close()}}
 renderFrame(now){
  if(document.hidden)return;const signal=this.signal(),off=!signal.enabled,fps=off?8:this.low||this.economy?16:this.quality==='high'?40:signal.phase==='thinking'?20:28;
  if(now-this.last<1000/fps&&!this.changed||off&&this.motion.awake<.056&&!this.changed&&Math.abs(this.gaze.x-this.target.x)+Math.abs(this.gaze.y-this.target.y)<.005)return;const start=performance.now(),dt=Math.min(.12,(now-this.last)/1000);this.last=now;const t=(now-this.clock)/1000;
  const m=this.motion.step({...signal,output:signal.output?.()||{}},t,dt);this.u.uTime.value=t;this.u.uJaw.value=m.jaw;this.u.uRound.value=m.round;this.u.uAwake.value=m.awake;this.u.uAssembly.value=m.assembly;this.u.uDisperse.value=m.bursting?1-m.assembly:0;this.u.uMic.value=m.mic;this.u.uBlink.value=m.blink;this.u.uThinking.value=m.thinking?1:0;
  this.gaze.x=THREE.MathUtils.damp(this.gaze.x,this.target.x,4,dt);this.gaze.y=THREE.MathUtils.damp(this.gaze.y,this.target.y,4,dt);this.u.uGaze.value.set(this.gaze.x,this.gaze.y);
  this.head.rotation.y=(Math.sin(t*.18)*.035+this.gaze.x*.28)*Math.max(.4,m.awake);this.head.rotation.x=(Math.sin(t*.23)*.009+this.gaze.y*.14)*Math.max(.4,m.awake);this.head.rotation.z=Math.sin(t*.17)*.005*m.awake;this.head.position.y=Math.sin(t*.75)*.008*m.awake;
  this.cube.rotation.y=.26+Math.sin(t*.16)*.025*m.awake+this.gaze.x*.035;
  this.renderer.render(this.scene,this.camera);this.changed=false;
  const elapsed=performance.now()-start;this.frameTimes.push(elapsed);if(this.frameTimes.length>40)this.frameTimes.shift();
  if(this.quality==='auto'&&!this.economy&&(this.software||this.frameTimes.length===40&&this.frameTimes.reduce((s,v)=>s+v,0)/40>14)){this.economy=true;this.ratio=1;this.u.uPixelRatio.value=1;this.renderer.setPixelRatio(1);if(this.glow)this.glow.visible=false;this.size();this.onQuality?.('Экономный режим')}
  this.host.__faceDiagnostics={frames:(this.host.__faceDiagnostics?.frames||0)+1,style:'white-lidar-silhouette-voxel-cube',cube:true,cubeVoxels:this.voxelCount,eyes:false,wind:.20,phase:signal.phase,activation:signal.activation,jaw:m.jaw,awake:m.awake,assembly:m.assembly,yaw:this.head.rotation.y,blink:m.blink,gaze:[this.gaze.x,this.gaze.y],cells:this.cellCount,volumeCells:this.volumeCount,width:this.host.clientWidth,height:this.host.clientHeight,drawCalls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles,renderMs:elapsed,fpsLimit:fps,device:this.device};
 }
 close(){this.closed=true;cancelAnimationFrame(this.raf);this.resize.disconnect();this.host.removeEventListener('pointermove',this.pointer);this.host.removeEventListener('pointerleave',this.leave);this.renderer.domElement.removeEventListener('webglcontextlost',this.lost);const geometries=new Set(),materials=new Set();this.scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>materials.add(m))});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());this.renderer.dispose();this.renderer.forceContextLoss();if(!this.externalCanvas)this.renderer.domElement.remove();delete this.host.dataset.faceReady}
}
