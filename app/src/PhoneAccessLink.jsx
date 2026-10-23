import React from 'react';
import {Smartphone,ChevronRight} from 'lucide-react';
import {t} from './i18n.js';

export function PhoneAccessLink({onOpen}){
  if(!onOpen||!['127.0.0.1','localhost'].includes(location.hostname))return null;
  return <button className="settings-advisor-link" onClick={onOpen}>
    <Smartphone size={20}/><div><strong>{t('Доступ с телефона')}</strong><p>{t('iPhone и браузер · QR-код · подтверждение на вашем ПК')}</p></div><ChevronRight size={15}/>
  </button>;
}
