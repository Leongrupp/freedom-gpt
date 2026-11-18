import {chromium} from 'playwright';
import readline from 'node:readline';
import path from 'node:path';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {selectedBrowser} from './preview-launch.mjs';
import {openPage,readPage,searchPage} from './browser-research.mjs';

const root=process.cwd(),cache=path.join(root,'.cache','preview-frames'),output=path.join(root,'output','browser-preview');
await fs.mkdir(cache,{recursive:true});await fs.mkdir(output,{recursive:true});
const pages=new Map(),epoch=crypto.randomUUID();const browsers=new Map(),warmPages=new Map();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const emit=(sid,result,open=false)=>process.stdout.write(JSON.stringify({event:'preview.changed',sid,result,open})+'\n');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex').slice(0,24);
async function getBrowser(browserId='builtin'){
 const running=browsers.get(browserId);if(running?.browser()?.isConnected())return running;
 const profile=path.resolve(root,browserId==='builtin'?(process.env.FREEDOM_BROWSER_PROFILE||'data/browser/profile'):'data/browser/profiles/'+browserId);
 if(path.relative(root,profile).startsWith('..')||path.isAbsolute(path.relative(root,profile)))throw Error('Профиль браузера должен храниться в папке Freedom.');
 await fs.mkdir(profile,{recursive:true});
 const browser=await chromium.launchPersistentContext(profile,{executablePath:await selectedBrowser(chromium,browserId),headless:browserId==='builtin',chromiumSandbox:browserId!=='builtin',viewport:{width:1280,height:800},deviceScaleFactor:1,locale:'ru-RU',acceptDownloads:false,args:[...(browserId==='builtin'?['--disable-gpu']:[]),'--disable-background-networking','--disable-sync','--no-first-run','--restore-last-session','--disk-cache-dir='+path.join(root,'.cache','preview-browser',browserId,'disk'),'--crash-dumps-dir='+path.join(root,'.cache','preview-browser',browserId,'crashes')]});
 const warmPage=browserId==='builtin'?await browser.newPage():browser.pages().find(p=>p.url()==='about:blank')||await browser.newPage();if(browserId==='builtin')for(const old of browser.pages())if(old!==warmPage)await old.close();warmPages.set(browserId,warmPage);browsers.set(browserId,browser);return browser;
}
async function pageFor(sid,create=false,browserId='builtin'){
 let item=pages.get(sid);
 if(item&&!item.page.isClosed()){if(!create||item.browserId===browserId){item.used=Date.now();return item}await Promise.all([...item.owned].map(p=>p.close()));pages.delete(sid)}
 if(!create)return null;
 if(pages.size>=4){const[old,entry]=[...pages].sort((a,b)=>a[1].used-b[1].used)[0];await Promise.all([...entry.owned].map(page=>page.close()));pages.delete(old);process.stdout.write(JSON.stringify({event:'preview.closed',sid:old,reason:'evicted'})+'\n')}
 const context=await getBrowser(browserId);const page=warmPages.get(browserId)||await context.newPage();warmPages.delete(browserId);
 item={context,page,browserId,owned:new Set(),used:Date.now(),width:1280,height:800,revision:0,errors:[],console_errors:[],cursor:null,source:'user',action:'status',capture:null};pages.set(sid,item);
 wire(page,item);return item;
}
function wire(page,item){item.owned.add(page);page.on('popup',popup=>{item.page=popup;wire(popup,item)});page.on('framenavigated',frame=>{if(frame===page.mainFrame())item.visit_id=crypto.randomUUID()});page.on('response',response=>{try{if(response.request().isNavigationRequest()&&response.frame()===page.mainFrame())item.http_status=response.status()}catch{}});page.on('pageerror',error=>{item.errors.push(String(error.message).slice(0,400));item.errors=item.errors.slice(-12)});page.on('console',message=>{if(message.type()==='error'){item.console_errors.push(message.text().slice(0,400));item.console_errors=item.console_errors.slice(-12)}});page.on('dialog',dialog=>dialog.dismiss().catch(()=>{}))}
async function state(sid,item,frame=false){
 if(!item)return {state:'idle',url:'',title:'',width:1280,height:800,epoch,updated_at:Date.now()};
 const page=item.page;
 if(frame){
  if(!item.capture)item.capture=(async()=>{const target=path.join(cache,hash(sid)+'.jpg');const bytes=await page.screenshot({type:'jpeg',quality:72,timeout:12000});await fs.writeFile(target+'.new',bytes);await fs.rename(target+'.new',target);item.revision++})().finally(()=>item.capture=null);
  await item.capture;
 }
 return {state:'ready',url:page.url(),title:await page.title().catch(()=>''),width:item.width,height:item.height,revision:item.revision,errors:item.errors,console_errors:item.console_errors,http_status:item.http_status,epoch,updated_at:Date.now(),visit_id:item.visit_id,profile:'persistent',browser:item.browserId,browser_name:({builtin:'Встроенный браузер',chrome:'Google Chrome',yandex:'Яндекс Браузер'})[item.browserId],external:item.browserId!=='builtin',cursor:item.cursor,source:item.source,action:item.action};
}
async function movePointer(sid,item,x,y){
 const start=item.cursor||{x:Math.min(100,item.width/2),y:Math.min(100,item.height/2)};
 const end={x:Math.max(0,Math.min(item.width,x)),y:Math.max(0,Math.min(item.height,y))};
 for(let i=1;i<=8;i++){
  const t=i/8,eased=t*t*(3-2*t);item.cursor={x:start.x+(end.x-start.x)*eased,y:start.y+(end.y-start.y)*eased,visible:true,down:false};
  await item.page.mouse.move(item.cursor.x,item.cursor.y);
  emit(sid,await state(sid,item),item.source==='agent');await pause(25);
 }
}
async function pointAt(sid,item,locator){
 await locator.scrollIntoViewIfNeeded({timeout:8000});const box=await locator.boundingBox();
 if(box)await movePointer(sid,item,box.x+box.width/2,box.y+box.height/2);
}
async function observedType(page,text){
 const part=text.slice(0,160);await page.keyboard.type(part,{delay:24});
 if(text.length>part.length)await page.keyboard.insertText(text.slice(part.length));
}
async function inspect(page){
 return page.evaluate(()=>{
  document.querySelectorAll('[data-freedom-preview]').forEach(e=>e.removeAttribute('data-freedom-preview'));
  const controls=[...document.querySelectorAll('a,button,input,textarea,select,[role="button"],[contenteditable="true"]')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height}).slice(0,70);
  const text=document.body?.innerText||'';
  return {text:text.slice(0,11000),layout:{text_chars:text.trim().length,interactive_count:controls.length,media_count:document.querySelectorAll('canvas,img,video,svg').length,horizontal_overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth)},elements:controls.map((e,i)=>{const ref='p'+(i+1);e.setAttribute('data-freedom-preview',ref);return {ref,tag:e.tagName.toLowerCase(),label:(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.getAttribute('name')||'').slice(0,130),type:e.getAttribute('type')}})};
 });
}
async function command(data){
 const {sid,action}=data;
 if(action==='close'){const item=pages.get(sid);if(item)await Promise.all([...item.owned].map(page=>page.close()));pages.delete(sid);return {state:'idle'}}
 if(action==='adopt'){const item=pages.get(data.from);if(item&&!pages.has(sid)){pages.delete(data.from);pages.set(sid,item)}return state(sid,pages.get(sid),true)}
 let item=await pageFor(sid,['open','search'].includes(action),data.browser||'builtin');
 if(!item){if(action==='status')return state(sid,null);throw Error('Сначала откройте сайт в панели просмотра.')}
 let page=item.page;if(action!=='status'){item.source=data.source==='agent'?'agent':'user';item.action=action}
 let updating=false;
 const stream=setInterval(async()=>{if(updating||!pages.has(sid))return;updating=true;try{emit(sid,await state(sid,item,true),item.source==='agent')}catch{}finally{updating=false}},260);
 try{
 if(['open','reload','back','forward'].includes(action)){item.errors=[];item.console_errors=[]}
 if(item.source==='agent')emit(sid,await state(sid,item),true);
 switch(action){
  case 'open':{const navigation=await openPage(page,data.url,{timeout:data.navigation_timeout,attempts:data.navigation_attempts});item.http_status=navigation.status;item.navigation_attempts=navigation.attempts;break;}
  case 'search':{const engine=data.search_engine||'auto';item.search=await searchPage(page,data.query,data.limit,{engine,reuse:item.lastQuery===data.query&&item.lastEngine===engine});item.lastQuery=data.query;item.lastEngine=engine;break;}
  case 'read':break;
  case 'focus':await page.bringToFront();break;
  case 'login_fill':{
   if(data.source!=='credential-vault')throw Error('Заполнение входа доступно только через кнопку сохранённых паролей.');
   await page.evaluate(({origin,username,password})=>{
    if(location.origin!==origin)throw Error('Сайт изменился. Откройте сохранённый вход заново.');
    const visible=e=>!!e.getClientRects().length&&!e.disabled;
    const secret=[...document.querySelectorAll('input[type="password"]')].find(visible);
    if(!secret)throw Error('На этой странице не найдена форма с паролем.');
    const form=secret.form||document;
    const inputs=[...form.querySelectorAll('input')].filter(e=>visible(e)&&e!==secret);
    const login=inputs.find(e=>e.autocomplete==='username')||inputs.find(e=>e.type==='email')||inputs.filter(e=>e.type==='text'||e.type==='tel').at(-1);
    const set=(e,value)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))};
    if(login)set(login,username);set(secret,password);
   },{origin:data.origin,username:data.username,password:data.password});
   break;
  }
  case 'reload':{const response=await page.reload({waitUntil:'domcontentloaded',timeout:25000});item.http_status=response?.status()||200;break;}
  case 'back':{const response=await page.goBack({waitUntil:'domcontentloaded',timeout:18000});item.http_status=response?.status()||200;break;}
  case 'forward':{const response=await page.goForward({waitUntil:'domcontentloaded',timeout:18000});item.http_status=response?.status()||200;break;}
  case 'viewport':item.width=data.width;item.height=data.height;await page.setViewportSize({width:item.width,height:item.height});if(item.cursor){item.cursor={...item.cursor,x:Math.min(item.width,item.cursor.x),y:Math.min(item.height,item.cursor.y)};await page.mouse.move(item.cursor.x,item.cursor.y)}break;
  case 'click':{
   const locator=data.ref?page.locator('[data-freedom-preview="'+data.ref+'"]'):null;
   if(locator)await pointAt(sid,item,locator);else await movePointer(sid,item,data.x,data.y);
   item.cursor={...item.cursor,down:true,click_id:Date.now()};emit(sid,await state(sid,item),item.source==='agent');
   if(locator)await locator.click({timeout:8000});else await page.mouse.click(data.x,data.y);
   await pause(100);item.cursor={...item.cursor,down:false};break;
  }
  case 'fill':{
   const locator=page.locator('[data-freedom-preview="'+data.ref+'"]');await pointAt(sid,item,locator);await locator.click({timeout:8000});
   await locator.fill('',{timeout:8000});await observedType(page,data.text);break;
  }
  case 'type':await observedType(page,data.text);break;
  case 'press':await page.keyboard.press(data.key);break;
  case 'scroll':await page.mouse.wheel(0,data.dy);break;
  case 'status':case 'look':case 'inspect':case 'screenshot':break;
  default:throw Error('Неизвестное действие просмотра.');
 }
 item=pages.get(sid);page=item.page;
 const result=await state(sid,item,data.frame!==false);
  if(action==='read'||(action==='open'&&data.read)){result.reading=await readPage(page,data.max_chars);result.http_status=item.http_status||200;result.navigation_attempts=item.navigation_attempts||1}
  if(action==='search'){result.search=item.search;delete item.search}
 if(['look','inspect','screenshot'].includes(action)){
  result.snapshot=await inspect(page);
  result.screenshot_path=path.join(output,'preview-'+hash(sid)+'-'+Date.now()+'.png');
  await page.screenshot({path:result.screenshot_path,animations:'disabled',timeout:12000});
 }
 return result;
 }finally{clearInterval(stream)}
}
const lines=readline.createInterface({input:process.stdin,terminal:false});
for await(const line of lines){
 let data;try{data=JSON.parse(line);const result=await command(data);process.stdout.write(JSON.stringify({id:data.id,result})+'\n')}
 catch(error){const launch=String(error.message).includes('browserType.launch');if(launch)process.stderr.write(String(error.stack)+'\n');process.stdout.write(JSON.stringify({id:data?.id,error:launch?'Не удалось запустить отдельный браузер просмотра. Подробности сохранены в журнале приложения.':String(error.message).slice(0,350)})+'\n')}
}
for(const browser of browsers.values())await browser.close();
