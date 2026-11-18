import {FilesetResolver,FaceLandmarker,PoseLandmarker,HandLandmarker} from '@mediapipe/tasks-vision';

let face,headFace,pose,hands,stableHead,lastPose,lastHands,lastPoseStamp=-Infinity,lastHandsStamp=-Infinity;
const headCanvas=new OffscreenCanvas(256,256),headContext=headCanvas.getContext('2d');

function headRegion(landmarks,width,height){
  const visible=landmarks.slice(0,11).filter(p=>(p.visibility??1)>.5);
  if(visible.length<5)return null;
  const xs=visible.map(p=>p.x*width),ys=visible.map(p=>p.y*height);
  const size=Math.max((Math.max(...xs)-Math.min(...xs))*2.4,(Math.max(...ys)-Math.min(...ys))*3,width*.08);
  const x=(Math.max(...xs)+Math.min(...xs))/2-size/2,y=(Math.max(...ys)+Math.min(...ys))/2-size*.42;
  if(x<0||y<0||x+size>width||y+size>height)return null;
  return {x,y,size};
}
self.onmessage=async({data})=>{
  if(data.type==='init'){
    try{
      const files=await FilesetResolver.forVisionTasks(data.origin+'/api/camera/assets');
      const options=path=>({baseOptions:{modelAssetPath:data.origin+path,delegate:'CPU'},canvas:new OffscreenCanvas(1,1),runningMode:'VIDEO'});
      const create=async(Task,settings)=>{
        if(data.gpu){try{return await Task.createFromOptions(files,{...settings,baseOptions:{...settings.baseOptions,delegate:'GPU'}})}catch{}}
        return Task.createFromOptions(files,{...settings,canvas:new OffscreenCanvas(1,1)});
      };
      face=await create(FaceLandmarker,{...options('/api/camera/assets/face_landmarker.task'),numFaces:2,minFaceDetectionConfidence:.55,minFacePresenceConfidence:.55,minTrackingConfidence:.55,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true});
      headFace=await create(FaceLandmarker,{...options('/api/camera/assets/face_landmarker.task'),runningMode:'IMAGE',numFaces:2,minFaceDetectionConfidence:.55,minFacePresenceConfidence:.55,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true});
      const warnings=[];
      // The lightweight body detector also locates a small face in photo mode.
      // CPU pose recovery is more reliable for the owner's seated PS4-camera
      // view. Keep GPU acceleration for the high-frequency face and hand tasks.
      try{pose=await PoseLandmarker.createFromOptions(files,{...options('/assets/camera-motion/pose_landmarker_lite.task'),numPoses:2,minPoseDetectionConfidence:.5,minPosePresenceConfidence:.5,minTrackingConfidence:.5,outputSegmentationMasks:false})}catch{if(data.motion)warnings.push('pose')}
      if(data.motion){
        try{hands=await create(HandLandmarker,{...options('/assets/camera-motion/hand_landmarker.task'),numHands:2,minHandDetectionConfidence:.5,minHandPresenceConfidence:.5,minTrackingConfidence:.5})}catch{warnings.push('hands')}
      }
      self.postMessage({type:'ready',warnings});
    }catch(error){self.postMessage({type:'error',error:error.message})}
    return;
  }
  if(data.type==='frame'){
    const start=performance.now();
    try{
      let result=face.detectForVideo(data.image,data.stamp);
      const wideFaces=result.faceLandmarks.length;let headFaces=null;
      if(pose&&data.stamp-lastPoseStamp>140){lastPose=pose.detectForVideo(data.image,data.stamp);lastPoseStamp=data.stamp}
      const body=lastPose;
      const multiple=result.faceLandmarks.length>1||body?.landmarks?.length>1;
      if(multiple)result.faceLandmarks=[];
      if(!multiple){
        let roi=body?.landmarks?.length===1?headRegion(body.landmarks[0],data.image.width,data.image.height):null;
        if(!roi&&result.faceLandmarks.length===1){
          const points=result.faceLandmarks[0],xs=points.map(p=>p.x*data.image.width),ys=points.map(p=>p.y*data.image.height);
          const size=Math.min(data.image.width,data.image.height,Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))*1.65);
          roi={x:Math.max(0,Math.min(data.image.width-size,(Math.max(...xs)+Math.min(...xs)-size)/2)),y:Math.max(0,Math.min(data.image.height-size,(Math.max(...ys)+Math.min(...ys)-size)/2)),size};
        }
        if(roi){
          if(stableHead&&Math.hypot(roi.x-stableHead.x,roi.y-stableHead.y)<roi.size*.7){for(const key of ['x','y','size'])roi[key]=stableHead[key]*.55+roi[key]*.45}
          stableHead={...roi};
          headContext.drawImage(data.image,roi.x,roi.y,roi.size,roi.size,0,0,256,256);
          // A separate IMAGE-mode detector keeps crop coordinates out of the
          // wide detector's VIDEO history. Mixing them caused facial jumps.
          const close=headFace.detect(headCanvas);
          headFaces=close.faceLandmarks.length;
          if(close.faceLandmarks.length===1){
            close.faceLandmarks=close.faceLandmarks.map(points=>points.map(p=>({...p,x:(roi.x+p.x*roi.size)/data.image.width,y:(roi.y+p.y*roi.size)/data.image.height,z:p.z*roi.size/data.image.width})));
            result=close;
          }else result.faceLandmarks=[];
        }else stableHead=null;
      }
      // Multiple people must never drive different parts of one avatar.
      if(data.motion&&result.faceLandmarks.length===1){
        if(body)result.pose=body;
        if(hands){if(data.stamp-lastHandsStamp>125){lastHands=hands.detectForVideo(data.image,data.stamp);lastHandsStamp=data.stamp}result.hands=lastHands}
      }else lastHands=null;
      result.trackingInfo={wideFaces,headFaces,poses:body?.landmarks?.length||0};
      self.postMessage({type:'result',id:data.id,result,milliseconds:performance.now()-start});
    }catch(error){self.postMessage({type:'error',error:error.message})}
    finally{data.image.close()}
  }
};
