import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {VRMLoaderPlugin,VRMUtils} from '@pixiv/three-vrm';
import {BodyRig} from './bodyRig.js';
import {loadUserCatAvatar} from './userCatAvatar.js';

export class AvatarRenderer{
  constructor(canvas){
    this.canvas=canvas;this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
    this.renderer.setPixelRatio(1);this.renderer.setSize(1280,720,false);this.renderer.setClearColor('#111318');
    this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(32,1280/720,.01,100);
    const sun=new THREE.DirectionalLight(0xffffff,2.4);sun.position.set(1,2,3);this.scene.add(sun);
    const rim=new THREE.DirectionalLight(0xaaa0ff,1.2);rim.position.set(-2,1,-1);this.scene.add(rim);
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x444455,2));
    this.clock=new THREE.Clock();this.frame='waist';this.headQuaternion=new THREE.Quaternion();this.neutral=null;this.disposed=false;
  }
  async load(url,character='vrm'){
    if(character==='cat')this.vrm=await loadUserCatAvatar();
    else{
      const loader=new GLTFLoader();loader.register(parser=>new VRMLoaderPlugin(parser));
      const gltf=await loader.loadAsync(url);
      if(this.disposed){VRMUtils.deepDispose(gltf.scene);return}
      if(!gltf.userData.vrm)throw Error('VRM model unavailable');
      this.vrm=gltf.userData.vrm;VRMUtils.rotateVRM0(this.vrm);
    }
    if(this.disposed){VRMUtils.deepDispose(this.vrm.scene);return}this.scene.add(this.vrm.scene);
    this.vrm.scene.traverse(object=>{object.frustumCulled=false});
    this.bodyRig=new BodyRig(this.vrm);
    const bones=this.vrm.humanoid;
    const left=bones.getNormalizedBoneNode('leftUpperArm'),right=bones.getNormalizedBoneNode('rightUpperArm');
    if(left)left.rotation.z=-1.12;if(right)right.rotation.z=1.12;
    this.vrm.update(0);this.vrm.scene.updateMatrixWorld(true);
    const bounds=new THREE.Box3().setFromObject(this.vrm.scene);this.topY=bounds.max.y;this.bottomY=bounds.min.y;
    this.originalMaterials=new Map();
    this.vrm.scene.traverse(object=>{
      for(const material of (Array.isArray(object.material)?object.material:[object.material]).filter(Boolean)){
        if(material.color)this.originalMaterials.set(material,{color:material.color.clone(),shade:material.shadeColorFactor?.clone()});
      }
    });
    this.setFrame(this.frame);this.draw();let lastDraw=0;this.renderer.setAnimationLoop(now=>{if(now-lastDraw>=1000/30){lastDraw=now;this.draw()}});
  }
  setFrame(frame){
    this.frame=frame;
    this.vrm?.update(0);this.vrm?.scene.updateMatrixWorld(true);
    const head=this.vrm?.humanoid.getRawBoneNode('head');
    const headY=head?head.getWorldPosition(new THREE.Vector3()).y:1.45;
    const top=this.topY||headY+.23,bottom=this.bottomY||0,height=Math.max(1,top-bottom);
    const span=frame==='head'?Math.max(.6,(top-headY)*2.5):frame==='full'?height*1.4:height*.67;
    const center=frame==='full'?(top+bottom)/2:top-span*.4;
    this.camera.position.set(0,center,span/(2*Math.tan(THREE.MathUtils.degToRad(this.camera.fov/2))));this.camera.lookAt(0,center,0);
  }
  setTint(value){
    for(const [material,original]of this.originalMaterials||[]){
      material.color.copy(original.color);if(original.shade)material.shadeColorFactor.copy(original.shade);
      if(value==='blue'){
        const color=original.color;
        if(/skin|body|face/i.test(material.name)||(color.r>color.b*1.1&&color.r>color.g*.9)){material.color.setRGB(.18,.58,.82);if(material.shadeColorFactor)material.shadeColorFactor.setRGB(.09,.26,.42)}
      }
    }
  }
  calibrate(){this.neutral=null}
  update(result){
    if(!this.vrm)return;
    const categories=result.faceBlendshapes?.[0]?.categories||[];
    const weights=Object.fromEntries(categories.map(x=>[x.categoryName,x.score]));const value=name=>Math.max(0,Math.min(1,weights[name]||0));
    this.vrm.setFaceWeights?.(weights);
    const expression=this.vrm.expressionManager;
    const blink=name=>this.vrm.isFreedomCat?THREE.MathUtils.clamp((value(name)-.06)/.66,0,1):value(name);
    expression?.setValue('blinkLeft',blink('eyeBlinkLeft'));expression?.setValue('blinkRight',blink('eyeBlinkRight'));
    expression?.setValue('aa',value('jawOpen')*.9);expression?.setValue('ou',value('mouthFunnel')*.5);
    expression?.setValue('happy',(value('mouthSmileLeft')+value('mouthSmileRight'))*.35);
    expression?.setValue('angry',(value('browDownLeft')+value('browDownRight'))*.2);
    const tracked=this.bodyRig?.update(result)||{};
    const matrix=result.facialTransformationMatrixes?.[0]?.data;
    if(matrix?.length===16){
      const q=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().fromArray(matrix));
      if(!this.neutral)this.neutral=q.clone().invert();
      q.premultiply(this.neutral);const euler=new THREE.Euler().setFromQuaternion(q,'YXZ');
      const target=new THREE.Quaternion().setFromEuler(new THREE.Euler(euler.x*.85,euler.y*.85,-euler.z*.85,'YXZ'));
      this.headQuaternion.slerp(target,.4);
      const head=this.vrm.humanoid.getNormalizedBoneNode('head');if(head)head.quaternion.copy(this.headQuaternion);
      const chest=this.vrm.humanoid.getNormalizedBoneNode('chest');if(chest&&!tracked.body)chest.rotation.set(euler.x*.08,euler.y*.12,-euler.z*.1);
    }
    this.draw();return tracked;
  }
  draw(){if(this.disposed)return;this.vrm?.update(Math.min(.05,this.clock.getDelta()));this.renderer.render(this.scene,this.camera)}
  dispose(){this.disposed=true;this.renderer.setAnimationLoop(null);if(this.vrm)VRMUtils.deepDispose(this.vrm.scene);this.renderer.dispose()}
}
