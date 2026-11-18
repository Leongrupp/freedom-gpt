import {FilesetResolver,FaceLandmarker} from '@mediapipe/tasks-vision';

export async function createTracker(runningMode='VIDEO'){
  const files=await FilesetResolver.forVisionTasks('/api/camera/assets');
  return FaceLandmarker.createFromOptions(files,{
    baseOptions:{modelAssetPath:'/api/camera/assets/face_landmarker.task',delegate:'CPU'},
    runningMode,numFaces:2,minFaceDetectionConfidence:.65,minFacePresenceConfidence:.65,
    minTrackingConfidence:.65,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true
  });
}

export function faceCrop(result,width,height,minArea=.006){
  if(result.faceLandmarks?.length!==1)return null;
  const points=result.faceLandmarks[0],xs=points.map(p=>p.x),ys=points.map(p=>p.y);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  if(minX<.005||minY<.005||maxX>.995||maxY>.995||(maxX-minX)*(maxY-minY)<minArea)return null;
  const left=points[33],right=points[263];
  const angle=Math.atan2((right.y-left.y)*height,(right.x-left.x)*width);
  if(Math.abs(angle)>Math.PI/2)return null;
  return {cx:(minX+maxX)/2,cy:(minY+maxY)/2-.025,size:Math.max((maxX-minX)*width,(maxY-minY)*height)*2.05/Math.max(width,height),angle};
}

export function cropPortrait(image,crop){
  const width=image.naturalWidth||image.width,height=image.naturalHeight||image.height;
  const size=crop.size*Math.max(width,height),cx=crop.cx*width,cy=crop.cy*height;
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=512;
  const ctx=canvas.getContext('2d');ctx.fillStyle='#26262c';ctx.fillRect(0,0,512,512);
  ctx.translate(256,256);ctx.rotate(-crop.angle);ctx.scale(512/size,512/size);ctx.drawImage(image,-cx,-cy);
  return canvas.toDataURL('image/jpeg',.95);
}

export async function gatherIce(peer,timeout=6000){
  if(peer.iceGatheringState==='complete')return;
  await new Promise(resolve=>{
    const done=()=>{clearTimeout(timer);peer.removeEventListener('icegatheringstatechange',changed);resolve()};
    const changed=()=>{if(peer.iceGatheringState==='complete')done()};
    const timer=setTimeout(done,timeout);peer.addEventListener('icegatheringstatechange',changed);
  });
}
export const rtcOptions={iceServers:[{urls:'stun:stun.l.google.com:19302'}],iceCandidatePoolSize:0};
