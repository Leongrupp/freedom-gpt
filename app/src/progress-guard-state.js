export function guardStoppedReply(message,index,count,notice){
 if(!notice||message?.role!=='assistant'||index!==count-1)return false;
 return /^(?:Your request was not processed\.|This turn did not complete\.|Interrupted by user\.?)/i.test(String(message.content||'').trim());
}
