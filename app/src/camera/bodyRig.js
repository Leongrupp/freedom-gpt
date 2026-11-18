import * as THREE from 'three';

const point=p=>new THREE.Vector3(p.x,-p.y,-p.z);
const valid=p=>p&&[p.x,p.y,p.z].every(Number.isFinite);
const confidence=p=>valid(p)&&(p.visibility??1)>.5&&(p.presence??1)>.5;
const inFrame=p=>confidence(p)&&p.x>.005&&p.x<.995&&p.y>.005&&p.y<.995;
const sides=[['left',11,13,15,23,25,27,31],['right',12,14,16,24,26,28,32]];
const fingers=[['Thumb',[1,2,3,4],['Metacarpal','Proximal','Distal']],['Index',[5,6,7,8]],['Middle',[9,10,11,12]],['Ring',[13,14,15,16]],['Little',[17,18,19,20]]];

function basis(across,up){
  const x=across.clone().normalize(),y=up.clone().addScaledVector(x,-up.dot(x)).normalize();
  const z=new THREE.Vector3().crossVectors(x,y).normalize();
  if(x.lengthSq()<.5||y.lengthSq()<.5||z.lengthSq()<.5)return null;
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,z));
}

export class BodyRig{
  constructor(vrm){
    this.vrm=vrm;this.bones=new Map();this.rest=new Map();this.aims=new Map();this.lastSeen=new Map();this.palms=new Map();
    const names=['hips','spine','chest','upperChest','neck','head'];
    for(const[side]of sides){
      for(const part of ['Shoulder','UpperArm','LowerArm','Hand','UpperLeg','LowerLeg','Foot','Toes'])names.push(side+part);
      for(const[finger,,segments=['Proximal','Intermediate','Distal']]of fingers)for(const segment of segments)names.push(side+finger+segment);
    }
    vrm.scene.updateMatrixWorld(true);
    for(const name of names){const node=vrm.humanoid.getNormalizedBoneNode(name);if(node){this.bones.set(name,node);this.rest.set(name,node.quaternion.clone())}}
    const position=name=>this.bones.get(name)?.getWorldPosition(new THREE.Vector3());
    for(const[name,node]of this.bones){
      const child=node.children.find(child=>child.position.lengthSq()>1e-8);
      let direction=child?.position.clone();
      // VRM has no fingertip bone. Continue the rest direction of its parent.
      if(!direction&&/Distal|Toes/.test(name)){
        const world=node.getWorldPosition(new THREE.Vector3()).sub(node.parent.getWorldPosition(new THREE.Vector3()));
        direction=world.applyQuaternion(node.getWorldQuaternion(new THREE.Quaternion()).invert());
      }
      if(direction?.lengthSq()>1e-8)this.aims.set(name,direction.normalize().applyQuaternion(node.quaternion));
    }
    for(const[side]of sides){
      const wrist=position(side+'Hand'),index=position(side+'IndexProximal'),little=position(side+'LittleProximal'),middle=position(side+'MiddleProximal');
      if(wrist&&index&&little&&middle){const restBasis=basis(index.sub(little),middle.sub(wrist));if(restBasis)this.palms.set(side,{basis:restBasis,bone:this.bones.get(side+'Hand').getWorldQuaternion(new THREE.Quaternion())})}
    }
  }
  touch(name,now){this.lastSeen.set(name,now)}
  orient(name,world,now,weight=.4){
    const node=this.bones.get(name);if(!node||!world)return;
    const local=node.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(world);
    node.quaternion.slerp(local,weight);node.updateWorldMatrix(false,true);this.touch(name,now);
  }
  aim(name,from,to,now){
    const node=this.bones.get(name),restDirection=this.aims.get(name);if(!node||!restDirection||!valid(from)||!valid(to))return;
    const target=point(to).sub(point(from));if(target.lengthSq()<1e-7)return;
    target.normalize().applyQuaternion(node.parent.getWorldQuaternion(new THREE.Quaternion()).invert());
    const q=new THREE.Quaternion().setFromUnitVectors(restDirection,target).multiply(this.rest.get(name));
    node.quaternion.slerp(q,.48);node.updateWorldMatrix(false,true);this.touch(name,now);
  }
  torso(points,landmarks,now){
    if(![11,12].every(i=>inFrame(landmarks[i])&&valid(points[i])))return false;
    const left=point(points[11]),right=point(points[12]),hipsVisible=[23,24].every(i=>inFrame(landmarks[i])&&valid(points[i]));
    const hipL=valid(points[23])?point(points[23]):new THREE.Vector3(),hipR=valid(points[24])?point(points[24]):new THREE.Vector3();
    const up=hipsVisible?left.clone().add(right).sub(hipL).sub(hipR).multiplyScalar(.5):new THREE.Vector3(0,1,0);
    const shoulder=basis(left.clone().sub(right),up),hips=hipsVisible?basis(hipL.clone().sub(hipR),up):null;
    if(!shoulder)return false;
    // Guard against a one-frame depth flip from the monocular estimator.
    const chest=this.bones.has('chest')?'chest':this.bones.has('upperChest')?'upperChest':'spine';
    for(const[name,q]of [['hips',hips],[chest,shoulder]]){
      if(!q)continue;
      const e=new THREE.Euler().setFromQuaternion(q,'YXZ');e.x=THREE.MathUtils.clamp(e.x,-.75,.75);e.y=THREE.MathUtils.clamp(e.y,-1.3,1.3);e.z=THREE.MathUtils.clamp(e.z,-.7,.7);
      this.orient(name,new THREE.Quaternion().setFromEuler(e),now,.3);
    }
    return true;
  }
  update(result,now=performance.now()){
    const landmarks=result.pose?.landmarks?.[0],world=result.pose?.worldLandmarks?.[0];
    const tracked={body:false,leftHand:false,rightHand:false,legs:false};
    if(landmarks?.length===33&&world?.length===33){
      tracked.body=this.torso(world,landmarks,now);
      for(const[side,shoulder,elbow,wrist,hip,knee,ankle,toe]of sides){
        // A hidden elbow or leg is not evidence for a movement.
        if([shoulder,elbow].every(i=>inFrame(landmarks[i])))this.aim(side+'UpperArm',world[shoulder],world[elbow],now);
        if([elbow,wrist].every(i=>inFrame(landmarks[i])))this.aim(side+'LowerArm',world[elbow],world[wrist],now);
        if([hip,knee].every(i=>inFrame(landmarks[i]))){this.aim(side+'UpperLeg',world[hip],world[knee],now);tracked.legs=true}
        if([knee,ankle].every(i=>inFrame(landmarks[i])))this.aim(side+'LowerLeg',world[knee],world[ankle],now);
        if([ankle,toe].every(i=>inFrame(landmarks[i])))this.aim(side+'Foot',world[ankle],world[toe],now);
      }
    }
    const hands=result.hands;
    for(let i=0;i<(hands?.landmarks?.length||0);i++){
      const hand=hands.landmarks[i],points=hands.worldLandmarks?.[i];if(points?.length!==21||hand.length!==21||!points.every(valid))continue;
      const side=this.handSide(hand,hands.handedness?.[i]?.[0],landmarks);if(!side)continue;
      const bind=this.palms.get(side);
      if(bind){const palm=basis(point(points[5]).sub(point(points[17])),point(points[9]).sub(point(points[0])));if(palm)this.orient(side+'Hand',palm.multiply(bind.basis.clone().invert()).multiply(bind.bone),now,.45)}
      for(const[finger,indices,segments=['Proximal','Intermediate','Distal']]of fingers){
        for(let joint=0;joint<3;joint++)this.aim(side+finger+segments[joint],points[indices[joint]],points[indices[joint+1]],now);
      }
      tracked[side+'Hand']=true;
    }
    // If tracking is lost, relax joints instead of freezing the last gesture.
    for(const[name,node]of this.bones){
      if(/head|neck/i.test(name))continue;
      if(now-(this.lastSeen.get(name)??-Infinity)<450)continue;
      const target=this.rest.get(name).clone();
      if(name==='leftUpperArm')target.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),-1.12));
      if(name==='rightUpperArm')target.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),1.12));
      node.quaternion.slerp(target,.15);
    }
    return tracked;
  }
  handSide(hand,classification,pose){
    // HandLandmarker does not define visibility/presence scores. Its generated
    // protobuf landmarks may contain zero for these unused fields.
    if(!hand.every(valid)||hand[0].x<=.005||hand[0].x>=.995||hand[0].y<=.005||hand[0].y>=.995)return null;
    if(pose){
      // Associate with this person's wrists. This also resolves selfie labeling
      // differences between camera drivers without swapping left/right hands.
      const distances=sides.map(([side,,,wrist])=>[side,inFrame(pose[wrist])?Math.hypot(hand[0].x-pose[wrist].x,hand[0].y-pose[wrist].y):Infinity]).sort((a,b)=>a[1]-b[1]);
      if(distances[0][1]<.18)return distances[0][0];
      return null;
    }
    if((classification?.score||0)<.7)return null;
    return classification.categoryName==='Left'?'left':classification.categoryName==='Right'?'right':null;
  }
}
