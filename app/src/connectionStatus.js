import {useEffect, useState} from 'react';

// Read the existing video API while an older running server finishes a job.
// This lets the updated UI show the right state without restarting its worker.
export function useVideoActivity(enabled) {
  const [activity, setActivity] = useState(null);
  useEffect(() => {
    if (!enabled) {setActivity(null); return;}
    let stopped = false, timer, controller;
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch('/api/video', {cache: 'no-store', signal: controller.signal});
        if (!response.ok) return;
        const {current} = await response.json();
        if (!stopped) setActivity(current && ['queued', 'loading', 'generating', 'restoring'].includes(current.state)
          ? {kind: 'video', state: current.state, phase: current.phase, progress: current.progress} : null);
      } catch {} finally {
        clearTimeout(timeout);
        if (!stopped) timer = setTimeout(poll, 4000);
      }
    }
    poll();
    return () => {stopped = true; clearTimeout(timer); controller?.abort();};
  }, [enabled]);
  return enabled ? activity : null;
}

export function connectionStatus(connected, metrics = {}, cloudRoute = null) {
  if (!connected || !metrics.gateway_ready) return {ready: false, label: 'Подключение', hint: ''};
  if (cloudRoute) return {ready: Boolean(cloudRoute.available), label: cloudRoute.paid ? 'Платный API' : 'Через API', hint: ''};
  if (metrics.model_ready) return {ready: true, label: 'Локально', hint: ''};
  const activity = metrics.local_model_activity;
  if (activity?.state === 'restoring') return {
    ready: false, label: 'Возвращаю модель',
    hint: 'Генерация завершена. Загружаем модель чата обратно в видеопамять.'
  };
  if (activity?.kind === 'video' && activity.phase === 'decoding') return {
    ready: false, label: 'Собираю кадры',
    hint: 'Модель чата временно освобождает видеопамять. После завершения она подключится автоматически.'
  };
  const labels = {video: 'Создаю видео', music: 'Создаю музыку', camera: 'Камера включена', image: 'Создаю изображение'};
  if (labels[activity?.kind]) return {
    ready: false, label: labels[activity.kind],
    hint: 'Модель чата временно освобождает видеопамять. После завершения она подключится автоматически.'
  };
  return {ready: false, label: 'Подключение', hint: ''};
}
