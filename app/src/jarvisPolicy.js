import {speechText} from './speechText.js';
export const defaults={modeVersion:2,assistant:'archi',humor:75,tarsRu:'ru-tars',alpoRu:'ru-eugene',microphone:'auto',recognitionLanguage:'ru',autoStart:true,showOnWake:true,portrait3d:true,portraitQuality:'auto',continuous:true,wake:true,language:'ru',style:'cinematic',stream:false,brief:true,hotkey:'Alt+J',ru:'ru-eugene',en:'en-amy',rate:1,volume:1};
export function preferences(raw={}){
 const saved=raw&&typeof raw==='object'&&!Array.isArray(raw)?raw:{};
 return {...defaults,...saved,...(saved.modeVersion===2?{}:{modeVersion:2,microphone:'auto',autoStart:true,showOnWake:true,portrait3d:true,portraitQuality:'auto',continuous:true,wake:true,language:'ru',style:'cinematic',stream:false}),assistant:['archi','tars','alpo'].includes(saved.assistant)?saved.assistant:'archi',humor:Number.isFinite(Number(saved.humor))?Math.round(Math.max(0,Math.min(100,Number(saved.humor)))):75};
}
export const assistantName=p=>({archi:'Арчи',tars:'ТАРС',alpo:'Альпо'}[p.assistant]||'Арчи');
export const assistantVoiceKey=p=>p.assistant==='tars'?'tarsRu':p.assistant==='alpo'?'alpoRu':'ru';
export const assistantVoice=p=>p[assistantVoiceKey(p)];
export const assistantOptions=p=>({assistant:p.assistant,humor:p.humor,language:p.language,brief:p.brief,style:p.style});
export function smallTalk(text,p,english=false){
 const v=text.toLowerCase().replace(/[,.!?—–]/g,' ').replace(/\s+/g,' ').trim();
 if(/^(?:(?:привет|здравствуй|здравствуйте) )?(?:как (?:ты|дела|твои дела|у тебя дела|жизнь)|как настроение)(?: у тебя)?$|^(?:hi |hello )?how are you$/.test(v))return english?'All good. How are you?':'Всё хорошо. А у тебя как дела?';
 if(/^(?:спасибо|благодарю|спасибо тебе|спасибо большое|thanks|thank you)$/.test(v))return english?'You are welcome.':'Всегда пожалуйста.';
 if(/^(?:всё хорошо|все хорошо|нормально|отлично|хорошо|all good|i am fine)$/.test(v))return english?'Glad to hear it. What shall we work on?':'Рад слышать. Чем займёмся?';
 if(/^(?:кто ты|как тебя зовут|who are you|what is your name)$/.test(v))return english?`I am ${p.assistant==='tars'?'TARS':p.assistant==='alpo'?'Alpo':'Archi'}, your voice assistant.`:'Я '+assistantName(p)+', твой голосовой помощник.';
 return null;
}
export function isVoiceQuestion(value){
 // An action remains a task even when phrased as a polite question.
 if(/^how (?:do|does|can|should|to)\b/i.test(value))return true;
 if(/(?:^|[\s,;])(?:создай|сделай|удали|установи|запусти|открой|измени|исправь|скачай|отправь|найди|проверь|напиши|create|delete|install|run|open|change|fix|download|send|find|write)(?=$|[\s,.?!:;])/i.test(value))return false;
 return /^(?:что|почему|зачем|когда|где|кто|какой|какая|какие|сколько|как|объясни|расскажи|what|why|when|where|who|how|explain|tell me)(?:\s|$)/i.test(value);
}
export function hoverRemark(p,english=false){return english?'Hey, that tickles. Shall we get back to work?':p.assistant==='tars'?'Тактильный контакт зарегистрирован. Может, всё-таки поработаем?':'Эй, ты чего меня трогаешь? Давай лучше поработаем.'}
function humorNumber(text){
 const value=text.toLowerCase().trim();if(/^\d{1,3}$/.test(value))return Number(value);
 const units=['ноль','один','два','три','четыре','пять','шесть','семь','восемь','девять','десять','одиннадцать','двенадцать','тринадцать','четырнадцать','пятнадцать','шестнадцать','семнадцать','восемнадцать','девятнадцать'];
 const tens={двадцать:20,тридцать:30,сорок:40,пятьдесят:50,шестьдесят:60,семьдесят:70,восемьдесят:80,девяносто:90,сто:100};
 if(units.includes(value))return units.indexOf(value);if(value in tens)return tens[value];
 if(value==='нуль'||value==='минимум')return 0;if(value==='максимум')return 100;
 const parts=value.split(/\s+/);if(parts.length===2&&tens[parts[0]]>=20&&tens[parts[0]]<=90&&units.indexOf(parts[1])>0&&units.indexOf(parts[1])<10)return tens[parts[0]]+units.indexOf(parts[1]);return null;
}
export function greeting(p,english=false){
 if(p.assistant==='alpo')return english?'Alpo here. How can I help?':'Альпо на связи. Чем займёмся?';
 if(p.assistant!=='tars')return english?'Archi here. How can I help?':'Арчи на связи. Чем займёмся?';
 if(english)return p.humor===0?'TARS online. Ready for your task.':`TARS online. Humor at ${p.humor} percent. Ready for your task.`;
 if(p.humor===0)return 'Тарс на связи. Готов к работе.';
 if(p.humor<50)return 'Тарс на связи. Слушаю задачу.';
 if(p.humor<75)return 'Тарс на связи. Задача ваша, расчёты мои.';
 return `Тарс на связи. Юмор — ${p.humor} процентов. Остальное — работа.`;
}
export function command(text,{wake=false}={}){
 const raw=String(text||'').trim();
 // Whisper may prefix a spoken turn with dialogue punctuation or repeat the name.
 // Keep old wake names as compatibility aliases for already saved recordings.
 const address=/^(?:[\s,!.?:;—–\-«»"“”]*(?:эй[ ,!]*|hey[ ,!]*)?(?:арч(?:ик|ий|и|а|е)|альпо|алпо|alpo|тарс|тарз|тарас|tars|archie|archi|джарвис|джервис|жарвис|jarvis)(?=[\s,!?:;.—–\-«»"“”]|$)[\s,!?:;.—–\-«»"“”]*)+/i;
 const called=address.test(raw),assistant=called?(/тарс|тарз|тарас|tars/i.test(raw.match(address)?.[0]||'')?'tars':/альпо|алпо|alpo/i.test(raw.match(address)?.[0]||'')?'alpo':'archi'):null;
 if(wake&&!called)return {kind:'ignore',raw,called,assistant};
 const value=raw.replace(address,'').trim().replace(/[.!?]+$/,'');
 if(!value)return {kind:called?'wake':'clarify',raw,called,assistant};
 if(smallTalk(value,{assistant:assistant||'archi'}))return {kind:'smalltalk',value,raw,called,assistant};
 if(/^(?:создай|открой|начни|начать|открыть|создать) (?:пожалуйста,? )?новый чат$|^новый чат$|^(?:create|open|start)(?: a)? new chat$/i.test(value))return {kind:'new-chat',raw,called,assistant};
 if(/^(?:привет|здравствуй(?:те)?|ты (?:тут|здесь|на связи)|hello|hi|are you there)(?:[\s,!?.]+(?:арч(?:ик|ий|и|а|е)|альпо|алпо|alpo|тарс|тарз|тарас|tars|archie|archi|джарвис|джервис|жарвис|jarvis))*$/i.test(value))return {kind:'greet',raw,called,assistant};
 const humor=value.match(/^(?:(?:установи(?:л)?|поставь|сделай)\s+)?(?:уровень\s+)?юмор(?:а)?(?:\s+(?:на\s+)?(.*))?$/i);
 if(humor){const number=humorNumber((humor[1]||'').replace(/\s*(?:%|процент(?:ов|а)?)$/i,''));return {kind:number!==null&&number<=100?'humor':'humor-invalid',value:number,raw,called,assistant}}
 if(/^(?:выключи|отключи) юмор$/i.test(value))return {kind:'humor',value:0,raw,called,assistant};
 if(/^(?:останови(?:сь| работу| задачу| агента)?|стоп задачу|stop(?: the)? (?:task|agent|work))$/i.test(value))return {kind:'stop-task',raw,called,assistant};
 if(/^(?:замолчи|тише|стоп|останови (?:озвучку|голос)|stop(?: speaking)?|be quiet|mute)$/i.test(value))return {kind:'stop-speech',raw,called,assistant};
 if(/^(?:повтори(?: ответ)?|прочитай (?:ответ|предыдущий ответ)|repeat(?: (?:the |your )?answer)?)$/i.test(value))return {kind:'repeat',raw,called,assistant};
 if(/^(?:говори короче|короче|be brief|shorter answers)$/i.test(value))return {kind:'brief',raw,called,assistant};
 if(/^(?:покажи[,]? что ты (?:сейчас )?делаешь|статус|what are you doing|show status)$/i.test(value))return {kind:'status',raw,called,assistant};
 if(/^(?:скорректируй|поправка|уточнение|корректировка|actually|correction|change the current task)\b/i.test(value)||/^(?:скорректируй|поправка|уточнение|корректировка)[\s,:]/i.test(value))return {kind:'steer',raw,called,assistant};
 if(value.length<3||/^\[[^\]]+\]$/.test(value))return {kind:'clarify',raw,called,assistant};
 return {kind:isVoiceQuestion(value)?'question':'task',raw,called,assistant};
}
export function spokenSummary(text,brief=true){
 const clean=speechText(text);if(!brief)return clean;
 if(clean.length<=600)return clean;
 const part=clean.slice(0,520),end=[...part.matchAll(/[.!?…](?:\s|$)/g)].at(-1)?.index;
 return (end>60?part.slice(0,end+1):part.slice(0,part.lastIndexOf(' ')))+' '+(/[а-яё]/i.test(clean)?'Подробности оставил в чате.':'Details are in the chat.');
}
export function soundsLikeEcho(text,spoken){
 const words=s=>String(s||'').toLowerCase().match(/[\p{L}\p{N}]+/gu)||[];
 const a=words(text),b=words(spoken);if(!a.length||!b.length)return false;
 const normalized=b.join(' '),sample=a.join(' ');
 if(a.length===1&&b.includes(a[0]))return true;
 if(a.length>=2&&normalized.includes(sample))return true;
 if(a.length<4)return false;
 const pairs=new Set(b.slice(1).map((v,i)=>b[i]+' '+v));
 return a.slice(1).filter((v,i)=>pairs.has(a[i]+' '+v)).length/(a.length-1)>.8;
}
export function completedSentences(text){
 // Streaming code/tool payloads are never spoken as prose.
 const beforeCode=String(text||'').split('```')[0];const clean=speechText(beforeCode);
 const end=[...clean.matchAll(/[.!?…](?:\s|$)/g)].at(-1)?.index;
 return end===undefined?'':clean.slice(0,end+1);
}
export function pronounce(text,language='auto'){
 if(language==='en'||language==='auto'&&!/[а-яё]/i.test(text))return text;
 const words={python:'Пайтон',github:'Гитхаб',javascript:'Джаваскрипт',typescript:'Тайпскрипт',freedom:'Фридом',jarvis:'Арчи',archi:'Арчи',archie:'Арчи',tars:'Тарс',alpo:'Альпо',api:'эй пи ай',html:'эйч ти эм эл',css:'си эс эс'};
 return text.replace(/\b(Python|GitHub|JavaScript|TypeScript|Freedom|Jarvis|Archi|Archie|TARS|Alpo|API|HTML|CSS)\b/gi,word=>words[word.toLowerCase()]);
}
