// The hosted phone UI serves only trusted project assets. Its persistent state
// is additionally scoped per PC, so drafts never carry into another computer.
export function scopedStorage(native,prefix=''){
 const fallback=new Map();
 function keys(){const names=new Set(fallback.keys());try{for(let i=0;i<native.length;i++){const key=native.key(i);if(key?.startsWith(prefix))names.add(key.slice(prefix.length))}}catch{}return [...names]}
 return {getItem(key){try{return native.getItem(prefix+key)??fallback.get(String(key))??null}catch{return fallback.get(String(key))??null}},
  setItem(key,value){fallback.set(String(key),String(value));try{native.setItem(prefix+key,String(value))}catch{}},
  removeItem(key){fallback.delete(String(key));try{native.removeItem(prefix+key)}catch{}},
  key(index){return keys()[index]??null},get length(){return keys().length},clear(){for(const key of keys())this.removeItem(key)}};
}
const prefix=typeof document!=='undefined'&&document.documentElement.dataset.freedomRemote?'remote:'+document.documentElement.dataset.freedomRemote+':':'';
let local,session;try{local=window.localStorage;session=window.sessionStorage}catch{}
export const localStore=scopedStorage(local,prefix),sessionStore=scopedStorage(session,prefix);
