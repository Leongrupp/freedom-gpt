import * as T from 'three';
import {localStore} from '../browserStorage.js';
export const windowTypes=[['chat','Диалог'],['code','Код и файлы'],['activity','Действия агента'],['sessions','Мои чаты'],['state','Телеметрия']];
const key='freedom-vr-window-layout',limit=16;
const finite3=v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite);
export function roomLayout(room){
 const defaults=room.panels.map(p=>({id:p.id,kind:p.kind,title:p.title,w:p.w,h:p.h,position:p.mesh.position.toArray(),rotation:p.mesh.rotation.toArray().slice(0,3),scale:1}));
 let selected='chat',editing=false,type='chat';
 const windows=()=>room.panels.filter(p=>p.kind!=='layout');
 const serialize=p=>({id:p.id,kind:p.kind,title:p.title,w:p.w,h:p.h,position:p.mesh.position.toArray(),rotation:p.mesh.rotation.toArray().slice(0,3),scale:p.mesh.scale.x});
 function constrain(p){const m=p.mesh;m.position.x=T.MathUtils.clamp(m.position.x,-7,7);m.position.y=T.MathUtils.clamp(m.position.y,.35,5);m.position.z=T.MathUtils.clamp(m.position.z,-7,7);m.scale.setScalar(T.MathUtils.clamp(m.scale.x,.45,2));m.updateMatrixWorld()}
 function notify(){for(const p of windows())p.mesh.children[0]?.material.color.set(p.id===selected?0x91f3d3:0x526e9d);room.host.dispatchEvent(new CustomEvent('vr-layout',{detail:state()}));const editor=room.panels.find(p=>p.kind==='layout');if(editor)room.paint(editor)}
 function state(){return {selected,editing,type,windows:windows().map(p=>({id:p.id,kind:p.kind,title:p.title,scale:p.mesh.scale.x})),canAdd:windows().length<limit}}
 function save(){localStore.setItem(key,JSON.stringify({version:1,windows:windows().map(serialize)}));notify()}
 function select(id){if(windows().some(p=>p.id===id)){selected=id;notify()}}
 function removeMesh(p){room.targets=room.targets.filter(m=>m!==p.mesh);room.panels=room.panels.filter(v=>v!==p);delete room.pages[p.id];p.mesh.removeFromParent();p.mesh.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});p.texture.dispose()}
 function create(row){const p=room.panel(row.id,row.title,...row.position,row.w,row.h,row.kind);p.mesh.rotation.set(...row.rotation);p.mesh.scale.setScalar(row.scale);constrain(p);room.paint(p);return p}
 function restore(){try{const data=JSON.parse(localStore.getItem(key));if(data?.version!==1||!Array.isArray(data.windows))return;const seen=new Set(),rows=data.windows.slice(0,limit).filter(r=>{
  if(!r||typeof r.id!=='string'||r.id.length>80||r.id==='layout'||seen.has(r.id)||!['controls',...windowTypes.map(t=>t[0])].includes(r.kind)||!finite3(r.position)||!finite3(r.rotation)||!Number.isFinite(r.scale)||!Number.isFinite(r.w)||!Number.isFinite(r.h)||r.w<1||r.w>4||r.h<.4||r.h>3)return false;
  if(r.kind==='controls'&&r.id!=='controls')return false;seen.add(r.id);return true;
 });if(!rows.some(r=>r.id==='controls'&&r.kind==='controls'))return;for(const p of [...windows()])removeMesh(p);for(const row of rows)create({...row,title:row.kind==='controls'?'УПРАВЛЕНИЕ':windowTypes.find(t=>t[0]===row.kind)[1]});selected=windows()[0]?.id}catch{}}
 function add(kind=type){if(!windowTypes.some(t=>t[0]===kind))return;if(windows().length>=limit){room.onError('В комнате уже 16 экранов. Закройте ненужный перед добавлением.');return}const camera=room.renderer.xr.isPresenting?room.renderer.xr.getCamera():room.camera;camera.updateWorldMatrix(true,false);const pos=new T.Vector3(),direction=new T.Vector3();camera.getWorldPosition(pos);camera.getWorldDirection(direction);pos.addScaledVector(direction,2.6);const p=room.panel('window-'+crypto.randomUUID(),windowTypes.find(t=>t[0]===kind)[1],pos.x,pos.y,pos.z,2.4,1.65,kind);camera.getWorldPosition(direction);p.mesh.lookAt(direction);constrain(p);room.paint(p);selected=p.id;save();return p}
 function remove(){const p=windows().find(p=>p.id===selected);if(!p||p.kind==='controls')return;removeMesh(p);selected=windows()[0]?.id;save()}
 function transform(action){const p=windows().find(p=>p.id===selected);if(!p)return;const m=p.mesh;
  const moves={left:[-.2,0,0],right:[.2,0,0],up:[0,.2,0],down:[0,-.2,0]};if(moves[action])m.position.add(new T.Vector3(...moves[action]));
  if(action==='near'||action==='far'){const camera=room.renderer.xr.isPresenting?room.renderer.xr.getCamera():room.camera,origin=new T.Vector3();camera.getWorldPosition(origin);const delta=m.position.clone().sub(origin);delta.setLength(T.MathUtils.clamp(delta.length()+(action==='near'?-.2:.2),.8,8));m.position.copy(origin).add(delta)}
  if(action==='yaw-left')m.rotateY(.12);if(action==='yaw-right')m.rotateY(-.12);if(action==='tilt-up')m.rotateX(.10);if(action==='tilt-down')m.rotateX(-.10);
  if(action==='smaller'||action==='bigger')m.scale.multiplyScalar(action==='smaller'?.9:1.1);
  if(action==='face'){const eye=new T.Vector3();(room.renderer.xr.isPresenting?room.renderer.xr.getCamera():room.camera).getWorldPosition(eye);m.lookAt(eye)}constrain(p);save()
 }
 function reset(){for(const p of [...windows()])removeMesh(p);for(const row of defaults)create(row);selected='chat';save()}
 function toggleEditor(){const existing=room.panels.find(p=>p.kind==='layout');if(existing){removeMesh(existing);editing=false}else{const camera=room.renderer.xr.isPresenting?room.renderer.xr.getCamera():room.camera,eye=new T.Vector3(),direction=new T.Vector3();camera.getWorldPosition(eye);camera.getWorldDirection(direction);const pos=eye.clone().addScaledVector(direction,1.75);const p=room.panel('layout','МОЯ КОМНАТА',...pos.toArray(),2.3,1.65,'layout');p.mesh.lookAt(eye);editing=true;room.paint(p)}notify()}
 function action(action){if(action==='editor'){toggleEditor();return}if(action==='new'){add();return}if(action==='remove'){remove();return}if(action==='reset'){reset();return}if(action==='type'){type=windowTypes[(windowTypes.findIndex(t=>t[0]===type)+1)%windowTypes.length][0];notify();return}if(action==='next'){const list=windows();select(list[(list.findIndex(p=>p.id===selected)+1)%list.length].id);return}transform(action)}
 function paint(p,c,w,h){const current=windows().find(p=>p.id===selected);c.font='24px sans-serif';c.fillStyle='#bad4e8';c.fillText('Выбран: '+(current?.title||'Экран'),30,115);const buttons=[['Следующее окно','next'],['Тип: '+windowTypes.find(t=>t[0]===type)[1],'type'],['+ Новый экран','new'],['← Влево','left'],['Выше','up'],['Вправо →','right'],['Ближе','near'],['Ниже','down'],['Дальше','far'],['Повернуть ↶','yaw-left'],['Наклон ↑','tilt-up'],['Повернуть ↷','yaw-right'],['Меньше','smaller'],['Наклон ↓','tilt-down'],['Больше','bigger'],['Ко мне','face'],['Закрыть окно','remove'],['Сброс окон','reset'],['Сменить комнату','environment'],['Выбрать взглядом: заголовок','help'],['Готово','editor']];
  buttons.forEach(([label,action],i)=>{const x=22+(i%3)*394,y=145+Math.floor(i/3)*95;c.fillStyle='#20374c';c.fillRect(x,y,380,78);c.fillStyle=action==='remove'&&current?.kind==='controls'?'#758395':'#d5edf8';c.font=action==='help'?'17px sans-serif':'23px sans-serif';c.fillText(label,x+12,y+47);p.rows.push({x,y,w:380,h:78,action:action==='environment'?'environment':'layout:'+action})});room.dirty(p)
 }
 restore();return {state,select,save,constrain,add,remove,reset,transform,toggleEditor,action,paint,setEditing(value){editing=value;notify()},setType(value){if(windowTypes.some(t=>t[0]===value)){type=value;notify()}},get editing(){return editing}};
}
