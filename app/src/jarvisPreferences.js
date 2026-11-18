import {useSyncExternalStore} from 'react';
import {localStore} from './browserStorage.js';
import {preferences} from './jarvisPolicy.js';
const key='freedom-jarvis',listeners=new Set();
function read(){try{return preferences(JSON.parse(localStore.getItem(key)||'{}'))}catch{return preferences()}}
let current=read();
export function changeJarvisPreferences(patch){current=preferences({...current,...patch});localStore.setItem(key,JSON.stringify(current));for(const listener of listeners)listener()}
export function useJarvisPreferences(){return useSyncExternalStore(listener=>{listeners.add(listener);return()=>listeners.delete(listener)},()=>current)}
window.addEventListener('storage',event=>{if(event.key?.endsWith(key)){current=read();for(const listener of listeners)listener()}});
export function jarvisControl(action){window.dispatchEvent(new CustomEvent('freedom-jarvis-control',{detail:{action}}))}
