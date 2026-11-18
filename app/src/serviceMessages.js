// Translate complete, known runtime notices only. Ordinary answers, quotations,
// code blocks and tool output remain the model's original text.
const compression='Context compression timed out without reducing this conversation. No messages were dropped. Start a fresh session with /new, or check auxiliary.compression before retrying /compress.';
const incomplete='This turn did not complete. Some actions may already have run; verify their effects before resending.';
export function serviceMessage(text,locale='ru'){
  const raw=String(text),value=raw.trim();
  if(locale==='en')return raw;
  if(value===compression)return locale==='zh'?'对话压缩超时，未能缩短上下文。没有删除任何消息。请创建新聊天或分支，或检查压缩设置后重试。':'Сжатие истории превысило время ожидания и не уменьшило контекст. Ни одно сообщение не удалено. Можно создать новый чат или ветку с этой перепиской либо проверить настройки сжатия перед повторной попыткой.';
  if(value===incomplete)return locale==='zh'?'本次请求未完成。部分操作可能已执行；再次发送前请检查结果。':'Этот запрос не завершён. Некоторые действия могли уже выполниться. Перед повторной отправкой проверьте их результаты.';
  const waiting=value.match(/^Operation interrupted: waiting for model response \((\d+(?:\.\d+)?)s elapsed\)\.$/);
  if(waiting)return locale==='zh'?`操作已中断：正在等待模型回复（已过去 ${waiting[1]} 秒）。`:`Выполнение остановлено во время ожидания ответа модели (${waiting[1].replace('.',',')} с). Это длительность ожидания, а не лимит работы.`;
  if(value==='Operation interrupted.')return locale==='zh'?'操作已中断。':'Операция прервана.';
  return raw;
}
export function userMessage(text){
  return String(text).replace(/\n\n\[Freedom: reply language\]\n[^]*?\n\[\/Freedom: reply language\]$/,'');
}
