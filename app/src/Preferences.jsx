import {NotificationSettings} from './CompletionNotifications.jsx';
import React, { useEffect, useState } from 'react';
import { RefreshCw, ShieldCheck, Cpu, ChevronRight,UserRound } from 'lucide-react';
import { api } from './api.js';
import {AgentAbout} from './AgentAbout.jsx';
import { SupportCard } from './SupportCard.jsx';
import {PhoneAccessLink} from './PhoneAccessLink.jsx';
import { t, useLocale } from './i18n.js';
import appVersion from '../version.json';
import './program-update.css';
export function LocaleSwitch() {
  const [locale, set] = useLocale();
  return <div className="segmented language-switch" role="group" aria-label={t("Язык интерфейса")}>
    <button className={locale === 'ru' ? 'active' : ''} onClick={() => set('ru')} aria-pressed={locale === 'ru'} title="Русский">RU</button>
    <button className={locale === 'en' ? 'active' : ''} onClick={() => set('en')} aria-pressed={locale === 'en'} title="English">EN</button>
    <button lang="zh-CN" className={locale === 'zh' ? 'active' : ''} onClick={() => set('zh')} aria-pressed={locale === 'zh'} title="简体中文">中文</button>
  </div>;
}
export function Preferences({onAdvisor,onAccounts,onPhone}) {
  return <>
    <AgentAbout/>
    <NotificationSettings/>
    <PhoneAccessLink onOpen={onPhone}/>
    {onAccounts&&<button className="settings-advisor-link settings-accounts-link" onClick={onAccounts}><UserRound size={20}/><div><strong>{t('Аккаунты и подключения')}</strong><p>{t('GitHub для агента · Hugging Face для моделей · вход по желанию')}</p></div><ChevronRight size={15}/></button>}
    {onAdvisor&&<button className="settings-advisor-link" onClick={onAdvisor}><Cpu size={20}/><div><strong>{t("Подбор моделей под ваш ПК")}</strong><p>{t("Проверка ПК и рекомендации для кода, чата, изображений и видео")}</p></div><ChevronRight size={15}/></button>}
    <div className="manual-update-note"><ShieldCheck size={17}/><span>{t("Обновления только по вашей команде. Проверка и скачивание начинаются после нажатия кнопки ниже. Установка выполняется, когда агент свободен; чаты и модели сохраняются.")}</span></div>
    <SupportCard/>
  </>;
}
export function ProgramUpdate() {
  const [state, set] = useState(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let closed = false;
    const load = async () => {
      try {
        const d = await api('/updates');
        if (!closed) set(d);
      } catch (e) {
        if (!closed) setError(e.message);
      }
    };
    load();
    const timer = setInterval(load, 2000);
    return () => {
      closed = true;
      clearInterval(timer);
    };
  }, []);
  async function action(path, body) {
    try {
      setBusy(true);
      setError('');
      set(await api('/updates/' + path, {
        method: 'POST',
        body: JSON.stringify(body)
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const labels = {
    idle: t("Ожидаем проверку"),
    checking: t("Проверяем обновления"),
    current: t("Установлена актуальная версия"),
    downloading: t("Скачиваем обновление"),
    ready: t("Обновление скачано по вашему запросу. Ожидает завершения задач."),
    applying: t("Устанавливаем обновление. Окно восстановится автоматически."),
    error: t("Проверка недоступна. Нажмите кнопку, чтобы повторить.")
  };
  const updating=busy||['checking','downloading','applying'].includes(state?.state);
  return <section className="program-update">
    <button type="button" className="program-update-button" disabled={updating} onClick={()=>action('check',{})}>
      <RefreshCw size={16} className={updating?'spin':undefined}/>
      <span>{t('Обновить программу')}</span>
    </button>
    <div className="program-update-status" role="status" aria-live="polite">
      <span>{labels[state?.state||'idle']}{state?.state==='downloading'?' · '+state.percent+'%':''}</span>
      <small>Freedom GPT {state?.current_version||appVersion.version}{state?.available_version?' → '+state.available_version:''}</small>
    </div>
    {error&&<p className="error-text" role="alert">{t(error)}</p>}
  </section>;
}
