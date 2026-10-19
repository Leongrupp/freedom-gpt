import React,{useState} from 'react';
import {Copy,Check,Heart,MessageCircle,Star,ExternalLink} from 'lucide-react';
import {copyText} from './clipboard.js';
import {t} from './i18n.js';

export function ProjectSupport({support}){
 const[copied,setCopied]=useState(false),[error,setError]=useState('');
 if(!support)return null;
 async function copy(){try{setError('');await copyText(support.bitcoin);setCopied(true);setTimeout(()=>setCopied(false),1800)}catch(e){setError(e.message)}}
 return <section className="support-card project-support" aria-label={t('Связаться и поддержать')}>
  <strong><Heart size={16}/>{t('Спасибо, что вы с Freedom GPT')}</strong>
  <p>{t('Приложение бесплатно. Вопросы и идеи можно отправить автору. Звезда на GitHub и отзывы помогают проекту расти.')}</p>
  <div className="project-support-links">
   <a href={support.telegram} target="_blank" rel="noopener noreferrer"><MessageCircle size={14}/>{t('Поддержка в Telegram')}</a>
   <a href={support.github} target="_blank" rel="noopener noreferrer"><Star size={14}/>{t('Оценить на GitHub')}</a>
   <a href={support.website} target="_blank" rel="noopener noreferrer"><ExternalLink size={14}/>{t('Сайт проекта')}</a>
  </div>
  <p>{t('Развиваю агента Freedom GPT, новые модели и генерацию видео. Спасибо каждому за помощь и поддержку 💛')}</p>
  <details><summary>{t('Добровольно поддержать разработку · Bitcoin')}</summary><p>{t('Донат необязателен и не открывает платных функций.')}</p><code>{support.bitcoin}</code><button className="icon-text" onClick={copy}>{copied?<Check size={13}/>:<Copy size={13}/>} {t(copied?'Скопировано':'Копировать адрес')}</button>{error&&<small role="alert">{error}</small>}</details>
 </section>;
}
