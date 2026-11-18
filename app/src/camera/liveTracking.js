import {createTracker} from './tracking.js';

// One frame in flight. Inference is isolated from React and controls so that
// a slow CPU never creates an unbounded queue of camera frames.
export async function createLiveTracker(motion=true,{gpu=/Windows/i.test(globalThis.navigator?.userAgent||'')}={}){
  let worker;
  try{
    worker=new Worker(new URL('./trackingWorker.js',import.meta.url));
    const tracker=new WorkerTracker(worker);
    const ready=tracker.request({type:'init',origin:location.origin,motion,gpu},[],60000);
    const info=await ready;tracker.warnings=info.warnings;return tracker;
  }catch(error){
    worker?.terminate();
    const face=await createTracker('VIDEO');
    return {warnings:motion?['pose','hands']:[],detect:async(source,stamp)=>face.detectForVideo(source,stamp),close:()=>face.close()};
  }
}

class WorkerTracker{
  constructor(worker){
    this.worker=worker;this.pending=null;this.sequence=0;this.closed=false;
    worker.onmessage=({data})=>{const pending=this.pending;if(!pending)return;this.pending=null;clearTimeout(pending.timer);data.type==='error'?pending.reject(Error(data.error)):pending.resolve(data.type==='result'?data.result:data)};
    worker.onerror=event=>{this.fail(Error(event.message||'Camera tracking worker stopped'))};
  }
  fail(error){if(this.pending){clearTimeout(this.pending.timer);this.pending.reject(error);this.pending=null}}
  request(data,transfer=[],timeout=15000){
    if(this.closed)return Promise.reject(Error('Camera tracking stopped'));
    if(this.pending)return Promise.reject(Error('Camera frame already in flight'));
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>this.fail(Error('Camera tracking timed out')),timeout);this.pending={resolve,reject,timer};
      try{this.worker.postMessage(data,transfer)}catch(error){this.fail(error)}
    });
  }
  async detect(source,stamp){
    const image=await createImageBitmap(source);
    if(this.closed){image.close();throw Error('Camera tracking stopped')}
    try{return await this.request({type:'frame',id:++this.sequence,image,stamp,motion:true},[image])}catch(error){image.close();throw error}
  }
  close(){this.closed=true;this.fail(Error('Camera tracking stopped'));this.worker.terminate()}
}
