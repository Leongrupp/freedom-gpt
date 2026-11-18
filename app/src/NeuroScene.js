import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {positionsFor} from './neuroGraph.js';

const palette={project:'#a993ef',chat:'#7eaac7',task:'#d4b77a',goal:'#c1a6ed',memory:'#83cdb8',file:'#8da4c4',skill:'#9bafdc',group:'#7f819e'};
export class NeuroScene{
 constructor(host,{onSelect,onHover,onQuality,onError,cameraState,onCamera,quality='auto'}){
  this.host=host;this.options={onSelect,onHover,onQuality,onError,onCamera};this.closed=false;this.dirty=true;this.quality=quality;this.maxFps=quality==='high'?40:quality==='low'?12:24;this.live={phase:'off',level:0};this.scene=new THREE.Scene();
  this.renderer=new THREE.WebGLRenderer({alpha:true,antialias:quality!=='low',powerPreference:'low-power',preserveDrawingBuffer:false});
  this.renderer.setClearColor(0x000000,0);this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.1;
  this.renderer.setPixelRatio(quality==='low'?1:Math.min(devicePixelRatio,1.25));this.renderer.domElement.setAttribute('aria-label','Трёхмерная карта проектов');host.appendChild(this.renderer.domElement);
  this.camera=new THREE.PerspectiveCamera(42,1,.1,100);this.camera.position.set(24,13,28);
  this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.enableDamping=true;this.controls.dampingFactor=.12;this.controls.rotateSpeed=.55;this.controls.panSpeed=.7;this.controls.zoomSpeed=.85;this.controls.zoomToCursor=true;this.controls.minDistance=1.2;this.controls.maxDistance=65;this.controls.maxPolarAngle=Math.PI*.92;this.controls.minPolarAngle=.1;this.controls.autoRotateSpeed=.35;this.rotating=true;
  this.controls.addEventListener('change',()=>{this.dirty=true;if(!this.inAutomaticUpdate){const value={position:this.camera.position.toArray(),target:this.controls.target.toArray()};clearTimeout(this.saveTimer);this.saveTimer=setTimeout(()=>this.options.onCamera?.(value),200)}});
  this.controls.addEventListener('start',()=>{this.transition=null;this.interacting=true;this.options.onHover?.(null)});this.controls.addEventListener('end',()=>{this.interacting=false;this.lastInteraction=performance.now()});
  if(cameraState?.position?.length===3&&cameraState?.target?.length===3){this.camera.position.fromArray(cameraState.position);this.controls.target.fromArray(cameraState.target);this.controls.update()}
  this.scene.add(new THREE.HemisphereLight(0xb4c7ef,0x17111a,2));
  const key=new THREE.DirectionalLight(0xffdfaa,4);key.position.set(4,7,5);this.scene.add(key);
  const rim=new THREE.DirectionalLight(0x9a93fb,3);rim.position.set(-5,2,-3);this.scene.add(rim);
  const fill=new THREE.DirectionalLight(0x8dcfcf,1.1);fill.position.set(1,-2,6);this.scene.add(fill);
  this.core=new THREE.Group();this.scene.add(this.core);this.sceneObjects=[];
  this.makeAtmosphere();this.makeStar();this.raycaster=new THREE.Raycaster();this.pointer=new THREE.Vector2();this.nodes=[];this.positions=new Map();
  this.down=e=>{this.downAt=[e.clientX,e.clientY]};this.up=e=>{if(e.button===0&&this.downAt&&Math.hypot(e.clientX-this.downAt[0],e.clientY-this.downAt[1])<5)this.pick(e,true)};this.move=e=>{if(!this.interacting)this.pick(e,false)};
  this.renderer.domElement.addEventListener('pointerdown',this.down);this.renderer.domElement.addEventListener('pointerup',this.up);this.renderer.domElement.addEventListener('pointermove',this.move);
  this.leave=()=>this.options.onHover?.(null);this.renderer.domElement.addEventListener('pointerleave',this.leave);
  this.contextLost=e=>{e.preventDefault();if(!this.closed)this.options.onError?.('Графический контекст потерян. Доступна двумерная карта.')};this.renderer.domElement.addEventListener('webglcontextlost',this.contextLost);
  this.resize=new ResizeObserver(()=>this.size());this.resize.observe(host);this.size();this.start=performance.now();this.last=0;this.frames=[];this.loop=this.loop.bind(this);this.raf=requestAnimationFrame(this.loop);
 }
 makeAtmosphere(){
  const positions=[];for(let i=0;i<180;i++){const a=i*2.399963,y=((i*71)%180)/180*16-8,r=11+(i%7)*.65;positions.push(Math.cos(a)*r,y,Math.sin(a)*r)}
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));this.scene.add(new THREE.Points(geometry,new THREE.PointsMaterial({color:0xa6b6d3,size:.018,transparent:true,opacity:.3,depthWrite:false})));
  this.coreGlow=new THREE.PointLight(0xe1b777,0,5);this.coreGlow.position.set(.1,.5,0);this.scene.add(this.coreGlow);
 }
 makeStar(){
  const vertex=`varying vec3 vPoint; varying vec3 vNormal; void main(){vPoint=position;vNormal=normal;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
  const fragment=`precision highp float; varying vec3 vPoint; varying vec3 vNormal; uniform float uTime; uniform float uEnergy;
   float hash(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
   float noise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
   void main(){vec3 p=normalize(vPoint);float n=noise(p*9.0+vec3(uTime*.025,uTime*.013,0));n+=.5*noise(p*23.0+uTime*.02);n+=.25*noise(p*61.0-uTime*.015);float heat=smoothstep(.15,1.5,n);vec3 color=mix(vec3(.46,.23,.15),vec3(.9,.64,.44),heat);color+=uEnergy*vec3(.04,.025,.02);gl_FragColor=vec4(color,1.0);}`;
  this.starMaterial=new THREE.ShaderMaterial({vertexShader:vertex,fragmentShader:fragment,uniforms:{uTime:{value:0},uEnergy:{value:0}}});
  this.star=new THREE.Mesh(new THREE.SphereGeometry(.42,40,28),this.starMaterial);this.star.userData.pickCore=true;this.core.add(this.star);
  this.coronaMaterial=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uTime:{value:0},uEnergy:{value:0}},vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,fragmentShader:`precision highp float;varying vec2 vUv;uniform float uTime;uniform float uEnergy;void main(){float r=length((vUv-.5)*2.0);float halo=(exp(-r*7.0)*.19+exp(-abs(r-.3)*9.0)*.14)*(1.0-smoothstep(.55,1.0,r));gl_FragColor=vec4(vec3(.67,.39,.27),halo*(1.0+uEnergy*.2));}`});

  this.corona=new THREE.Mesh(new THREE.PlaneGeometry(2.6,2.6),this.coronaMaterial);this.corona.renderOrder=-1;this.core.add(this.corona);
  this.host.dataset.neuroReady='true';
 }
 size(){const width=this.host.clientWidth,height=this.host.clientHeight;if(!width||!height)return;this.renderer.setSize(width,height);this.camera.aspect=width/height;this.camera.updateProjectionMatrix();this.dirty=true;if(this.nodes&&!this.closed)this.renderer.render(this.scene,this.camera)}
 setGraph(nodes,links){
  this.nodes=nodes;this.positions=positionsFor(nodes,links);this.graphLinks=links;
  for(const object of this.sceneObjects){this.scene.remove(object);object.geometry?.dispose();if(object.material?.map)object.material.map.dispose();if(Array.isArray(object.material))object.material.forEach(m=>m.dispose());else object.material?.dispose()}
  this.sceneObjects=[];this.labelNodes=nodes.filter(n=>n.id!=='core');
  const geometry=new THREE.SphereGeometry(1,12,8),material=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.65,metalness:.05,emissive:0x0b090f,emissiveIntensity:.2});
  this.spheres=new THREE.InstancedMesh(geometry,material,this.labelNodes.length);this.spheres.instanceMatrix.setUsage(THREE.DynamicDrawUsage);const matrix=new THREE.Matrix4();
  for(let i=0;i<this.labelNodes.length;i++){
   const node=this.labelNodes[i],p=this.positions.get(node.id),size=node.type==='category'?.27:node.visualChild?.045:node.type==='project'?.10+Math.min(.09,Math.log2(1+(node.chatsCount||0))*.019):node.type==='group'?.13:node.type==='task'?.075:.06;
   matrix.compose(new THREE.Vector3(...p),new THREE.Quaternion(),new THREE.Vector3(size,size,size));this.spheres.setMatrixAt(i,matrix);this.spheres.setColorAt(i,new THREE.Color(node.status==='error'?'#e28b7f':['complete','suggested'].includes(node.status)?'#83cbb6':node.visualColor||palette[node.type]||'#a993ef'));
  }
  this.scene.add(this.spheres);this.sceneObjects.push(this.spheres);
  const positions=[],edgeColors=[];this.curves=[];
  for(const edge of links){const a=this.positions.get(edge.from),b=this.positions.get(edge.to);if(!a||!b)continue;const curve=new THREE.LineCurve3(new THREE.Vector3(...a),new THREE.Vector3(...b));this.curves.push({curve,edge});positions.push(...a,...b);const color=new THREE.Color(edge.suggested||edge.proposed?'#63dfad':nodes.find(n=>n.id===edge.to)?.visualColor||'#9a8bb9');edgeColors.push(color.r,color.g,color.b,color.r,color.g,color.b)}
  const lines=new THREE.BufferGeometry();lines.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));lines.setAttribute('color',new THREE.Float32BufferAttribute(edgeColors,3));const line=new THREE.LineSegments(lines,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.3}));this.scene.add(line);this.sceneObjects.push(line);
  this.pulses=new THREE.InstancedMesh(new THREE.SphereGeometry(.045,8,6),new THREE.MeshBasicMaterial({color:0xf3ce8d}),Math.max(1,this.curves.length));this.pulses.count=0;this.scene.add(this.pulses);this.sceneObjects.push(this.pulses);
  this.marker=new THREE.Mesh(new THREE.TorusGeometry(.29,.008,6,64),new THREE.MeshBasicMaterial({color:0xe2c59c,transparent:true,opacity:.8}));this.marker.visible=false;this.scene.add(this.marker);this.sceneObjects.push(this.marker);this.dirty=true;
  this.labels=[];this.categoryHalos=[];
  const categories=this.labelNodes.filter(n=>n.type==='category');
  for(const node of categories){
   const c=document.createElement('canvas');c.width=c.height=128;const ctx=c.getContext('2d'),g=ctx.createRadialGradient(64,64,2,64,64,62);g.addColorStop(0,node.visualColor+'aa');g.addColorStop(.2,node.visualColor+'55');g.addColorStop(1,node.visualColor+'00');ctx.fillStyle=g;ctx.fillRect(0,0,128,128);
   const texture=new THREE.CanvasTexture(c),halo=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending}));halo.position.set(...this.positions.get(node.id));halo.scale.set(1.8,1.8,1);this.scene.add(halo);this.sceneObjects.push(halo);this.categoryHalos.push(halo);
  }
  const labelled=[...categories,...this.labelNodes.filter(n=>n.type!=='category'&&!n.visualChild).slice(0,80),...this.labelNodes.filter(n=>n.visualChild).slice(0,24)];
  for(const node of labelled){
   const canvas=document.createElement('canvas');canvas.width=512;canvas.height=64;const ctx=canvas.getContext('2d');ctx.font=(node.type==='category'?'500 28px':'24px')+' system-ui';ctx.textAlign='center';ctx.fillStyle=node.visualColor||'#b3b1c4';ctx.shadowColor='#080a12';ctx.shadowBlur=5;ctx.fillText(String(node.title).slice(0,32),256,38);
   const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;const label=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthWrite:false,depthTest:false,sizeAttenuation:false,opacity:.95}));const p=this.positions.get(node.id);label.position.set(p[0],p[1]-(node.type==='category'?.7:.28),p[2]);label.scale.set(node.type==='category'?.34:node.visualChild?.21:.26,node.type==='category'?.0425:node.visualChild?.02625:.0325,1);label.userData.node=node;label.renderOrder=2;this.scene.add(label);this.sceneObjects.push(label);this.labels.push(label);
  }

 }
 setLabels(value){this.showLabels=!!value;this.dirty=true}
 setLive(live){
  const limit=this.quality==='auto'&&(live.agentBusy||live.gpuPressure);
  if(this.pixelLimited!==limit){this.pixelLimited=limit;if(this.quality==='auto'){this.renderer.setPixelRatio(limit?1:Math.min(devicePixelRatio,1.25));this.size();this.options.onQuality?.(limit?'Экономный режим во время нагрузки':'')}}
  this.live=live;this.dirty=true;
 }
 setRotation(value){this.rotating=!!value;if(!value)this.clearMotion();this.controls.autoRotate=false;this.dirty=true}
 select(id){this.selected=id;this.dirty=true;const pos=this.positions.get(id);if(this.marker){this.marker.visible=!!pos&&id!=='core';if(pos)this.marker.position.set(...pos)}}
 clearMotion(){this.controls.autoRotate=false;this.controls.enableDamping=false;this.controls.update();this.controls.enableDamping=true;this.lastInteraction=performance.now()}
 focus(id){const p=this.positions.get(id);if(!p)return;this.clearMotion();const target=new THREE.Vector3(...p),offset=this.camera.position.clone().sub(this.controls.target).normalize().multiplyScalar(id==='core'?39:this.nodes.find(n=>n.id===id)?.type==='category'?16:4.8);this.transition={start:performance.now(),position:this.camera.position.clone(),target:this.controls.target.clone(),to:target.clone().add(offset),toTarget:target};this.dirty=true}
 restoreCamera(value){if(!value)return this.reset();this.clearMotion();this.transition=null;this.camera.position.fromArray(value.position);this.controls.target.fromArray(value.target);this.controls.update();this.dirty=true}
 reset(){this.clearMotion();this.transition=null;this.camera.position.set(24,13,28);this.controls.target.set(0,0,0);this.controls.update();this.select(null);this.dirty=true}
 pick(event,select){
  const rect=this.renderer.domElement.getBoundingClientRect();this.pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);this.raycaster.setFromCamera(this.pointer,this.camera);
  const hit=this.spheres&&this.raycaster.intersectObject(this.spheres)[0],coreHit=this.raycaster.intersectObject(this.star)[0];let node=coreHit&&(!hit||coreHit.distance<hit.distance)?this.nodes.find(n=>n.id==='core'):hit?this.labelNodes[hit.instanceId]:null;
  if(!node){let nearest=10;for(const candidate of this.nodes){const pos=this.positions.get(candidate.id);if(!pos)continue;const projected=new THREE.Vector3(...pos).project(this.camera);if(projected.z<-1||projected.z>1)continue;const distance=Math.hypot((projected.x-this.pointer.x)*rect.width/2,(projected.y-this.pointer.y)*rect.height/2);if(distance<nearest){node=candidate;nearest=distance}}}
  if(select){if(node){this.select(node.id);this.options.onSelect?.(node.id)}}
  else{this.renderer.domElement.style.cursor=node?'pointer':'grab';this.options.onHover?.(node?{id:node.id,title:node.title,x:event.clientX-rect.left,y:event.clientY-rect.top}:null)}
 }
 loop(now){
  if(this.closed)return;this.raf=requestAnimationFrame(this.loop);if(document.hidden)return;
  const active=['listening','recognizing','processing','working','speaking'].includes(this.live.phase),moving=this.rotating||!!this.transition||this.interacting||this.inertia||now-(this.lastInteraction||0)<1800||active&&this.live.phase!=='listening'||this.live.level>.02;
  const fps=this.quality!=='low'&&(this.interacting||this.transition||this.inertia)?30:(this.live.agentBusy||this.live.gpuPressure)&&this.quality==='auto'?12:this.maxFps;if(now-this.last<1000/fps||!this.dirty&&!moving)return;const delta=Math.min(.12,(now-this.last)/1000);this.last=now;
  const start=performance.now(),t=(now-this.start)/1000;
  this.controls.autoRotate=false;
  if(this.transition){const move=this.transition,k=Math.min(1,(now-move.start)/800),smooth=k*k*(3-2*k);this.camera.position.copy(move.position).lerp(move.to,smooth);this.controls.target.copy(move.target).lerp(move.toTarget,smooth);this.controls.update();if(k===1)this.transition=null}
  this.controls.autoRotate=this.rotating&&!this.interacting&&!this.transition&&now-(this.lastInteraction||0)>3000;this.inAutomaticUpdate=this.controls.autoRotate;this.inertia=this.controls.update(delta)&&!this.controls.autoRotate;this.inAutomaticUpdate=false;
  if(this.pulses){const relevant=this.curves.filter(({edge})=>this.nodes.find(n=>n.id===edge.to)?.status==='active'||edge.to===this.live.activeNode);this.pulses.count=moving?relevant.length:0;const matrix=new THREE.Matrix4();for(let i=0;i<this.pulses.count;i++){matrix.makeTranslation(...relevant[i].curve.getPoint((t*.38+i*.2)%1).toArray());this.pulses.setMatrixAt(i,matrix)}this.pulses.instanceMatrix.needsUpdate=true}
  if(this.marker?.visible)this.marker.quaternion.copy(this.camera.quaternion);
  const energy=this.live.phase==='speaking'?this.live.outputLevel?.()||0:this.live.level||0;
  this.coreGlow.intensity=.2+(active ? .1+energy*.3 : 0);
  this.starMaterial.uniforms.uTime.value=t;this.starMaterial.uniforms.uEnergy.value=energy;this.star.rotation.y=t*.035;this.coronaMaterial.uniforms.uTime.value=t;this.coronaMaterial.uniforms.uEnergy.value=energy;this.corona.quaternion.copy(this.camera.quaternion);
  const occupied=[];
  for(const label of this.labels||[]){const n=label.userData.node,distance=this.camera.position.distanceTo(label.position);label.visible=this.showLabels!==false&&(n.type==='category'||distance<(n.visualChild?10:24));if(!label.visible)continue;const p=label.position.clone().project(this.camera),x=(p.x+1)*this.host.clientWidth/2,y=(1-p.y)*this.host.clientHeight/2,w=n.type==='category'?112:82;label.visible=p.z>-1&&p.z<1&&Math.abs(p.x)<1&&Math.abs(p.y)<1&&!occupied.some(r=>Math.abs(r.x-x)<(r.w+w)/2&&Math.abs(r.y-y)<15);if(label.visible)occupied.push({x,y,w});}

  this.renderer.render(this.scene,this.camera);this.dirty=false;
  const elapsed=performance.now()-start;this.frames.push(elapsed);if(this.frames.length>30)this.frames.shift();
  if(this.quality==='auto'&&this.frames.length===30&&this.frames.reduce((a,b)=>a+b)/30>18&&this.maxFps>12){this.maxFps=12;this.renderer.setPixelRatio(1);this.size();this.options.onQuality?.('Снижено автоматически: экономия ресурсов')}
  this.diagnostics={frames:(this.diagnostics?.frames||0)+1,width:this.host.clientWidth,height:this.host.clientHeight,drawCalls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles,geometries:this.renderer.info.memory.geometries,textures:this.renderer.info.memory.textures,renderMs:elapsed,fpsLimit:fps,rotating:this.rotating,camera:this.camera.position.toArray()};
  Object.assign(this.diagnostics,{categoryStars:(this.categoryHalos||[]).length,visibleLabels:(this.labels||[]).filter(l=>l.visible).length,nestedSpheres:this.labelNodes.filter(n=>n.visualChild).length,starRadius:.42,straightEdges:this.curves.length,edgeVertices:this.curves.length*2,target:this.controls.target.toArray()});this.host.__neuroDiagnostics=this.diagnostics;
 }
 close(){this.closed=true;cancelAnimationFrame(this.raf);clearTimeout(this.saveTimer);this.resize.disconnect();this.controls.dispose();this.scene.traverse(o=>{o.geometry?.dispose();if(o.material){(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>{m.map?.dispose();m.dispose()})}});this.renderer.dispose();this.renderer.forceContextLoss();this.renderer.domElement.remove()}
}
