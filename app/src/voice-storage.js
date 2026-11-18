// Audio drafts stay on this device until the PC confirms a durable task receipt.
const memory=new Map();
const scope=typeof document!=='undefined'&&document.documentElement.dataset.freedomRemote||'local';
const key=id=>scope+':'+id;
function database(){return new Promise((resolve,reject)=>{
 if(typeof indexedDB==='undefined'){reject(new Error('Storage unavailable'));return}
 const request=indexedDB.open('freedom-private-voice-v1',1);
 request.onupgradeneeded=()=>request.result.createObjectStore('pending',{keyPath:'key'});
 request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
})}
async function transact(mode,run){const db=await database();try{return await new Promise((resolve,reject)=>{
 const tx=db.transaction('pending',mode),request=run(tx.objectStore('pending'));
 tx.oncomplete=()=>resolve(request?.result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
})}finally{db.close()}}
export async function saveVoice(job){const value={...job,key:key(job.id),scope};memory.set(value.key,value);try{await transact('readwrite',store=>store.put(value))}catch{}return value}
export async function clearVoice(id){memory.delete(key(id));try{await transact('readwrite',store=>store.delete(key(id)))}catch{}}
export async function loadVoice(){let rows=[];try{rows=await transact('readonly',store=>store.getAll())}catch{}
 return [...new Map([...rows,...memory.values()].map(row=>[row.key,row])).values()].filter(row=>row.scope===scope).sort((a,b)=>b.created-a.created)[0]||null;
}
