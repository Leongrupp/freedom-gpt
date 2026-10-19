import {useEffect,useState} from 'react';
import english from './en.json';
let locale=localStorage.getItem('freedom-language')||(navigator.language?.toLowerCase().startsWith('ru')?'ru':'en');
if(!['ru','en'].includes(locale))locale='en';
export function getLocale(){return locale}
export function setLocale(value){if(!['ru','en'].includes(value))return;locale=value;localStorage.setItem('freedom-language',value);document.documentElement.lang=value;window.dispatchEvent(new Event('freedom-language'))}
export function useLocale(){const[value,set]=useState(locale);useEffect(()=>{const change=()=>set(locale);window.addEventListener('freedom-language',change);document.documentElement.lang=locale;return()=>window.removeEventListener('freedom-language',change)},[]);return[value,setLocale]}
const fragments=Object.entries(english).sort((a,b)=>b[0].length-a[0].length);
export function t(value){if(typeof value!=='string'||locale==='ru')return value;if(english[value]!==undefined)return english[value];for(const[from,to]of fragments)if(value.includes(from))value=value.replaceAll(from,to);return value}
