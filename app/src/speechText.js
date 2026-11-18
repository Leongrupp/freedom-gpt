export function speechText(value){
  return String(value||'').replace(/```[\s\S]*?```/g,'\n').replace(/`[^`\n]+`/g,' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g,' ').replace(/\[([^\]]+)\]\([^)]*\)/g,'$1')
    .replace(/https?:\/\/[^\s)\]>]+/g,' ').replace(/<[^>]+>/g,' ')
    .replace(/^\s{0,3}(?:#{1,6}\s*|>\s*|[-*+]\s+)/gm,'').replace(/[*_~]{1,3}/g,'')
    .replace(/\|/g,', ').replace(/[ \t]+/g,' ').replace(/\n{3,}/g,'\n\n').trim();
}
export function speechParts(value){
  let rest=speechText(value);const parts=[];
  if(rest.length>80000)throw new Error('Для озвучки выберите ответ короче 80 000 символов.');
  while(rest){
    const limit=parts.length?360:160;
    if(rest.length<=limit){parts.push(rest);break}
    const window=rest.slice(0,limit),ends=[...window.matchAll(/[.!?…]\s|\n/g)];
    let cut=ends.at(-1)?.index+1;
    if(!cut||cut<limit*.35)cut=window.lastIndexOf(' ');
    if(cut<limit*.35)cut=limit;
    parts.push(rest.slice(0,cut).trim());rest=rest.slice(cut).trim();
  }
  return parts.filter(Boolean);
}
export function isReadCommand(value){
  return /^(?:(?:прочитай|озвучь)(?:\s+(?:это|вслух|мне|пожалуйста|предыдущий|последний|свой|твой|ответ|сообщение|текст))*|read\s+(?:(?:it|this|aloud|your|the|last|previous|answer|response|please)\s*)+)[.!?\s]*$/i.test(String(value||'').trim());
}
