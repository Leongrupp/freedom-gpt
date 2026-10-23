import {localStore,sessionStore} from './browserStorage.js';
import {useCallback,useEffect,useRef,useState} from 'react';
import {api} from './api.js';
import {previewWindowState,updatePreviewWindow} from './preview-window-state.js';

function remembered(key){try{const value=JSON.parse(sessionStore.getItem('freedom-preview-ui:'+key)||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{}}catch{return {}}}
function remember(state){
 try{const key='freedom-preview-ui:'+state.key,value=JSON.stringify({manual:state.manual,open:state.open,muted:state.muted,finished:state.finished});if(sessionStore.getItem(key)!==value)sessionStore.setItem(key,value)}catch{}
}

export function usePreviewWindow(sid){
 const key=sid||'workspace',states=useRef(new Map()),timers=useRef(new Map()),keyRef=useRef(key);
 const [view,setView]=useState(()=>previewWindowState(key,remembered(key)));keyRef.current=key;
 const get=useCallback(id=>{
  if(!states.current.has(id))states.current.set(id,previewWindowState(id,remembered(id)));
  return states.current.get(id);
 },[]);
 const commit=useCallback(state=>{
  states.current.set(state.key,state);remember(state);
  if(state.key===keyRef.current)setView(state);
  if(states.current.size>40){for(const[id,value]of states.current){if(id!==keyRef.current&&!value.latest?.activity?.active){clearTimeout(timers.current.get(id));timers.current.delete(id);states.current.delete(id);if(states.current.size<=40)break}}}
 },[]);
 const receive=useCallback(frame=>{
  const id=frame.session_id;if(!id)return;
  const state=get(id),next=updatePreviewWindow(state,frame);if(next===state)return;
  if(frame.type==='preview.finished'){
   clearTimeout(timers.current.get(id));commit({...next,open:state.open});
   timers.current.set(id,setTimeout(()=>{timers.current.delete(id);commit(updatePreviewWindow(get(id),frame))},900));return;
  }
  if((frame.type==='preview.changed'&&frame.open)||(frame.type==='gateway.event'&&frame.event_type==='message.start')){clearTimeout(timers.current.get(id));timers.current.delete(id)}
  commit(next);
 },[get,commit]);
 const reconcile=useCallback((id,preview,open=false)=>receive({type:'preview.changed',session_id:id,preview,open}),[receive]);
 const refresh=useCallback(()=>{
  const id=keyRef.current;
  return api('/preview/'+id).then(preview=>reconcile(id,preview,Boolean(preview.activity?.active))).catch(()=>{});
 },[reconcile]);
 useEffect(()=>{commit(get(key));refresh()},[key,commit,get,refresh]);
 useEffect(()=>()=>{for(const timer of timers.current.values())clearTimeout(timer)},[]);
 const open=useCallback(url=>{
  const id=keyRef.current;clearTimeout(timers.current.get(id));timers.current.delete(id);
  commit({...get(id),open:true,manual:true,automatic:false,muted:false,request:url?{id:crypto.randomUUID(),url}:null});
 },[get,commit]);
 const close=useCallback(()=>{
  const id=keyRef.current;clearTimeout(timers.current.get(id));timers.current.delete(id);
  commit({...get(id),open:false,manual:false,automatic:false,muted:true});
 },[get,commit]);
 return {view:view.key===key?view:get(key),open,close,receive,reconcile,refresh};
}
