// Read actual rendered pages in the same isolated browser shown beside the chat.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

function relevant(results,query){
 const aliases=/beget|бегет/i.test(query)?/beget|бегет/i:/\bozon\b|озон/i.test(query)?/ozon|озон/i:/wildberries|вайлдберриз/i.test(query)?/wildberries|вайлдберриз/i:null;
 return aliases?results.filter(row=>aliases.test(row.title+' '+row.url+' '+row.description)):results;
}
function parseFeed(xml,limit){
 return new Promise((resolve,reject)=>{
  const root=process.cwd(),bundled=path.join(root,'runtime/python/python.exe'),unix=path.join(root,'runtime/python/bin/python3');
  const python=process.env.FREEDOM_PYTHON||(fs.existsSync(bundled)?bundled:fs.existsSync(unix)?unix:'python3');
  const child=spawn(python,['-B','-s',path.join(root,'scripts/parse-search-feed.py'),String(limit)],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8',TEMP:path.join(root,'.tmp'),TMP:path.join(root,'.tmp')}});
  let output='',error='';const timer=setTimeout(()=>{child.kill();reject(Error('RSS parser timeout'))},3000);
  child.stdout.setEncoding('utf8');child.stdout.on('data',chunk=>{output+=chunk});child.stderr.setEncoding('utf8');child.stderr.on('data',chunk=>{error+=chunk});
  child.on('error',e=>{clearTimeout(timer);reject(e)});child.on('close',code=>{clearTimeout(timer);if(code)return reject(Error('RSS could not be read'));try{resolve(JSON.parse(output))}catch(e){reject(e)}});
  child.stdin.on('error',()=>{});child.stdin.end(xml);
 });
}
export async function openPage(page,url,options={}){
 const tries=options.attempts===1?1:2,timeout=Math.max(1000,Math.min(12000,Number(options.timeout)||12000));
 for(let attempt=0;attempt<tries;attempt++){
  try{const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout});return {status:response?.status()||200,attempts:attempt+1}}
  catch(error){
   const transient=error.name==='TimeoutError'||/net::ERR_(?:CONNECTION|NETWORK|TIMED_OUT|NAME_NOT_RESOLVED|EMPTY_RESPONSE|HTTP2_PROTOCOL_ERROR|INTERNET_DISCONNECTED)/.test(error.message||'');
   if(attempt===tries-1||!transient||page.isClosed())throw error;
  }
 }
}

export async function readPage(page,maxChars=18000){
 return page.evaluate(limit=>{
  const title=document.title||'',url=location.href;
  const content=(document.body?.innerText||'').trim();
  const captcha=/\/((?:show)?captcha|challenge|sorry)(?:\/|\?|$)/i.test(location.pathname)||
   /^(captcha|just a moment|attention required|verify (?:you are|that you)|проверка браузера|вы не робот|подтвердите,? что вы не робот)/i.test(title.trim())||
   (!!document.querySelector('iframe[src*="challenges.cloudflare.com"],form[action*="showcaptcha"],form[action*="anomaly"],#challenge-running,#anomaly-modal')&&content.length<6000);
  const consent=location.hostname==='consent.google.com';
  const login=!!document.querySelector('input[type="password"]')&&/login|signin|sign-in|auth/i.test(location.pathname);
  const challenge=captcha||consent||login,access_gate=consent?'consent':login?'login':captcha?'captcha':null;
  const links=[...document.querySelectorAll('a[href]')].map(a=>({title:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,240),url:a.href})).filter(a=>/^https?:/i.test(a.url)&&a.title).slice(0,80);
  return {url,title,content:content.slice(0,limit),truncated:content.length>limit,challenge,access_gate,links};
 },Math.max(1000,Math.min(50000,Number(maxChars)||18000)));
}

function engineURL(engine,query){
 return engine==='bing'?'https://www.bing.com/search?q='+encodeURIComponent(query):'https://html.duckduckgo.com/html/?q='+encodeURIComponent(query);
}

async function selectedSearch(page,query,limit,engine,reuse){
 const urls={google:'https://www.google.com/search?q=',yandex:'https://yandex.ru/search/?text=',bing:'https://www.bing.com/search?q=',duckduckgo:'https://html.duckduckgo.com/html/?q='};
 const selectors={google:'#search a:has(h3), #rso a:has(h3)',yandex:'.serp-item h2 a, .serp-item a.OrganicTitle-Link, .OrganicTitle a',bing:'li.b_algo h2 a',duckduckgo:'a.result__a'};
 const result={success:false,engine,query,results:[],attempts:[]};
 try{
  const current=new URL(page.url());const sameHost=current.hostname===new URL(urls[engine]).hostname;
  const sameQuery=(current.searchParams.get(engine==='yandex'?'text':'q')||'')===query;
  let reading;
  if(reuse&&sameHost)reading=await readPage(page,8000);
  if(!(reuse&&sameHost&&(sameQuery||reading?.challenge))){
   const response=await page.goto(urls[engine]+encodeURIComponent(query),{waitUntil:'domcontentloaded',timeout:12000});
   if(response?.status()>=400){result.attempts.push({engine,status:response.status(),error:'http_'+response.status()});return {...result,error:'Поисковая система пока недоступна. Попробуйте позже.'}}
  }
  await page.locator(selectors[engine]).first().waitFor({state:'attached',timeout:1500}).catch(()=>{});
  reading=await readPage(page,8000);
  if(reading.challenge)return {...result,requires_human:true,challenge_url:reading.url,page:reading,error:'Поисковик запросил проверку или вход. Подтвердите её в открытом окне выбранного браузера, затем повторите отправку задания.'};
  const rows=await page.locator(selectors[engine]).evaluateAll((anchors,maximum)=>{
   const seen=new Set();return anchors.map(a=>{
    let url=a.href;try{const u=new URL(url);if(u.hostname.endsWith('google.com')&&u.pathname==='/url')url=u.searchParams.get('q')||u.searchParams.get('url')||url;if(u.hostname.endsWith('duckduckgo.com')&&u.searchParams.has('uddg'))url=u.searchParams.get('uddg')}catch{}
    const block=a.closest('.serp-item,li.b_algo,.result,.MjjYud')||a.parentElement?.parentElement;
    return {title:(a.querySelector('h3')?.innerText||a.innerText||a.textContent||'').trim(),url,description:(block?.innerText||'').trim().slice(0,1000)};
   }).filter(row=>row.title&&/^https?:/.test(row.url)&&!seen.has(row.url)&&seen.add(row.url)).slice(0,maximum).map((row,i)=>({...row,position:i+1}));
  },Math.max(1,Math.min(10,limit)));
  const results=relevant(rows,query);return {...result,success:!!results.length,results,page:reading,error:results.length?undefined:'На открытой странице пока не найдены ссылки выдачи. Проверьте страницу или измените запрос.'};
 }catch(error){return {...result,error:error.name==='TimeoutError'?'Страница поиска не успела загрузиться. Проверьте открытое окно браузера и повторите запрос.':String(error.message).split('\n')[0].slice(0,220)}}
}

