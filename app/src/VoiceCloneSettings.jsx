import React,{useEffect,useRef,useState} from 'react';
import {Upload,Mic,Check,LoaderCircle} from 'lucide-react';
import {api} from './api.js';

export default function VoiceCloneSettings({initial,onChange,onUse,onPreview}){
  const [info,setInfo]=useState(initial),[busy,setBusy]=useState(false),[error,setError]=useState(''),[name,setName]=useState('Мой голос'),[language,setLanguage]=useState('ru');
  const [selected,setSelected]=useState(null),[text,setText]=useState(''),[saved,setSaved]=useState(false);
  const input=useRef(),mounted=useRef(true);
  const apply=value=>{if(!mounted.current)return;setInfo(value);onChange(value)};
  useEffect(()=>{mounted.current=true;api('/speech/profiles').then(apply).catch(e=>setError(e.message));return()=>{mounted.current=false}},[]);
  useEffect(()=>{if(initial)setInfo(initial)},[initial]);
  const processing=info?.profiles?.some(p=>['preparing','transcribing'].includes(p.state));
  const pending=info?.enabled&&(!info.ready||processing);
  useEffect(()=>{if(!pending)return;const timer=setInterval(()=>api('/speech/profiles').then(apply).catch(e=>setError(e.message)),1500);return()=>clearInterval(timer)},[pending]);
  async function upload(file){
    if(!file)return;
    if(file.size>16*1024*1024){setError('Запись должна быть меньше 16 МБ.');return}
    setBusy(true);setError('');setSaved(false);
    try{
      const body=new FormData();body.append('audio',file);body.append('name',name);body.append('language',language);
      const p=await api('/speech/profiles',{method:'POST',body});
      apply(await api('/speech/profiles'));setSelected(p.id);setText(p.text||'');
    }catch(e){setError(e.message)}finally{if(mounted.current)setBusy(false);if(input.current)input.current.value=''}
  }
  async function save(){
    setBusy(true);setError('');try{
      await api('/speech/profiles/'+selected,{method:'POST',body:JSON.stringify({text})});
      apply(await api('/speech/profiles'));setSaved(true);
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }
  const profile=info?.profiles?.find(p=>p.id===selected);
  useEffect(()=>{if(profile?.state==='ready')setText(profile.text)},[profile?.id,profile?.state]);
  return <details className="voice-clone-settings" open={!!info?.profiles?.length}>
    <summary><Mic size={15}/><span>Мой голос</span><small>Локальное клонирование</small></summary>
    <p>Загрузите 15–30 секунд своей речи без музыки. Qwen3-TTS перенесёт тембр и манеру в новые ответы на русском и английском.</p>
    <div className="voice-clone-upload"><input aria-label="Название моего голоса" value={name} maxLength={70} onChange={e=>setName(e.target.value)} placeholder="Название голоса"/>
      <select aria-label="Язык образца голоса" value={language} onChange={e=>setLanguage(e.target.value)}><option value="ru">Русская запись</option><option value="en">English recording</option></select>
      <button type="button" disabled={busy||processing} onClick={()=>input.current?.click()}>{busy?<LoaderCircle size={14} className="spin"/>:<Upload size={14}/>}Загрузить запись</button>
      <input ref={input} type="file" accept="audio/*,.ogg,.wav,.mp3,.m4a,.flac,.webm" hidden onChange={e=>upload(e.target.files?.[0])}/>
    </div>
    {!info?.ready&&<p>Модель клонирования ещё подготавливается.</p>}
    <div className="voice-clone-profiles">{info?.profiles?.map(p=><div className="voice-clone-profile" key={p.id}>
      <div><strong>{p.name}</strong><small>{p.state==='ready'?`${p.seconds} с · русский и английский`:p.state==='error'?p.error:'Распознаю и сохраняю образец…'}</small></div>
      {p.state==='ready'?<><button type="button" onClick={()=>{setSelected(p.id);setText(p.text);setSaved(false)}}>Текст записи</button><button type="button" disabled={!info?.ready} onClick={()=>onUse('clone-'+p.id)}><Check size={13}/>Выбрать</button></>:p.state!=='error'&&<LoaderCircle size={15} className="spin"/>}
    </div>)}</div>
    {profile?.state==='ready'&&<div className="voice-clone-reference">
      <audio controls preload="none" src={'/api/speech/profiles/'+profile.id+'/audio'} aria-label="Образец моего голоса"/>
      <label>Текст, произнесённый в записи<textarea aria-label="Текст образца голоса" value={text} maxLength={2500} onChange={e=>{setText(e.target.value);setSaved(false)}}/></label>
      <div><button type="button" disabled={busy||!text.trim()} onClick={save}>Сохранить текст</button><button type="button" disabled={!info?.ready} onClick={()=>onPreview('clone-'+profile.id)}>Проверить мой голос</button>{saved&&<small><Check size={12}/>Сохранено</small>}</div>
    </div>}
    <p>Запись остаётся на этом ПК. Клонирование на процессоре медленнее стандартных голосов; во время подготовки можно продолжать чат. Сходство и интонации зависят от образца, точное совпадение не гарантируется. Темп регулируется выше.</p>
    {error&&<p className="error-text" role="alert">{error}</p>}
  </details>;
}
