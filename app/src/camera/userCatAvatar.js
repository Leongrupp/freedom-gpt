import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

// The supplied Blender model has no skeleton or facial shape keys. Keep it as
// a static preview, without pretending that tracking drives an absent rig.
export async function loadUserCatAvatar(){
  const gltf=await new GLTFLoader().loadAsync('/assets/camera/orange-cat-20261023.glb');
  const scene=new THREE.Group();
  const bounds=new THREE.Box3().setFromObject(gltf.scene);
  const center=bounds.getCenter(new THREE.Vector3());
  gltf.scene.position.sub(new THREE.Vector3(center.x,bounds.min.y,center.z));
  scene.add(gltf.scene);scene.scale.setScalar(1.9/Math.max(.01,bounds.max.y-bounds.min.y));
  return {
    scene,isFreedomCat:true,staticModel:true,
    humanoid:{getNormalizedBoneNode:()=>null,getRawBoneNode:()=>null},
    expressionManager:{setValue(){}},
    update(){}
  };
}
