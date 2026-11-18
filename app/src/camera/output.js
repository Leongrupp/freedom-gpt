// OBS receives only the protected output; raw input is never a fallback URL.
const image=document.querySelector('#output');
const key=location.pathname.split('/').pop();let stopped=false;
async function next(){
  while(!stopped){
    try{
      const response=await fetch('/api/camera/output.jpg?key='+encodeURIComponent(key)+'&t='+Date.now(),{cache:'no-store'});
      if(!response.ok)throw Error('Output unavailable');
      const blob=await response.blob(),url=URL.createObjectURL(blob),previous=image.src;
      await new Promise(resolve=>{image.onload=resolve;image.onerror=resolve;image.src=url});
      if(previous.startsWith('blob:'))URL.revokeObjectURL(previous);
    }catch{image.removeAttribute('src')}
    await new Promise(resolve=>setTimeout(resolve,40));
  }
}
window.addEventListener('pagehide',()=>{stopped=true});next();
