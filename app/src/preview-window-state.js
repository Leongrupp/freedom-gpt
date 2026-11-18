export function previewWindowState(key,prefs={}){return {key,open:Boolean(prefs.manual&&prefs.open),manual:Boolean(prefs.manual),automatic:false,muted:Boolean(prefs.muted),finished:Boolean(prefs.finished),latest:null,request:null}}
export function updatePreviewWindow(state,frame){
 if(frame.session_id&&frame.session_id!==state.key)return state;
 const before=state.latest,nextFrame=frame.preview;
 if(before?.presentation_epoch&&before.presentation_epoch===nextFrame?.presentation_epoch&&(before.sequence||0)>(nextFrame.sequence||0))return state;
 let next={...state};
 if(frame.type==='preview.changed'){
  if(frame.preview)next.latest=frame.preview;
  const active=frame.preview?.activity?.active;
  if(active===false&&(state.automatic||state.latest?.activity?.active||state.finished)){
   next.finished=true;if(state.automatic)next.open=false;
  }
  if(frame.open&&active!==false&&!state.muted){next.open=true;next.automatic=state.open?!state.manual:true;next.finished=false;if(!state.open){next.request=null;next.manual=false}}
 }else if(frame.type==='preview.finished'){
  if(frame.preview)next.latest=frame.preview;
  next.finished=true;
  if(next.automatic)next.open=false;
 }else if(frame.type==='gateway.event'&&frame.event_type==='message.start'){
  next.muted=false;next.finished=false;
 }
 return next;
}
