import * as T from 'three';
import {portraitCells} from '../lidarPortraitGeometry.js';
import {cellVertex,cellFragment} from '../lidarPortraitShaders.js';
import {FaceMotion} from '../jarvisFaceMotion.js';
export function voiceHologram(){
 const data=portraitCells('low'),geometry=new T.BufferGeometry();for(const [name,key,size] of [['position','position',3],['aEdge','edge',1],['aTone','tone',1],['aSeed','seed',1],['aLayer','layer',1]])geometry.setAttribute(name,new T.BufferAttribute(data[key],size));
 const u={};for(const [k,v] of Object.entries({uTime:0,uJaw:0,uRound:0,uAwake:.3,uAssembly:1,uDisperse:0,uMic:0,uBlink:0,uThinking:0,uPixelRatio:1,uGlow:0,uSize:1.6}))u[k]={value:v};u.uGaze={value:new T.Vector2()};
 const mesh=new T.Points(geometry,new T.ShaderMaterial({uniforms:u,vertexShader:cellVertex,fragmentShader:cellFragment,transparent:true,depthWrite:false,blending:T.AdditiveBlending}));mesh.position.set(1.2,1.45,-1.9);mesh.scale.setScalar(.5);const motion=new FaceMotion();let last=0;
 return {mesh,update(t,voice,audio){const m=motion.step({enabled:!!voice?.enabled,phase:audio?.speaking?'speaking':voice?.phase||'standby',activation:voice?.enabled?1:0,mic:voice?.level||0,output:audio||{}},t,(t-last)||.016);last=t;for(const [k,v] of Object.entries({uTime:t,uJaw:m.jaw,uRound:m.round,uAwake:m.awake,uAssembly:m.assembly,uMic:m.mic,uBlink:m.blink,uThinking:m.thinking?1:0}))u[k].value=v;mesh.rotation.y=Math.sin(t*.2)*.08}};
}
