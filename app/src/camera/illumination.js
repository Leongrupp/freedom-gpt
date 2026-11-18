// Brighten the actual inference input, not just the visible preview. All pixels
// remain in this browser; the source camera/OBS settings are left intact.
export class CameraIllumination{
  constructor(){
    this.canvas=document.createElement('canvas');this.ctx=this.canvas.getContext('2d',{willReadFrequently:true,alpha:false});
    this.sample=document.createElement('canvas');this.sample.width=64;this.sample.height=40;
    this.sampleCtx=this.sample.getContext('2d',{willReadFrequently:true,alpha:false});
    this.gamma=1;this.lastSample=-Infinity;this.lut=new Uint8ClampedArray(256);this.lastGamma=null;this.mode='auto';
  }
  focusFace(result){
    const points=result.faceLandmarks?.length===1?result.faceLandmarks[0]:null;
    if(!points){this.focus=null;return}
    const xs=points.map(p=>p.x),ys=points.map(p=>p.y),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys);
    const width=right-left,height=bottom-top;
    this.focus={x:Math.max(0,left-width*.15),y:Math.max(0,top-height*.1),right:Math.min(1,right+width*.15),bottom:Math.min(1,bottom+height*.1)};
  }
  process(source,mode='auto',now=performance.now()){
    const width=source.videoWidth||source.width,height=source.videoHeight||source.height;
    const scale=Math.min(1,768/width,576/height),w=Math.max(1,Math.round(width*scale)),h=Math.max(1,Math.round(height*scale));
    if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h}
    this.ctx.drawImage(source,0,0,w,h);
    if(mode==='off')return this.canvas;
    if(now-this.lastSample>500||mode!==this.mode){
      const focus=this.focus;
      if(focus&&focus.right>focus.x&&focus.bottom>focus.y)this.sampleCtx.drawImage(this.canvas,focus.x*w,focus.y*h,(focus.right-focus.x)*w,(focus.bottom-focus.y)*h,0,0,64,40);
      else this.sampleCtx.drawImage(this.canvas,0,0,64,40);
      const pixels=this.sampleCtx.getImageData(0,0,64,40).data,values=[];
      // Use the central image, excluding the usual letterbox margins.
      for(let y=4;y<36;y++)for(let x=6;x<58;x++){const i=(y*64+x)*4;values.push(.2126*pixels[i]+.7152*pixels[i+1]+.0722*pixels[i+2])}
      values.sort((a,b)=>a-b);const light=values[Math.floor(values.length*.65)],target=mode==='boost'?145:112;
      const desired=light<3?1:light<target?Math.max(mode==='boost'?.36:.42,Math.log(target/255)/Math.log(light/255)):1;
      this.gamma=this.lastSample===-Infinity||mode!==this.mode?desired:this.gamma*.7+desired*.3;
      this.lastSample=now;this.mode=mode;
    }
    if(this.gamma>.985)return this.canvas;
    const rounded=Math.round(this.gamma*100)/100;
    if(rounded!==this.lastGamma){for(let i=0;i<256;i++)this.lut[i]=255*Math.pow(i/255,rounded);this.lastGamma=rounded}
    const image=this.ctx.getImageData(0,0,w,h),data=image.data;
    for(let i=0;i<data.length;i+=4){data[i]=this.lut[data[i]];data[i+1]=this.lut[data[i+1]];data[i+2]=this.lut[data[i+2]]}
    this.ctx.putImageData(image,0,0);return this.canvas;
  }
}
