import { t } from './i18n.js';
import { LocaleSwitch } from './Preferences.jsx';
import React, { useEffect, useState, useRef } from 'react';
import { X, Cpu, HardDrive, Download, Check, Pause, RefreshCw, Plus, FolderOpen, ChevronRight, Sparkles, AlertCircle } from 'lucide-react';
import { api } from './api.js';
const gb = n => (n / 1024 ** 3).toFixed(1) + t(" ГБ");
export function ModelLibrary({
  onClose,
  onActivated
}) {
  const [data, setData] = useState(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(''),
    [tab, setTab] = useState('catalog');
  const [path, setPath] = useState(''),
    [repo, setRepo] = useState(''),
    [remote, setRemote] = useState(null),
    [filename, setFilename] = useState('');
  const [endpoint, setEndpoint] = useState('http://127.0.0.1:1234/v1'),
    [externalModel, setExternalModel] = useState(''),
    [externalContext, setExternalContext] = useState(65536);
  const requested = useRef(false);
  useEffect(() => {
    let disposed = false;
    async function load() {
      try {
        const next = await api('/library');
        if (disposed) return;
        setData(next);
        if (requested.current && next.activation?.state === 'ready') onActivated();
      } catch (e) {
        if (!disposed) setError(e.message);
      }
    }
    load();
    const id = setInterval(load, 1800);
    return () => {
      disposed = true;
      clearInterval(id);
    };
  }, []);
  async function action(type, payload = {}) {
    setError('');
    setBusy(type + (payload.id || ''));
    if (type === 'activate') requested.current = true;
    try {
      const next = await api('/library/' + type, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      if (type === 'connect') onActivated();
      if (type === 'hf') {
        setRemote(next);
        setFilename(next.files[0]?.name || '');
      }
      if (type === 'hf-add') {
        setTab('catalog');
        setRemote(null);
      }
      if (type === 'import') {
        setPath('');
        setTab('catalog');
      }
      if (type === 'scan') setData(next);else setData(await api('/library'));
    } catch (e) {
      setError(e.message);
      requested.current = false;
    } finally {
      setBusy('');
    }
  }
  const hw = data?.hardware || {},
    models = data?.models || [];
  return <div className="modal-backdrop"><section role="dialog" aria-modal="true" aria-label={t("Модели Freedom GPT")} className="modal library-modal"><header><LocaleSwitch /><div><div className="library-eyebrow">{t("FREEDOM GPT · ВАШ КОМПЬЮТЕР")}</div><h2>{data?.first_run ? t("Начнём с вашего ПК") : t("Модели и загрузки")}</h2><p>{t("Выберите модель под своё железо. После загрузки она работает без интернета.")}</p></div><button className="icon-button" aria-label={t("Закрыть")} onClick={onClose}><X size={18} /></button></header>
 <div className="hardware-summary"><div><Cpu size={18} /><strong>{hw.cpu || t("Определяем процессор…")}</strong><span>{hw.physical_cores || '—'}{t(" ядер · ")}{hw.ram_gb || '—'}{t(" ГБ RAM")}</span></div><div><Sparkles size={18} /><strong>{hw.gpus?.map(g => g.name).join(', ') || t("Определяем видеокарту…")}</strong><span>{hw.vram_gb ? hw.vram_gb + t(" ГБ VRAM") : t("CPU / видеопамять не определена")}</span></div><div><HardDrive size={18} /><strong>{hw.free_disk_gb || '—'}{t(" ГБ свободно")}</strong><span title={hw.storage}>{hw.storage || t("Папка приложения")}</span></div></div>
 <div className="library-toolbar"><div className="segmented"><button className={tab === 'catalog' ? 'active' : ''} onClick={() => setTab('catalog')}>{t("Каталог")}</button><button className={tab === 'import' ? 'active' : ''} onClick={() => setTab('import')}>{t("Другие модели")}</button></div><button className="icon-text" disabled={!!busy} onClick={() => action('scan')}><RefreshCw size={14} />{t("Проверить ПК")}</button></div>
 {error && <div role="alert" className="library-error"><AlertCircle size={16} />{t(error)}</div>}
 {data?.activation?.state === 'loading' && <div role="status" className="library-notice"><RefreshCw className="spin" size={15} />{t("Загружаем модель в память. Это может занять несколько минут.")}</div>}
 {data?.activation?.state === 'error' && <div role="alert" className="library-error">{t(data.activation.error)}</div>}
 {tab === 'catalog' ? <div className="library-models">{models.map(model => {
          const job = model.job || {},
            working = ['downloading', 'verifying'].includes(job.state);
          return <article className="library-model" key={model.id}><div className="library-model-top"><div><div className="library-badges">{model.default && <span>{t("СТАНДАРТНЫЙ НАБОР")}</span>}{model.id === data.recommended && <span className="fit">{t("РЕКОМЕНДУЕМ ДЛЯ ПК")}</span>}{model.kind === 'image' && <span>{t("ИЗОБРАЖЕНИЯ")}</span>}</div><h3>{model.name}</h3><p>{t(model.quantization)} · {gb(model.total)}</p></div>{model.installed ? <Check size={20} className="library-ready" /> : <Download size={19} />}</div><p className={'fit-text ' + model.recommendation.level}>{t(model.recommendation.reason)}</p><div className="library-source"><a href={model.source.startsWith('https:') ? model.source : undefined} target="_blank" rel="noreferrer">{model.source.startsWith('https:') ? t("Источник и лицензия ↗") : t("Локальный импорт")}</a><span>{String(model.license)}</span></div>
 {(model.bytes > 0 || working) && !model.installed && <><div className="download-summary"><span>{gb(model.bytes)} / {gb(model.total)}{job.speed ? ' · ' + (job.speed / 1024 ** 2).toFixed(1) + t(" МБ/с") : ''}</span><strong>{model.percent}%</strong></div><div className="download-progress"><i style={{
                  width: model.percent + '%'
                }} /></div></>}
 {job.error && <p className="library-error">{t(job.error)}</p>}<div className="library-actions">{model.installed ? model.kind === 'image' ? <span>{t("Готово для кнопки «Создать изображение»")}</span> : <button className={data.active === model.id ? 'installed-button' : 'primary-button'} disabled={data.active === model.id && data.model_ready || data.activation?.state === 'loading' || !!busy} onClick={() => action('activate', {
                id: model.id
              })}>{data.active === model.id ? data.model_ready ? t("Активна") : t("Запустить модель") : t("Использовать модель")}<ChevronRight size={14} /></button> : working ? <button onClick={() => action('pause', {
                id: model.id
              })}><Pause size={14} />{job.state === 'verifying' ? t("Проверяем SHA256") : t("Приостановить")}</button> : <button className="primary-button" disabled={!!busy} onClick={() => action('download', {
                id: model.id
              })}><Download size={14} />{model.bytes ? t("Продолжить загрузку") : t("Скачать модель")}</button>}</div></article>;
        })}</div> : <div className="import-models"><section><h3>{t("GGUF с вашего диска")}</h3><p>{t("Укажите полный путь к готовому GGUF. Нужен исходный контекст от 64К. Приложение сохранит независимую копию в своей папке.")}</p><input aria-label={t("Путь к GGUF")} placeholder="E:\Models\model.gguf" value={path} onChange={e => setPath(e.target.value)} /><button className="primary-button" disabled={!path || !!busy} onClick={() => action('import', {
            path
          })}><FolderOpen size={15} />{t("Импортировать GGUF")}</button></section><section><h3>{t("Модель с Hugging Face")}</h3><p>{t("Нужен исходный контекст от 64К. Поддерживаются единые GGUF, совместимые с установленным llama.cpp. Лицензию и требования выбираемой модели нужно учитывать отдельно.")}</p><input aria-label={t("Репозиторий Hugging Face")} placeholder="owner/repository" value={repo} onChange={e => setRepo(e.target.value)} /><button disabled={!repo || !!busy} onClick={() => action('hf', {
            repo
          })}>{t("Показать файлы")}</button>{remote && <><select aria-label={t("Файл GGUF")} value={filename} onChange={e => setFilename(e.target.value)}>{remote.files.map(file => <option key={file.name} value={file.name}>{file.name} · {gb(file.bytes)}</option>)}</select><button className="primary-button" disabled={!filename || !!busy} onClick={() => action('hf-add', {
              repo: remote.repo,
              filename
            })}><Plus size={14} />{t("Добавить в каталог")}</button></>}</section></div>}
 {tab === 'import' && <section className="local-api-import"><h3>{t("Уже запущен локальный сервер?")}</h3><p>{t("Можно подключить OpenAI-совместимый API на этом ПК: llama.cpp, LM Studio или Ollama. Доступны только loopback-адреса.")}</p><div><input aria-label={t("Адрес локального API")} value={endpoint} onChange={e => setEndpoint(e.target.value)} /><input aria-label={t("Идентификатор локальной модели")} placeholder={t("Идентификатор из /v1/models")} value={externalModel} onChange={e => setExternalModel(e.target.value)} /><label>{t("Контекст сервера")}<input type="number" min="64000" aria-label={t("Контекст локального сервера")} value={externalContext} onChange={e => setExternalContext(Number(e.target.value))} /></label><button className="primary-button" disabled={!!busy || !externalModel || externalContext < 64000} onClick={() => action('connect', {
            url: endpoint,
            model: externalModel,
            context: externalContext
          })}>{t("Подключить")}</button></div></section>}
 <footer className="library-footer"><span>{t("Оценка по памяти предварительная: объём контекста и скорость зависят от оборудования.")}</span><span>{t("Загрузки можно продолжить после обрыва. Выход из окна не удаляет модели.")}</span></footer></section></div>;
}
