import { t } from './i18n.js';
export const CONNECTION_ERROR = t("Нет связи с локальной панелью. Переподключаемся; текст сохранён.");
export class ApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'ApiError';
    Object.assign(this, details);
  }
}
// Retry reads only. A lost POST response must never silently repeat an agent task.
export function createApi({
  fetchFn = (...args) => fetch(...args),
  sleep = ms => new Promise(r => setTimeout(r, ms)),
  onState = () => {},
  timeoutMs = 45000
} = {}) {
  let token = '',
    refreshing = null;
  async function request(path, options = {}, mayRefresh = true) {
    const method = (options.method || 'GET').toUpperCase(),
      read = ['GET', 'HEAD'].includes(method);
    for (let attempt = 0; attempt < (read ? 3 : 1); attempt++) {
      const controller = new AbortController(),
        timer = setTimeout(() => controller.abort(), timeoutMs);
      let response, data;
      try {
        const headers = {
          ...(options.body instanceof FormData ? {} : {
            'Content-Type': 'application/json'
          }),
          ...options.headers
        };
        if (token) headers['X-Freedom-Token'] = token;
        response = await fetchFn('/api' + path, {
          ...options,
          method,
          headers,
          cache: 'no-store',
          signal: controller.signal
        });
        try {
          data = await response.json();
        } catch (error) {
          if (!(error instanceof SyntaxError)) throw error;
          throw new ApiError(t("Сервер вернул неполный ответ. Проверьте соединение."), {
            code: 'bad_response',
            status: response.status
          });
        }
      } catch (error) {
        if (error instanceof ApiError) throw error;
        onState('reconnecting');
        if (read && attempt < 2) {
          await sleep(350 * (attempt + 1));
          continue;
        }
        throw new ApiError(CONNECTION_ERROR, {
          code: 'network',
          uncertain: !read,
          cause: error
        });
      } finally {
        clearTimeout(timer);
      }
      onState('ready');
      if (response.status === 403 && data.code === 'session_expired' && mayRefresh) {
        if (!refreshing) refreshing = request('/bootstrap', {}, false).finally(() => {
          refreshing = null;
        });
        await refreshing;
        return request(path, options, false);
      }
      if (!response.ok) throw new ApiError(t(data.error) || t("Не удалось выполнить запрос"), {
        code: data.code,
        status: response.status
      });
      if (path === '/bootstrap' && data.token) token = data.token;
      return data;
    }
  }
  return {
    request,
    setToken: value => {
      token = value;
    }
  };
}
const client = createApi({
  onState: state => {
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('freedom-transport', {
      detail: state
    }));
  }
});
export const api = client.request;
