const uid=m=>m?.message_uid||m?.message_id||m?.row_id;
export function voiceReplyBaseline(messages=[]){return new Set(messages.map(uid).filter(v=>v!=null))}
// Completion belongs to a turn, not to the queue's global busy indicator.
export function readyVoiceReplies(messages,pending,sid,busy){
 const found=new Map();let user=null;
 for(const reply of messages){
  if(reply.role==='user'){user=reply;continue}
  if(!user||reply.role!=='assistant'||!reply.content||reply.tool_calls?.length)continue;
  const finished=Number(reply.work_timing?.finished)>0;
  if(busy&&!finished)continue;
  for(const [id,q] of pending){
   if(q.sid!==sid||q.before?.has(uid(user))||String(user.content||'').trim()!==q.text.trim())continue;
   const owner=user.display_metadata?.gateway_input_owner;
   if(q.owner&&owner&&q.owner!==owner)continue;
   found.set(id,{id,reply});break;
  }
 }
 return [...found.values()];
}
