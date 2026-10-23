import React,{useEffect,useRef,useState} from 'react';
import {Heart,Bitcoin,Copy,Check,Download} from 'lucide-react';
import appVersion from '../version.json';
import {copyText} from './clipboard.js';
import {t} from './i18n.js';
import qrUrl from './assets/bitcoin-qr.svg?url';
import './support-card.css';

export function SupportCard(){
 const address=appVersion.support.bitcoin;
 const[copied,setCopied]=useState(false),[error,setError]=useState('');
 const timer=useRef(null);
 useEffect(()=>()=>clearTimeout(timer.current),[]);
 async function copy(){
  try{await copyText(address);setError('');setCopied(true);clearTimeout(timer.current);timer.current=setTimeout(()=>setCopied(false),1800)}
  catch(e){setError(e.message)}
 }
 return <section className="support-card donation-card" aria-label={t('Поддержать Freedom GPT')}>
  <a className="donation-qr" href={qrUrl} target="_blank" rel="noreferrer" title={t('Открыть QR-код')}><img src={qrUrl} width="98" height="98" alt={t('QR-код для поддержки Freedom GPT')}/></a>
  <div className="donation-details">
   <header className="donation-header"><Heart size={14}/><strong>{t('Поддержать Freedom GPT')}</strong></header>
   <span className="donation-network"><Bitcoin size={12}/>Bitcoin · BTC</span>
   <code className="donation-address">{address}</code>
   <div className="donation-actions">
    <button type="button" className="donation-copy" onClick={copy} aria-label={copied?t('Скопировано'):t('Копировать адрес')}>{copied?<Check size={12}/>:<Copy size={12}/>}<span aria-live="polite">{copied?t('Скопировано'):t('Копировать')}</span></button>
    <a className="donation-save" href={qrUrl} download="Freedom-GPT-Bitcoin-QR.svg" title={t('Сохранить QR-код')} aria-label={t('Сохранить QR-код')}><Download size={14}/></a>
   </div>
   {error&&<p role="alert" className="copy-error">{t(error)}</p>}
  </div>
 </section>;
}
