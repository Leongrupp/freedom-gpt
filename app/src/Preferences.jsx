import React, { useEffect, useState } from 'react';
import { RefreshCw, ShieldCheck, Cpu, ChevronRight,UserRound } from 'lucide-react';
import { api } from './api.js';
import {AgentAbout} from './AgentAbout.jsx';
import { SupportCard } from './SupportCard.jsx';
import { t, useLocale } from './i18n.js';
export function LocaleSwitch() {
  const [locale, set] = useLocale();
  return <div className="segmented language-switch" role="group" aria-label={t("Язык интерфейса")}><button className={locale === 'ru' ? 'active' : ''} onClick={() => set('ru')} aria-pressed={locale === 'ru'}>RU</button><button className={locale === 'en' ? 'active' : ''} onClick={() => set('en')} aria-pressed={locale === 'en'}>EN</button></div>;
}
export function Preferences({onAdvisor,onAccounts}) {
  const [state, set] = useState(null),
    [error, setError] = useState('');
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
      setError('');
      set(await api('/updates/' + path, {
        method: 'POST',
        body: JSON.stringify(body)
      }));
    } catch (e) {
      setError(e.message);
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
  return <><AgentAbout/>{onAccounts&&<button className="settings-advisor-link settings-accounts-link" onClick={onAccounts}><UserRound size={20}/><div><strong>{t('Аккаунты и подключения')}</strong><p>{t('GitHub для агента · Hugging Face для моделей · вход по желанию')}</p></div><ChevronRight size={15}/></button>}{onAdvisor&&<button className="settings-advisor-link" onClick={onAdvisor}><Cpu size={20}/><div><strong>{t("Подбор моделей под ваш ПК")}</strong><p>{t("Проверка ПК и рекомендации для кода, чата, изображений и видео")}</p></div><ChevronRight size={15}/></button>}<div className="settings-row"><div><strong>{t("Язык")}</strong><p>{t("Интерфейс на русском или английском")}</p></div><LocaleSwitch /></div><div className="manual-update-note"><ShieldCheck size={17}/><span>{t("Обновления только по вашей команде. Проверка и скачивание начинаются после нажатия кнопки ниже. Установка выполняется, когда агент свободен; чаты и модели сохраняются.")}</span></div><div className="update-status" role="status"><span>{t(labels[state?.state || 'idle'])}{state?.state === 'downloading' ? ' · ' + state.percent + '%' : ''}</span><small>Freedom GPT {state?.current_version || '1.2.0'}{state?.available_version ? ' → ' + state.available_version : ''}</small><button className="icon-text" disabled={['checking', 'downloading', 'applying'].includes(state?.state)} onClick={() => action('check', {})}><RefreshCw size={13} />{t("Проверить обновления")}</button></div>{error && <p role="alert">{t(error)}</p>}<SupportCard/></>;
}
