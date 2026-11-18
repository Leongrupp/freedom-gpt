import React,{useEffect,useState} from 'react';
import {Clock3,KeyRound,Search,Trash2,X,ArrowUpRight,LockKeyhole} from 'lucide-react';
import {api} from './api.js';

export function PreviewLibrary({kind,sid,url,onClose,onOpen,onFilled}){
 const[rows,setRows]=useState([]),[query,setQuery]=useState(''),[site,setSite]=useState(null),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 async function load(){
  const data=await api(kind==='history'?'/browser/history?q='+encodeURIComponent(query):'/browser/'+sid+'/logins');
  setRows(data.visits||data.logins||[]);setSite(data.origin||null);
 }
 useEffect(()=>{let cancelled=false;setError('');setRows([]);setPassword('');setNotice('');
  const timer=setTimeout(async()=>{try{const data=await api(kind==='history'?'/browser/history?q='+encodeURIComponent(query):'/browser/'+sid+'/logins');if(!cancelled){setRows(data.visits||data.logins||[]);setSite(data.origin||null)}}catch(e){if(!cancelled)setError(e.message)}},kind==='history'?150:0);
  return()=>{cancelled=true;clearTimeout(timer)};
 },[kind,sid,query,url]);
 async function login(action,row){
  setBusy(true);setError('');setNotice('');
  try{await api('/browser/'+sid+'/logins',{method:'POST',body:JSON.stringify({action,origin:site,...(row?{id:row.id}:{username,password})})});
   setPassword('');await load();setNotice(action==='save'?'Вход сохранён на этом компьютере.':action==='delete'?'Вход удалён.':'Вход заполнен. Проверьте форму и нажмите кнопку входа на сайте.');if(action==='fill')onFilled?.();
  }catch(e){setError(e.message)}finally{setBusy(false)}
 }
 async function clear(){setBusy(true);try{await api('/browser/history',{method:'DELETE'});setRows([])}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <section className="preview-library" aria-label={kind==='history'?'История браузера':'Сохранённые входы'}>
  <header><strong>{kind==='history'?<Clock3 size={15}/>:<KeyRound size={15}/>} {kind==='history'?'История браузера':'Сохранённые входы'}</strong><button className="icon-button" aria-label="Закрыть историю и входы" onClick={onClose}><X size={15}/></button></header>
  {kind==='history'?<>
   <label className="preview-library-search"><Search size={14}/><input autoFocus placeholder="Найти страницу…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
   <div className="preview-library-list">{rows.map(row=><div className="preview-history-row" key={row.id}><button onClick={()=>{onOpen(row.url);onClose()}} title={row.url}><strong>{row.title||row.url}</strong><span>{row.url}</span><small>{new Date(row.visited*1000).toLocaleString('ru-RU',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</small></button><ArrowUpRight size={14}/></div>)}{!rows.length&&<p className="preview-library-empty">{query?'Ничего не найдено.':'Здесь появятся посещённые страницы.'}</p>}</div>
   {!!rows.length&&<button className="preview-library-clear" disabled={busy} onClick={clear}><Trash2 size={12}/> Очистить историю посещений</button>}
  </>:<>
   <p className="preview-library-note"><LockKeyhole size={14}/> Пароли зашифрованы Windows и хранятся на этом ПК. Заполнение — только для точного адреса сайта.</p>
   {site?<><div className="preview-login-site">{site}</div><div className="preview-library-list">{rows.map(row=><div key={row.id} className="preview-login-row"><strong>{row.username}</strong><button disabled={busy} onClick={()=>login('fill',row)}>Заполнить</button><button className="icon-button" disabled={busy} aria-label={'Удалить вход '+row.username} onClick={()=>login('delete',row)}><Trash2 size={13}/></button></div>)}</div>
    <form className="preview-login-form" onSubmit={e=>{e.preventDefault();login('save')}}><label>Логин<input autoComplete="username" value={username} maxLength={500} onChange={e=>setUsername(e.target.value)} placeholder="Email или имя пользователя" required/></label><label>Пароль<input type="password" autoComplete="new-password" value={password} maxLength={4096} onChange={e=>setPassword(e.target.value)} placeholder="Сохранить для этого сайта" required/></label><button disabled={busy||!username.trim()||!password}><KeyRound size={13}/> Сохранить вход</button></form>
   </>:<p className="preview-library-empty">Откройте сайт, чтобы сохранить или заполнить вход.</p>}
  </>}
  {error&&<p className="preview-library-error" role="alert">{error}</p>}{notice&&<p className="preview-library-notice" role="status">{notice}</p>}
  <footer>Общий профиль Freedom: входы на сайты сохраняются между чатами и перезапусками. История и пароли не добавляются в переписку.</footer>
 </section>;
}
