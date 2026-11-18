import {JarvisFaceScene} from '../JarvisFaceScene.js';
import * as THREE from 'three';
export class AvatarRenderer{
 constructor(canvas){this.canvas=canvas;this.audio=()=>({});this.face=new JarvisFaceScene(canvas.parentElement,{canvas,quality:'auto',signal:()=>{const a=this.audio();return {enabled:true,phase:a.speaking?'speaking':'listening',activation:1,output:()=>a}}});this.vrm=true}
 async load(){}
 setFrame(frame){this.face.camera.position.z=frame==='head'?5.8:8;this.draw()}
 setTint(){}
 calibrate(){this.neutral=null}
 update(result){const m=result.facialTransformationMatrixes?.[0]?.data;if(m?.length===16){const q=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().fromArray(m));if(!this.neutral)this.neutral=q.clone().invert();q.premultiply(this.neutral);const e=new THREE.Euler().setFromQuaternion(q,'YXZ');this.face.target={x:THREE.MathUtils.clamp(e.y*3,-1,1),y:THREE.MathUtils.clamp(e.x*3,-1,1)}}this.draw();return {}}
 draw(){this.face.changed=true;this.face.renderFrame(performance.now())}
 dispose(){this.face.close()}
}
