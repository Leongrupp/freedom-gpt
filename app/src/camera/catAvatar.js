import * as THREE from 'three';

// Original articulated character. Geometry and expression controls are real 3D;
// the generated concept image is a design reference, not a video billboard.
export function createCatAvatar(){
  const scene=new THREE.Group();scene.name='Freedom Street Cat';
  const bones=new Map(),weights={},smoothed={};let elapsed=0;
  const material=(name,color,roughness=.8)=>{const m=new THREE.MeshStandardMaterial({color,roughness});m.name=name;return m};
  const fur=material('Cat ginger fur','#b96524'),cream=material('Cat cream fur','#ddbb8d'),dark=material('Cat tabby markings','#60331b');
  const leather=material('Cat vest charcoal','#242525',.72),seam=material('Cat vest seams','#62503a'),pink=material('Cat nose and pads','#a85853');
  const white=material('Cat eyes ivory','#faf3d9',.24),green=material('Cat iris green','#5c9b2c',.3),black=material('Cat pupils and mouth','#101310',.5),shine=material('Cat eye highlight','#ffffff',.12);
  const scar=material('Cat healed scar','#d1a09b'),mouthPink=material('Cat tongue','#b85e65');
  for(const m of [fur,cream]){
    m.onBeforeCompile=shader=>{
      shader.vertexShader='varying vec3 vCatLocal;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvCatLocal=position;');
      shader.fragmentShader='varying vec3 vCatLocal;\n'+shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
        float grain=fract(sin(dot(vCatLocal,vec3(127.1,311.7,74.7)))*43758.5453);
        diffuseColor.rgb*=.94+.06*grain;
        ${m===fur?'float bands=sin(vCatLocal.y*10.+sin(vCatLocal.x*6.)*.7+vCatLocal.z*5.);diffuseColor.rgb*=mix(vec3(1.),vec3(.60,.48,.38),smoothstep(.73,.97,bands)*.48);':''}`);
    };
    m.customProgramCacheKey=()=>m===fur?'cat-striped-fur-v1':'cat-cream-fur-v1';
  }
  const sphere=(parent,mat,scale,position=[0,0,0],segments=28)=>{
    const mesh=new THREE.Mesh(new THREE.SphereGeometry(1,segments,20),mat);mesh.scale.set(...scale);mesh.position.set(...position);parent.add(mesh);return mesh;
  };
  const bone=(name,parent,position)=>{const node=new THREE.Object3D();node.name=name;node.position.set(...position);parent.add(node);bones.set(name,node);return node};
  const tube=(parent,points,radius,mat)=>{const path=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));const mesh=new THREE.Mesh(new THREE.TubeGeometry(path,24,radius,7,false),mat);parent.add(mesh);return mesh};
  const limb=(parent,end,radius,mat=fur)=>{
    const vector=new THREE.Vector3(...end),length=vector.length();const mesh=new THREE.Mesh(new THREE.CapsuleGeometry(radius,length,8,16),mat);
    mesh.position.copy(vector).multiplyScalar(.5);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),vector.normalize());parent.add(mesh);return mesh;
  };
  const hips=bone('hips',scene,[0,.66,0]),spine=bone('spine',hips,[0,.19,0]),chest=bone('chest',spine,[0,.22,0]),neck=bone('neck',chest,[0,.15,0]),head=bone('head',neck,[0,.09,0]);
  head.scale.setScalar(1.12);
  sphere(hips,fur,[.235,.225,.165],[0,.055,0]);sphere(spine,fur,[.225,.285,.17],[0,.055,0]);sphere(chest,fur,[.25,.17,.17],[0,0,0]);
  sphere(spine,cream,[.16,.27,.035],[0,.03,.153]);
  sphere(spine,leather,[.25,.28,.07],[0,.055,-.135]);
  for(const sign of [-1,1]){
    sphere(spine,leather,[.08,.25,.044],[sign*.19,.065,.13]);
    sphere(spine,leather,[.058,.047,.019],[sign*.192,.14,.17]);
    tube(spine,[[sign*.14,.17,.188],[sign*.192,.159,.193],[sign*.244,.17,.188]],.004,seam);
    tube(spine,[[sign*.12,.25,.15],[sign*.14,.13,.174],[sign*.13,-.17,.15]],.008,seam);
    tube(chest,[[sign*.11,.13,.16],[sign*.19,.10,.18],[sign*.14,.015,.18]],.023,leather);
    for(let n=0;n<3;n++)sphere(spine,seam,[.009,.009,.006],[sign*.14,.13-n*.11,.182],12);
  }
  sphere(neck,fur,[.13,.13,.12],[0,.02,0]);
  sphere(head,fur,[.285,.265,.245],[0,.115,.015]);
  sphere(head,cream,[.22,.14,.07],[0,-.025,.202]);
  for(const sign of [-1,1]){
    const earShape=new THREE.Shape();earShape.moveTo(-.095,0);earShape.lineTo(-.014,.232);earShape.quadraticCurveTo(0,.252,.014,.23);
    if(sign===1){earShape.lineTo(.044,.156);earShape.lineTo(.015,.142);earShape.lineTo(.058,.132)}
    earShape.lineTo(.104,0);earShape.quadraticCurveTo(0,-.035,-.095,0);
    const ear=new THREE.Mesh(new THREE.ExtrudeGeometry(earShape,{depth:.045,bevelEnabled:true,bevelThickness:.012,bevelSize:.012,bevelSegments:3,steps:1}),fur);
    ear.position.set(sign*.205,.29,-.005);ear.rotation.z=-sign*.17;head.add(ear);
    const inner=new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape([new THREE.Vector2(-.055,.025),new THREE.Vector2(0,.195),new THREE.Vector2(.065,.025)])),pink);inner.position.set(0,0,.059);ear.add(inner);
    for(let n=0;n<3;n++){
      const tuft=new THREE.Mesh(new THREE.ConeGeometry(.03,.09,5),fur);tuft.position.set(sign*(.247+n*.008),.08-n*.033,.06);tuft.rotation.z=-sign*(1.1+n*.12);head.add(tuft);
    }
    tube(head,[[sign*.03,.31,.219],[sign*.055,.265,.244],[sign*.065,.218,.253]],.013,dark);
    tube(head,[[sign*.19,.22,.18],[sign*.25,.19,.135],[sign*.266,.15,.10]],.011,dark);
  }
  // Each eye has its own lid scale and a movable iris/pupil group.
  const eyes={},brows={};
  for(const[side,sign]of [['left',1],['right',-1]]){
    const eye=new THREE.Group();eye.name='cat-eye-'+side;eye.position.set(sign*.12,.165,.232);head.add(eye);eyes[side]=eye;
    sphere(eye,black,[.092,.101,.037],[0,0,-.006]);sphere(eye,white,[.084,.092,.039]);
    const pupil=new THREE.Group();pupil.position.z=.035;eye.add(pupil);eye.userData.pupil=pupil;
    sphere(pupil,green,[.052,.065,.016]);sphere(pupil,black,[.023,.047,.009],[0,0,.014]);sphere(pupil,shine,[.012,.016,.005],[.017,.026,.024],16);
    const brow=new THREE.Group();brow.position.set(sign*.12,.255,.222);brow.rotation.z=sign*.16;head.add(brow);brows[side]=brow;
    tube(brow,[[-.075,-sign*.02,-.005],[0,0,.023],[.075,sign*.012,-.005]],.025,dark);
  }
  const muzzle=new THREE.Group();head.add(muzzle);
  sphere(muzzle,cream,[.09,.064,.069],[-.065,.004,.257]);sphere(muzzle,cream,[.09,.064,.069],[.065,.004,.257]);
  sphere(muzzle,pink,[.041,.027,.025],[0,.034,.318]);tube(muzzle,[[0,.015,.332],[0,-.025,.326]],.004,dark);
  const smile=tube(muzzle,[[-.087,-.025,.306],[-.047,-.046,.323],[0,-.025,.329],[.047,-.04,.323],[.089,-.013,.3]],.004,dark);
  const jaw=new THREE.Group();jaw.position.set(0,-.073,.225);head.add(jaw);sphere(jaw,cream,[.12,.063,.085]);
  const mouth=sphere(head,black,[.065,.012,.032],[0,-.047,.293]);mouth.name='cat-mouth';jaw.name='cat-jaw';
  const tongue=sphere(head,mouthPink,[.04,.012,.011],[0,-.078,.322]);tongue.visible=false;
  const teeth=[];
  for(const sign of [-1,1]){const tooth=new THREE.Mesh(new THREE.ConeGeometry(.008,.026,10),white);tooth.rotation.z=Math.PI;tooth.position.set(sign*.04,-.034,.324);head.add(tooth);teeth.push(tooth)}
  // Healed scar passes above and below the right eye; the eye stays intact.
  tube(head,[[-.235,.36,.122],[-.19,.31,.203],[-.156,.277,.247]],.008,scar);
  tube(head,[[-.214,.112,.213],[-.244,.069,.184]],.008,scar);
  for(const sign of [-1,1])for(let n=0;n<3;n++){
    tube(head,[[sign*.09,-.003-n*.014,.319],[sign*.24,.014-n*.033,.306],[sign*.39,.025-n*.047,.258]],.0017,cream);
    sphere(head,dark,[.0035,.0035,.003],[sign*(.065+n*.018),.006-n*.006,.325],10);
  }
  // Finger joints use standard VRM names, so the existing hand tracker drives
  // the actual geometry of each phalanx instead of deforming a photograph.
  for(const[side,sign]of [['left',1],['right',-1]]){
    const shoulder=bone(side+'Shoulder',chest,[sign*.21,.055,0]);
    const upper=bone(side+'UpperArm',shoulder,[sign*.055,0,0]),lower=bone(side+'LowerArm',upper,[sign*.22,0,0]),hand=bone(side+'Hand',lower,[sign*.2,0,0]);
    limb(upper,[sign*.22,0,0],.068);limb(lower,[sign*.2,0,0],.055);sphere(upper,fur,[.085,.083,.083]);sphere(lower,fur,[.06,.06,.06]);sphere(hand,cream,[.078,.057,.07],[sign*.035,0,0]);
    sphere(hand,pink,[.045,.037,.012],[sign*.035,0,.061]);
    for(const[finger,index]of [['Index',0],['Middle',1],['Ring',2],['Little',3]]){
      const z=(1.5-index)*.034,start=bone(side+finger+'Proximal',hand,[sign*.073,0,z]);
      const mid=bone(side+finger+'Intermediate',start,[sign*.032,0,0]),tip=bone(side+finger+'Distal',mid,[sign*.026,0,0]);
      limb(start,[sign*.032,0,0],.018,cream);limb(mid,[sign*.026,0,0],.016,cream);limb(tip,[sign*.024,0,0],.015,cream);
    }
    const thumb=bone(side+'ThumbMetacarpal',hand,[sign*.006,0,.068]),thumbP=bone(side+'ThumbProximal',thumb,[sign*.02,0,.027]),thumbD=bone(side+'ThumbDistal',thumbP,[sign*.022,0,.012]);
    limb(thumb,[sign*.02,0,.027],.021,cream);limb(thumbP,[sign*.022,0,.012],.019,cream);limb(thumbD,[sign*.024,0,0],.018,cream);
    const thigh=bone(side+'UpperLeg',hips,[sign*.13,-.02,0]),shin=bone(side+'LowerLeg',thigh,[0,-.25,0]),foot=bone(side+'Foot',shin,[0,-.26,0]),toes=bone(side+'Toes',foot,[0,-.035,.13]);
    limb(thigh,[0,-.25,0],.105);limb(shin,[0,-.26,0],.07);sphere(foot,cream,[.098,.067,.145],[0,-.035,.075]);
    for(let n=0;n<3;n++)sphere(toes,cream,[.034,.044,.053],[(n-1)*.057,-.003,.044],18);
  }
  const tail=bone('tail',hips,[0,.055,-.145]);
  tube(tail,[[0,0,0],[-.22,-.035,-.06],[-.46,.01,-.04],[-.55,.14,-.015],[-.48,.26,.005]],.064,fur);
  sphere(tail,cream,[.063,.08,.063],[-.48,.26,.005]);
  const humanoid={getNormalizedBoneNode:name=>bones.get(name)||null,getRawBoneNode:name=>bones.get(name)||null};
  const expressionManager={setValue:(name,value)=>{weights[name]=Number.isFinite(value)?value:0}};
  const faceWeights={};
  const setFaceWeights=value=>{for(const[key,score]of Object.entries(value))faceWeights[key]=score};
  const faceValue=key=>Math.max(0,Math.min(1,faceWeights[key]||0));
  function update(delta){
    elapsed+=delta;const alpha=delta>0?1-Math.exp(-delta*20):1;
    for(const name of ['blinkLeft','blinkRight','aa','ou','happy','angry'])smoothed[name]=(smoothed[name]||0)+((weights[name]||0)-(smoothed[name]||0))*alpha;
    const open=Math.min(1,(smoothed.aa||0)*1.25),pucker=Math.max(faceValue('mouthPucker'),(smoothed.ou||0)*1.5);
    for(const[side,eye]of Object.entries(eyes)){
      const cap=side==='left'?'Left':'Right';eye.scale.y=Math.max(.035,.84*(1-(smoothed['blink'+cap]||0))*(1-faceValue('eyeSquint'+cap)*.35));
      const gazeX=(faceValue('eyeLookOut'+cap)-faceValue('eyeLookIn'+cap))*(side==='left'?1:-1),gazeY=faceValue('eyeLookUp'+cap)-faceValue('eyeLookDown'+cap);
      eye.userData.pupil.position.x=THREE.MathUtils.lerp(eye.userData.pupil.position.x,gazeX*.025,alpha);eye.userData.pupil.position.y=THREE.MathUtils.lerp(eye.userData.pupil.position.y,gazeY*.024,alpha);
      brows[side].position.y=.255+faceValue('browInnerUp')*.025-faceValue('browDown'+cap)*.012;
      brows[side].rotation.z=(side==='left'?1:-1)*(.16+(smoothed.angry||0)*.3-(smoothed.happy||0)*.1);
    }
    mouth.scale.x=.065*(1-pucker*.45);mouth.scale.y=.012+open*.082;mouth.position.y=-.047-open*.024;mouth.visible=open>.07;
    jaw.position.y=-.073-open*.07;smile.visible=open<.22;smile.scale.x=1+(smoothed.happy||0)*.22;
    tongue.visible=open>.25;tongue.position.y=-.07-open*.05;for(const tooth of teeth)tooth.visible=open>.38;
    tail.rotation.z=Math.sin(elapsed*1.4)*.045;tail.rotation.y=Math.sin(elapsed*.9)*.10;
    scene.updateMatrixWorld(true);
  }
  update(0);
  return {scene,humanoid,expressionManager,setFaceWeights,update,isFreedomCat:true};
}