export async function searchPage(page,query,limit=5,options={}){
 if(options.engine&&options.engine!=='auto'){
  if(!['google','yandex','bing','duckduckgo'].includes(options.engine))throw Error('Неизвестная поисковая система.');
  return selectedSearch(page,query,limit,options.engine,options.reuse);
 }
 const attempts=[];let challengeURL='';
 for(const engine of ['bing','duckduckgo']){
  try{
   const response=await page.goto(engineURL(engine,query),{waitUntil:'domcontentloaded',timeout:6500});
   const status=response?.status()||200;
   if(status>=400){attempts.push({engine,error:'http_'+status,status});continue}
   const selector=engine==='bing'?'li.b_algo h2 a':'a.result__a';
   await page.locator(selector).first().waitFor({state:'attached',timeout:1200}).catch(()=>{});
   const reading=await readPage(page,8000);
   if(reading.challenge){challengeURL=reading.url;attempts.push({engine,error:'captcha',status});continue}
   const results=await page.locator(selector).evaluateAll((anchors,max)=>anchors.map(a=>{
    let url=a.href;
    try{const parsed=new URL(url);if(parsed.hostname.endsWith('duckduckgo.com')&&parsed.searchParams.has('uddg'))url=parsed.searchParams.get('uddg');else if(parsed.hostname.endsWith('bing.com')&&parsed.pathname==='/ck/a'){const encoded=parsed.searchParams.get('u');if(encoded?.startsWith('a1')){let data=encoded.slice(2).replaceAll('-','+').replaceAll('_','/');url=atob(data)}}}catch{}
    const block=a.closest('li.b_algo,.result')||a.parentElement;
    const snippet=block?.querySelector('.b_caption p,.result__snippet');
    return {title:(a.innerText?.trim()||a.textContent||'').trim(),url,description:(snippet?.innerText?.trim()||snippet?.textContent||'').trim().slice(0,1400)};
   }).filter(r=>r.title&&(r.url.startsWith('https://')||r.url.startsWith('http://'))).slice(0,max).map((r,i)=>({...r,position:i+1})),Math.min(10,Math.max(1,Number(limit)||5)));
   const matching=relevant(results,query);
   if(matching.length)return {success:true,engine,query,results:matching,attempts,page:reading};
   attempts.push({engine,error:'no_results',status,matched:await page.locator(selector).count(),title:reading.title});
  }catch(error){attempts.push({engine,error:error.name==='TimeoutError'?'timeout':String(error.message).split('\n')[0].slice(0,180)})}
 }
 // Public RSS is an ordinary syndication format: keep its actual page visible,
 // without changing identity, cookies, proxy or CAPTCHA controls.
 const feeds=/(?:новост|взлом|сбой|хостинг|произош|случил|кибератак|beget|бегет|news|hack|outage|incident|cyber|breach)/i.test(query)?['google-news','bing-rss']:['bing-rss'];
 for(const feed of feeds){try{
  const url=feed==='google-news'?'https://news.google.com/rss/search?hl=ru&gl=RU&ceid=RU:ru&q='+encodeURIComponent(query):'https://www.bing.com/search?format=rss&q='+encodeURIComponent(query);
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:6500});
  if(response?.status()>=400)attempts.push({engine:feed,error:'http_'+response.status(),status:response.status()});
  else{
   const xml=await response.text();
   const results=relevant(await parseFeed(xml,Math.min(10,Math.max(1,Number(limit)||5))),query);
   if(results.length)return {success:true,engine:feed,query,results,attempts,page:await readPage(page,8000)};
   attempts.push({engine:feed,error:'no_results'});
  }
 }catch(error){attempts.push({engine:feed,error:error.name==='TimeoutError'?'timeout':String(error.message).split('\n')[0].slice(0,180)})}}
 const blocked=attempts.some(a=>a.error==='captcha');
 if(blocked&&challengeURL)await page.goto(challengeURL,{waitUntil:'domcontentloaded',timeout:5000}).catch(()=>{});
 return {success:false,query,results:[],attempts,requires_human:blocked,challenge_url:challengeURL||null,error:blocked?'Поисковик запросил проверку «Я не робот». Откройте страницу во встроенном браузере и подтвердите её вручную.':'Поисковые системы не вернули доступных результатов. Измените запрос или откройте известный адрес источника.'};
}
