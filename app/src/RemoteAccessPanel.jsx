import React,{useEffect,useState} from 'react';
import {Smartphone,ShieldCheck,QrCode,Wifi,RefreshCw,Link,Check,Monitor,ExternalLink} from 'lucide-react';
import {api} from './api.js';
import {copyText} from './clipboard.js';
import {t} from './i18n.js';
import './remote-access.css';

export function RemoteAccessPanel(){
 const[state,setState]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[copied,setCopied]=useState(false);
 async function load(){try{setState(await api('/phone'))}catch(e){setError(e.message)}}
 useEffect(()=>{load();const timer=setInterval(load,2000);return()=>clearInterval(timer)},[]);
 async function action(action,extra={}){try{setBusy(true);setError('');setState(await api('/phone',{method:'POST',body:JSON.stringify({action,...extra})}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function copy(){try{await copyText(state.public_url);setCopied(true);setTimeout(()=>setCopied(false),1500)}catch(e){setError(e.message)}}
 const ready=state?.state==='connected',pair=state?.pair;
 return <div className="remote-access"><div className="remote-intro"><span className="remote-phone-icon"><Smartphone size={27}/></span><div><h3>{t('Ваш агент — с вами')}</h3><p>{t('Чаты, работа агента и новые задания на телефоне, пока компьютер включён.')}</p></div></div>
 <div className="remote-toggle-row"><div><strong>{t('Доступ с телефона')}</strong><small>{t('По желанию · через интернет · без дополнительной подписки')}</small></div><button role="switch" aria-label={t('Доступ с телефона')} aria-checked={!!state?.enabled} className={'toggle '+(state?.enabled?'on':'')} disabled={busy||!state} onClick={()=>action('settings',{enabled:!state.enabled})}><span/></button></div>
 <div className={'remote-status '+(ready?'ready':'')}><Wifi size={14}/><span>{ready?t('Соединение с сервером готово'):state?.enabled?t('Подключаем ваш компьютер…'):t('Выключено. Программа работает локально.')}</span></div>
 {state?.enabled&&<>
 {state.device&&<div className="remote-device"><ShieldCheck size={20}/><div><strong>{state.device.label}</strong><small>{t('Телефон допущен к этому компьютеру')}</small></div><button disabled={busy||!ready} onClick={()=>action('revoke')}>{t('Отозвать доступ')}</button></div>}
 {state?.pending?.map(phone=><section className="remote-approval" key={phone.id}><div><Smartphone size={17}/><strong>{t('Запрос на подключение')}</strong></div><p>{phone.label} · {t('Сравните код с экраном телефона')}</p><div className="remote-code">{phone.code}</div><div className="remote-approval-actions"><button className="primary-button" disabled={busy} onClick={()=>action('approve',{claim_id:phone.id})}>{t('Разрешить')}</button><button disabled={busy} onClick={()=>action('reject',{claim_id:phone.id})}>{t('Отклонить')}</button></div></section>)}
 {pair&&ready?<div className="remote-pair"><div className="remote-qr"><img src={'/api/phone/qr.svg?expires='+pair.expires} alt={t('QR-код подключения телефона')}/></div><div><h4>{t('Откройте камеру на iPhone')}</h4><ol><li>{t('Отсканируйте QR-код и нажмите «Подключить этот телефон».')}</li><li>{t('Сравните код и подтвердите запрос здесь, на компьютере.')}</li><li>{t('Добавьте страницу в Safari на экран «Домой».')}</li></ol><small>{t('QR-код действует 5 минут. Новый телефон заменит прежний только после вашего подтверждения.')}</small></div></div>:<button className="remote-pair-button" disabled={busy||!ready} onClick={()=>action('pair')}><QrCode size={19}/>{t(state?.device?'Подключить другой телефон':'Показать QR-код')}</button>}
 <div className="remote-public-url"><Link size={14}/><code>{state.public_url}</code><button className="icon-button" title={t('Копировать адрес')} onClick={copy}>{copied?<Check size={15}/>:<Link size={15}/>}</button></div>
 </>}
 <div className="remote-explanation"><Monitor size={16}/><p>{t('Вычисления остаются на вашем ПК. Для удалённой работы данные передаются через сервер проекта по HTTPS; история и файлы на нём не сохраняются. Локальный режим не требует этого подключения.')}</p></div>
 <p className="muted-copy">{t('Компьютер должен быть включён, не находиться в режиме сна и иметь интернет. Профиль VPN и приложение из App Store не нужны. Ограничение загрузки через телефон — 20 МБ на запрос. При высокой нагрузке сервер может предложить подключиться позже.')}</p>
 {import.meta.env.VITE_OWNER_PHONE_CONTROL==='1'&&['localhost','127.0.0.1'].includes(location.hostname)&&<a className="remote-existing" href="http://127.0.0.1:17868/local/" target="_blank" rel="noreferrer"><ShieldCheck size={14}/>{t('Мой действующий личный доступ')}<ExternalLink size={12}/></a>}
 {(error||state?.error)&&<p className="error-text" role="alert">{error||state.error}</p>}
 </div>
}
