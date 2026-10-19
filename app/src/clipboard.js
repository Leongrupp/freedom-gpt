import { t } from './i18n.js';
export async function copyText(text, {
  clipboard = globalThis.navigator?.clipboard,
  document = globalThis.document,
  timeoutMs = 750
} = {}) {
  const value = String(text ?? '');
  let timer;
  try {
    if (clipboard?.writeText) {
      await Promise.race([clipboard.writeText(value), new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('Clipboard timeout')), timeoutMs);
      })]);
      return;
    }
  } catch {/* Denied or stalled clipboard access uses the synchronous fallback. */} finally {
    clearTimeout(timer);
  }
  if (!document?.body) throw new Error(t("Буфер обмена недоступен. Выделите текст и нажмите Ctrl+C."));
  const previous = document.activeElement,
    selection = document.getSelection?.();
  const ranges = selection ? Array.from({
    length: selection.rangeCount
  }, (_, i) => selection.getRangeAt(i).cloneRange()) : [];
  const field = document.createElement('textarea');
  field.value = value;
  field.readOnly = true;
  field.setAttribute('aria-hidden', 'true');
  field.style.cssText = 'position:fixed;left:-10000px;top:0;opacity:0';
  document.body.appendChild(field);
  try {
    field.focus();
    field.select();
    if (!document.execCommand?.('copy')) throw new Error(t("Выделите текст и нажмите Ctrl+C."));
  } finally {
    field.remove();
    previous?.focus?.({
      preventScroll: true
    });
    if (selection) {
      selection.removeAllRanges();
      ranges.forEach(range => selection.addRange(range));
    }
  }
}
