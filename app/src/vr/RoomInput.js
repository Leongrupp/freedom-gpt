import * as T from 'three';
import {localStore} from '../browserStorage.js';

const positionKey='freedom-vr-archi-position';
const home=[1.2,1.45,-1.9];
export function roomInput(room){
 const {host,camera,rig,hologram}=room,canvas=room.renderer.domElement;
 const keys=new Set(),ray=new T.Raycaster(),pointer=new T.Vector2(),plane=new T.Plane();
 const point=new T.Vector3(),offset=new T.Vector3(),normal=new T.Vector3();let drag=null,last=0;
 const activeCamera=()=>room.renderer.xr.isPresenting?room.renderer.xr.getCamera():camera;
 const bounds=()=>{const p=hologram.mesh.position;p.x=T.MathUtils.clamp(p.x,-6,6);p.y=T.MathUtils.clamp(p.y,.65,3);p.z=T.MathUtils.clamp(p.z,-6,3)};
 const save=()=>localStore.setItem(positionKey,JSON.stringify(hologram.mesh.position.toArray()));
 const reset=()=>{hologram.mesh.position.fromArray(home);save()};
 try{const saved=JSON.parse(localStore.getItem(positionKey));if(Array.isArray(saved)&&saved.length===3&&saved.every(Number.isFinite)){hologram.mesh.position.fromArray(saved);bounds()}else reset()}catch{reset()}
 // A small invisible picking surface avoids selecting thousands of individual particles.
 const handle=new T.Mesh(new T.SphereGeometry(1,16,12),new T.MeshBasicMaterial({visible:false}));handle.scale.set(.48,.64,.35);room.scene.add(handle);
 function aim(e){const b=canvas.getBoundingClientRect();pointer.set((e.clientX-b.left)/b.width*2-1,1-(e.clientY-b.top)/b.height*2);const view=activeCamera();view.updateWorldMatrix(true,false);ray.setFromCamera(pointer,view);handle.position.copy(hologram.mesh.position);handle.updateMatrixWorld();return ray.intersectObjects([handle,...room.targets],false)[0]}
 function info(hit){const p=hit?.object.userData.panel;if(!p)return {face:hit?.object===handle};const x=hit.uv.x*p.canvas.width,y=(1-hit.uv.y)*p.canvas.height;return {panel:p,header:y<75,row:p.rows.find(r=>x>=r.x&&x<=r.x+r.w&&y>=r.y&&y<=r.y+r.h)}}
 function down(e){if(drag||![0,2].includes(e.button))return;e.preventDefault();canvas.focus({preventScroll:true});const target=info(aim(e)),panel=e.button===0?target.panel:null;
  if(panel&&panel.kind!=='layout')room.layout.select(panel.id);
  const movable=panel&&(target.header||e.altKey||room.layout.editing&&!target.row);
  drag={id:e.pointerId,x:e.clientX,y:e.clientY,yaw:room.yaw,pitch:room.pitch,rigYaw:rig.rotation.y,moved:false,face:e.button===0&&target.face,panel:movable?panel:null,rotate:movable&&e.altKey,rotation:panel?.mesh.rotation.clone(),click:!!panel};
  const mesh=drag.face?hologram.mesh:drag.panel?.mesh;
  if(mesh){activeCamera().getWorldDirection(normal);plane.setFromNormalAndCoplanarPoint(normal,mesh.position);ray.ray.intersectPlane(plane,point);offset.copy(mesh.position).sub(point)}canvas.setPointerCapture(e.pointerId);canvas.style.cursor=mesh?'grabbing':'move';
 }
 function move(e){if(!drag){const target=info(aim(e));canvas.style.cursor=target.face||target.header||target.panel&&room.layout.editing&&!target.row?'grab':target.row?'pointer':'';return}if(e.pointerId!==drag.id)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.moved ||= Math.abs(dx)+Math.abs(dy)>5;
  if(drag.rotate){drag.panel.mesh.rotation.set(drag.rotation.x+dy*.006,drag.rotation.y+dx*.006,drag.rotation.z)}
  else if(drag.face||drag.panel){aim(e);if(ray.ray.intersectPlane(plane,point)){const mesh=drag.face?hologram.mesh:drag.panel.mesh;mesh.position.copy(point).add(offset);if(drag.face)bounds();else room.layout.constrain(drag.panel)}}
  else if(!drag.click){if(room.renderer.xr.isPresenting)rig.rotation.y=drag.rigYaw-dx*.003;else{room.yaw=drag.yaw-dx*.003;room.pitch=T.MathUtils.clamp(drag.pitch-dy*.003,-.85,.85)}}
 }
 function finish(e){if(!drag||e.pointerId!==drag.id)return;const current=drag;drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);canvas.style.cursor='';if(current.face)save();if(current.panel)room.layout.save();if(!current.face&&!current.moved&&e.button===0&&e.type==='pointerup'){aim(e);room.ray.ray.copy(ray.ray);room.hit(true)}}
 function wheel(e){if(drag){e.preventDefault();return}const target=info(aim(e)),mesh=target.face?hologram.mesh:target.panel?.mesh;if(!mesh)return;e.preventDefault();
  if(target.panel&&e.shiftKey)mesh.scale.multiplyScalar(Math.exp(-e.deltaY*.001));else{activeCamera().getWorldPosition(point);offset.copy(mesh.position).sub(point);offset.setLength(T.MathUtils.clamp(offset.length()+e.deltaY*.002,.85,target.face?5:8));mesh.position.copy(point).add(offset)}
  if(target.face){bounds();save()}else{room.layout.constrain(target.panel);room.layout.save()}
 }
 const editable=e=>e.target?.closest?.('input,textarea,select,button,[contenteditable="true"]');
 const key=e=>{if(editable(e))return;const code=e.code;if(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown'].includes(code)){e.preventDefault();keys.add(code)}if(e.repeat)return;if(code==='Enter'){e.preventDefault();room.gaze(true)}if(code==='ArrowLeft'){e.preventDefault();room.snap(-1)}if(code==='ArrowRight'){e.preventDefault();room.snap(1)}if(code==='Escape')room.end();if(code==='KeyR')room.reset();if(code==='KeyH')reset()};
 const keyup=e=>keys.delete(e.code),blur=()=>{keys.clear();if(drag)finish({pointerId:drag.id,type:'cancel'})},context=e=>e.preventDefault();
 canvas.addEventListener('pointerdown',down);canvas.addEventListener('pointermove',move);canvas.addEventListener('pointerup',finish);canvas.addEventListener('pointercancel',finish);canvas.addEventListener('lostpointercapture',finish);canvas.addEventListener('wheel',wheel,{passive:false});canvas.addEventListener('contextmenu',context);canvas.style.touchAction='none';canvas.tabIndex=0;canvas.style.outline='none';canvas.setAttribute('aria-label','VR-пространство: мышь и клавиатура');
 window.addEventListener('keydown',key);window.addEventListener('keyup',keyup);window.addEventListener('blur',blur);
 return {reset,tick(t){const dt=Math.min(.05,Math.max(0,(t-last)/1000));last=t;if(drag)return;const forward=Number(keys.has('KeyW')||keys.has('ArrowUp'))-Number(keys.has('KeyS')||keys.has('ArrowDown')),side=Number(keys.has('KeyD'))-Number(keys.has('KeyA'));if(!forward&&!side)return;activeCamera().getWorldDirection(normal);normal.y=0;normal.normalize();offset.crossVectors(normal,T.Object3D.DEFAULT_UP).normalize();point.copy(normal).multiplyScalar(forward).addScaledVector(offset,side).normalize();rig.position.addScaledVector(point,dt*1.4);rig.position.x=T.MathUtils.clamp(rig.position.x,-5,5);rig.position.z=T.MathUtils.clamp(rig.position.z,-5,5)},dispose(){blur();canvas.removeEventListener('pointerdown',down);canvas.removeEventListener('pointermove',move);canvas.removeEventListener('pointerup',finish);canvas.removeEventListener('pointercancel',finish);canvas.removeEventListener('lostpointercapture',finish);canvas.removeEventListener('wheel',wheel);canvas.removeEventListener('contextmenu',context);window.removeEventListener('keydown',key);window.removeEventListener('keyup',keyup);window.removeEventListener('blur',blur);handle.removeFromParent();handle.geometry.dispose();handle.material.dispose()}};
}
