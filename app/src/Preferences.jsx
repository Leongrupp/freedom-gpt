import React, { useEffect, useState } from 'react';
import { RefreshCw, Copy, Check } from 'lucide-react';
import { api } from './api.js';
import { ProjectSupport } from './ProjectSupport.jsx';
import { t, useLocale } from './i18n.js';
export function LocaleSwitch() {
  const [locale, set] = useLocale();
  return <div className="segmented language-switch" role="group" aria-label={t("Язык интерфейса")}><button className={locale === 'ru' ? 'active' : ''} onClick={() => set('ru')} aria-pressed={locale === 'ru'}>RU</button><button className={locale === 'en' ? 'active' : ''} onClick={() => set('en')} aria-pressed={locale === 'en'}>EN</button></div>;
}
export function Preferences({support}) {
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
    ready: t("Обновление готово. Установится между задачами."),
    applying: t("Устанавливаем обновление. Окно восстановится автоматически."),
    error: t("Проверка недоступна. Попробуем позже.")
  };
  return <><div className="settings-row"><div><strong>{t("Язык")}</strong><p>{t("Интерфейс на русском или английском")}</p></div><LocaleSwitch /></div><div className="settings-row"><div><strong>{t("Автоматические обновления")}</strong><p>{t("Новые версии устанавливаются между задачами. Модели и чаты сохраняются.")}</p></div><button role="switch" aria-label={t("Автоматические обновления")} aria-checked={state?.enabled ?? true} className={'toggle ' + (state?.enabled ?? true ? 'on' : '')} onClick={() => action('settings', {
        enabled: !state?.enabled
      })}><span /></button></div><div className="update-status" role="status"><span>{t(labels[state?.state || 'idle'])}{state?.state === 'downloading' ? ' · ' + state.percent + '%' : ''}</span><small>Freedom GPT {state?.current_version || '1.2.0'}{state?.available_version ? ' → ' + state.available_version : ''}</small><button className="icon-text" disabled={['checking', 'downloading', 'applying'].includes(state?.state)} onClick={() => action('check', {})}><RefreshCw size={13} />{t("Проверить обновления")}</button></div>{error && <p role="alert">{t(error)}</p>}<ProjectSupport support={support}/></>;
}
