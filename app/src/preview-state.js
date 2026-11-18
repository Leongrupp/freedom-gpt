// A manually opened preview starts with null state and no browser-worker epoch.
// Do not infer a shared epoch from two absent values.
export function selectPreviewState(previous,next){
 if(!next||typeof next!=='object'||Array.isArray(next))return previous;
 if(!previous)return next;
 if(previous.presentation_epoch&&previous.presentation_epoch===next.presentation_epoch){
  return (previous.sequence||0)>(next.sequence||0)?previous:next;
 }
 if(previous.epoch&&previous.epoch===next.epoch&&
    (previous.updated_at||0)>(next.updated_at||0))return previous;
 return next;
}
