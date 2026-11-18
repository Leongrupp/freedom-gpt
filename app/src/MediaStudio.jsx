import React,{useState} from 'react';
import {Music2,Mic2} from 'lucide-react';
import {MusicStudio} from './MusicStudio.jsx';
import {NarrationStudio} from './NarrationStudio.jsx';
import {t} from './i18n.js';
import './narration-studio.css';

export function MediaStudio(props){
 const[mode,setMode]=useState('music');
 const tabs=<div className="media-kind-tabs" role="tablist" aria-label={t('Режим студии')}><button role="tab" aria-selected={mode==='music'} onClick={()=>setMode('music')}><Music2 size={16}/>{t('Музыка')}</button><button role="tab" aria-selected={mode==='voice'} onClick={()=>setMode('voice')}><Mic2 size={16}/>{t('Озвучка')}</button></div>;
 return mode==='voice'?<NarrationStudio {...props} studioTabs={tabs}/>:<MusicStudio {...props} studioTabs={tabs}/>;
}
