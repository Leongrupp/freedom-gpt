import * as T from 'three';
export const environments=[{id:'original',name:'Ночная смена'},{id:'matrix',name:'Матрица'},{id:'studio',name:'Кабинет программиста'},{id:'cyberpunk',name:'Киберпанк · 2077'},{id:'penthouse',name:'Пентхаус · городской закат'}];
export function disposeEnvironment(group){const g=new Set(),m=new Set(),textures=new Set();group.traverse(o=>{if(o.geometry)g.add(o.geometry);if(o.material)for(const mat of Array.isArray(o.material)?o.material:[o.material])m.add(mat)});m.forEach(mat=>{for(const v of Object.values(mat))if(v?.isTexture)textures.add(v);mat.dispose()});textures.forEach(t=>t.dispose());g.forEach(v=>v.dispose());group.removeFromParent()}
export function makeEnvironment(id,{onError=()=>{},anisotropy=8}={}){
 const root=new T.Group(),animated=[];let seed=42;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
 const cyber=id==='cyberpunk',pent=id==='penthouse',matrix=id==='matrix',studio=id==='studio';
 const accent=matrix?0x42f693:cyber?0xff36ba:pent?0xffcc8f:0x71b5e5;
 const basic=(color)=>new T.MeshBasicMaterial({color});const standard=(color,roughness=.6,metalness=.15)=>new T.MeshStandardMaterial({color,roughness,metalness});
 function box(x,y,z,w,h,d,mat){const o=new T.Mesh(new T.BoxGeometry(w,h,d),mat);o.position.set(x,y,z);root.add(o);return o}
 function pbr(name,repeat,color){const load=(type)=>{const t=new T.TextureLoader().load('/assets/vr/materials/'+name+'_'+type+'.jpg',undefined,()=>{},()=>onError('Не загрузилась текстура '+name));t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(repeat,repeat);t.anisotropy=anisotropy;if(type==='diff')t.colorSpace=T.SRGBColorSpace;return t};return new T.MeshStandardMaterial({color,map:load('diff'),normalMap:load('nor_gl'),roughnessMap:load('rough'),roughness:.8,metalness:name==='metal_plate'?.65:.05,normalScale:new T.Vector2(.55,.55)})}
 const floor=pbr(pent||studio?'wood_floor':'metal_plate',5,pent?0xc5a594:studio?0x8999aa:0x546375),wall=pbr('concrete_floor',3,cyber?0x565b76:pent?0xb5a49a:0x71818b),dark=standard(0x111c28,.35,.7),trim=basic(accent);
 box(0,-.12,0,16,.2,16,floor);box(0,6.2,0,16,.2,16,dark);
 for(const side of [-1,1]){box(side*7.9,3,0,.2,6,16,wall);box(0,.4,side*7.9,16,.8,.2,wall);box(0,5.8,side*7.9,16,.6,.2,dark);for(let x=-7.5;x<=7.5;x+=3)box(x,3.25,side*7.8,.1,5.2,.18,dark);box(0,.85,side*7.7,16,.04,.04,trim);box(side*7.75,.1,0,.04,.03,16,trim)}
 // Recessed acoustic ceiling, mullions and architectural light strips.
 for(let i=-3;i<=3;i++){box(i*2.1,6,0,.08,.3,15,dark);box(i*2.1,5.81,0,.035,.015,12,trim)}
 const hemi=new T.HemisphereLight(pent?0xffd4a8:matrix?0x84d5aa:0x93b8e4,0x111522,pent?2.5:1.2);root.add(hemi);
 for(const x of [-5,5]){const light=new T.PointLight(accent,cyber?65:45,18,2);light.position.set(x,3.7,-4);root.add(light)}
 const canvas=document.createElement('canvas');canvas.width=canvas.height=1024;const c=canvas.getContext('2d');c.fillStyle='#060a13';c.fillRect(0,0,1024,1024);
 for(let y=0;y<1024;y+=32)for(let x=0;x<1024;x+=24){c.fillStyle=random()>.45?(pent?'#d8a267':cyber?(random()>.5?'#5bafc5':'#ae538e'):'#759ca6'):'#101b27';c.fillRect(x+4,y+4,11,18)}
 const windows=new T.CanvasTexture(canvas);windows.colorSpace=T.SRGBColorSpace;windows.wrapS=windows.wrapT=T.RepeatWrapping;
 const citymat=new T.MeshStandardMaterial({color:0x596576,map:windows,emissive:0xffffff,emissiveMap:windows,emissiveIntensity:pent?.35:.8,roughness:.7});citymat.onBeforeCompile=shader=>{shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>',`#include <uv_vertex>
#ifdef USE_INSTANCING
vec2 windowRepeat=vec2(length(instanceMatrix[0].xyz)*.16,length(instanceMatrix[1].xyz)*.07);
vMapUv*=windowRepeat;vEmissiveMapUv*=windowRepeat;
#endif`)};const city=new T.InstancedMesh(new T.BoxGeometry(1,1,1),citymat,72),mat=new T.Matrix4();
 for(let i=0;i<72;i++){const a=i/72*Math.PI*2,r=(pent?26:18)+random()*20,h=(pent?4:5)+random()*(pent?18:28),w=1.5+random()*4;mat.compose(new T.Vector3(Math.sin(a)*r,h/2-6,Math.cos(a)*r),new T.Quaternion(),new T.Vector3(w,h,w));city.setMatrixAt(i,mat)}root.add(city);
 if(pent){const sun=new T.Mesh(new T.SphereGeometry(4,24,16),basic(0xf5af70));sun.position.set(4,9,-43);root.add(sun);const light=new T.DirectionalLight(0xffbe83,2);light.position.set(4,8,-15);root.add(light)}
 function sofa(x,z,rotation){const g=new T.Group();const fabric=standard(pent?0xa99483:0x18293c,.92,0);const base=new T.Mesh(new T.BoxGeometry(3,.45,1),fabric);base.position.y=.45;g.add(base);for(const sx of [-1.4,1.4]){const arm=new T.Mesh(new T.BoxGeometry(.2,.65,1.1),fabric);arm.position.set(sx,.67,0);g.add(arm)}for(const sx of [-.9,0,.9]){const cushion=new T.Mesh(new T.BoxGeometry(.85,.2,.85),fabric);cushion.position.set(sx,.77,-.05);g.add(cushion)}const back=new T.Mesh(new T.BoxGeometry(3,1,.2),fabric);back.position.set(0,1,.5);g.add(back);g.position.set(x,0,z);g.rotation.y=rotation;root.add(g)}
 sofa(pent?4.8:5.6,4.8,-.7);box(3.8,.5,3.5,2,.12,.85,pbr('wood_floor',1,0x756659));for(const x of [3,4.6])box(x,.22,3.5,.1,.5,.65,dark);
 // Side workbench, books and a tower PC: all stand outside the interactive monitor volume.
 box(-6,1,2,2.5,.13,3,studio?floor:dark);for(const x of [-7,-5])for(const z of [1,3])box(x,.5,z,.08,1,.08,dark);
 for(let i=0;i<9;i++)box(-6.9+i*.16,1.3,2.9,.12,.4+random()*.15,.38,standard(new T.Color().setHSL(random(),.25,.35)));
 box(-5.4,1.55,2.3,.65,1,.8,dark);for(let i=0;i<3;i++){const fan=new T.Mesh(new T.TorusGeometry(.18,.012,6,32),trim);fan.position.set(-5.4,1.22+i*.3,1.89);root.add(fan)}
 for(const x of [-6.5,6.5]){const pot=new T.Mesh(new T.CylinderGeometry(.35,.25,.7,20),standard(0x353945));pot.position.set(x,.35,-5);root.add(pot);for(let i=0;i<9;i++){const leaf=new T.Mesh(new T.SphereGeometry(1,8,6),standard(pent?0x355b36:0x214f4d));leaf.scale.set(.14,.65,.08);leaf.rotation.z=(i-4)*.22;leaf.position.set(x+Math.sin(i)*.2,1+random()*.6,-5);root.add(leaf)}}
 function sign(text,x,y,z,color,width=3){const cn=document.createElement('canvas');cn.width=1024;cn.height=256;const ct=cn.getContext('2d');ct.fillStyle='#09101a';ct.fillRect(0,0,1024,256);ct.strokeStyle=color;ct.lineWidth=8;ct.strokeRect(12,12,1000,232);ct.fillStyle=color;ct.font='600 70px sans-serif';ct.textAlign='center';ct.fillText(text,512,150);const t=new T.CanvasTexture(cn);t.colorSpace=T.SRGBColorSpace;const m=new T.Mesh(new T.PlaneGeometry(width,width/4),new T.MeshBasicMaterial({map:t}));m.position.set(x,y,z);root.add(m)}
 if(cyber){sign('FREEDOM / 夜',-4.8,4,-7.65,'#ef5aa7',4);sign('AGENT DISTRICT',4.7,4.8,-7.65,'#61e3e8',4);for(const x of [-7.5,7.5])for(let z=-6;z<7;z+=3){box(x,2.8,z,.06,4.2,.06,trim);box(x*.98,4.8,z,.2,.03,2,trim)}
  const rain=new T.BufferGeometry(),positions=[];for(let i=0;i<450;i++){const x=(random()-.5)*28,y=random()*18,z=random()>.5?-9-random()*10:9+random()*10;positions.push(x,y,z,x-.02,y-.3,z)}rain.setAttribute('position',new T.Float32BufferAttribute(positions,3));const drops=new T.LineSegments(rain,new T.LineBasicMaterial({color:0x60909b,transparent:true,opacity:.35}));root.add(drops);animated.push(t=>drops.position.y=-(t*.002%4))}
 if(studio)sign('BUILD / THINK / CREATE',0,5,-7.65,'#a7c6db',5);
 if(pent)sign('F R E E D O M',0,5.2,-7.65,'#e1c6a5',5);
 if(matrix){city.visible=false;const cv=document.createElement('canvas');cv.width=1024;cv.height=2048;const ct=cv.getContext('2d');ct.fillStyle='#010705';ct.fillRect(0,0,1024,2048);ct.font='22px monospace';for(let x=0;x<1024;x+=25)for(let y=0;y<2048;y+=27){const f=random();ct.fillStyle=f>.98?'#c5ffde':f>.7?'#2cbf65':'#073a24';ct.fillText('01アイウエカキクサシスセソ'[Math.floor(random()*16)],x,y)}const tex=new T.CanvasTexture(cv);tex.colorSpace=T.SRGBColorSpace;tex.wrapS=tex.wrapT=T.RepeatWrapping;tex.repeat.set(5,1);const skin=new T.Mesh(new T.CylinderGeometry(7.6,7.6,9,96,1,true),new T.MeshBasicMaterial({map:tex,side:T.BackSide}));skin.position.y=4.5;root.add(skin);animated.push(t=>tex.offset.y=t*.000025);const grid=new T.GridHelper(16,64,0x55ce7c,0x113b25);grid.position.y=.005;root.add(grid)}
 return {root,background:matrix?0x010805:pent?0x75606d:cyber?0x100e24:0x142235,fog:pent?.009:.018,tick:t=>animated.forEach(f=>f(t))};
}

