import {localStore,sessionStore} from './browserStorage.js';
import {useEffect,useState} from 'react';
import english from './en.json';
import chinese from './zh-CN.json';
const htmlLanguages={ru:'ru',en:'en',zh:'zh-CN'};
const intlLanguages={ru:'ru-RU',en:'en-GB',zh:'zh-CN'};
const normalize=value=>{const code=String(value||'').toLowerCase().split('-')[0];return Object.hasOwn(htmlLanguages,code)?code:null};
let locale=normalize(localStore.getItem('freedom-language'))||normalize(navigator.language)||'en';
export function getLocale(){return locale}
export function getIntlLocale(){return intlLanguages[locale]}
export function setLocale(value){value=normalize(value);if(!value)return;locale=value;localStore.setItem('freedom-language',value);document.documentElement.lang=htmlLanguages[value];window.dispatchEvent(new Event('freedom-language'))}
export function useLocale(){const[value,set]=useState(locale);useEffect(()=>{const change=()=>set(locale);window.addEventListener('freedom-language',change);document.documentElement.lang=htmlLanguages[locale];return()=>window.removeEventListener('freedom-language',change)},[]);return[value,setLocale]}
const dictionaries={en:english,zh:chinese};
const fragments=Object.fromEntries(Object.entries(dictionaries).map(([code,dict])=>[code,Object.entries(dict).filter(([key])=>code!=='zh'||key.length>=4).sort((a,b)=>b[0].length-a[0].length)]));
const englishToChinese=new Map(Object.entries(english).filter(([key])=>chinese[key]!==undefined).map(([key,value])=>[value,chinese[key]]));
export function t(value){
 if(typeof value!=='string'||locale==='ru')return value;
 const dictionary=dictionaries[locale];
 if(Object.hasOwn(dictionary,value))return dictionary[value];
 if(locale==='zh'&&englishToChinese.has(value))return englishToChinese.get(value);
 for(const[from,to]of fragments[locale])if(value.includes(from))value=value.replaceAll(from,to);
 return value;
}
