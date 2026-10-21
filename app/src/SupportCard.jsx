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
  <header className="donation-header"><span className="donation-heart"><Heart size={19}/></span><div><strong>{t('Поддержать Freedom GPT')}</strong><p>{t('Приложение бесплатно. Если оно помогает вам в работе, можно поддержать развитие.')}</p></div></header>
  <div className="donation-layout">
   <div className="donation-qr-wrap"><a className="donation-qr" href={qrUrl} target="_blank" rel="noreferrer" title={t('Открыть QR-код')}><img src={qrUrl} width="196" height="196" alt={t('QR-код для поддержки Freedom GPT')}/></a><a className="donation-save" href={qrUrl} download="Freedom-GPT-Bitcoin-QR.svg"><Download size={12}/>{t('Сохранить QR-код')}</a></div>
   <div className="donation-details"><span className="donation-network"><Bitcoin size={15}/>Bitcoin · BTC</span><p className="donation-instructions">{t('Отсканируйте QR-код в Bitcoin-кошельке')}</p><span className="donation-address-label">{t('Адрес кошелька')}</span><code className="donation-address">{address}</code><button type="button" className="donation-copy" onClick={copy}>{copied?<Check size={14}/>:<Copy size={14}/>}<span aria-live="polite">{copied?t('Скопировано'):t('Копировать адрес')}</span></button>{error&&<p role="alert" className="copy-error">{t(error)}</p>}<small className="donation-thanks"><Heart size={11}/>{t('Спасибо за поддержку проекта')}</small></div>
  </div>
 </section>;
}
