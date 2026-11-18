import React,{useEffect,useRef,useState} from 'react';
export default function JarvisFace({name='Арчи',enabled,phase,mood,mic,activation,quality,output,onFallback,onTouch}){
 const host=useRef(null),signal=useRef({}),[note,setNote]=useState('');signal.current={enabled,phase,mood,mic,activation,output,onTouch};
 useEffect(()=>{
  let cancelled=false,scene;
  import('./JarvisFaceScene.js').then(({JarvisFaceScene})=>{if(cancelled||!host.current)return;try{scene=new JarvisFaceScene(host.current,{signal:()=>signal.current,quality,onQuality:setNote,onError:message=>{if(!cancelled)onFallback(message)}})}catch{scene?.close();if(!cancelled)onFallback('3D недоступно. Голосовое управление продолжает работать.')}}).catch(()=>{if(!cancelled)onFallback('Не удалось загрузить 3D. Голосовое управление доступно.')});
  return()=>{cancelled=true;scene?.close()};
 },[quality]);
 return <div className="jarvis-face" aria-label={'Голографический образ '+name}><div className="jarvis-face-canvas" ref={host}/><div className="jarvis-face-mark top-left">FREEDOM<span>СИЛУЭТ ИЗ СВЕТА</span></div><div className="jarvis-face-mark top-right">3D<span>ЖИВОЙ ГОЛОС</span></div><div className="jarvis-face-ruler" aria-hidden="true"/>{note&&<small className="jarvis-face-quality">{note}</small>}</div>;
}
