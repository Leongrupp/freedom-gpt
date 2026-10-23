import {chromium} from 'playwright';
import readline from 'node:readline';
import path from 'node:path';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {installedBrowser} from './preview-launch.mjs';

const root=process.cwd(),cache=path.join(root,'.cache','preview-frames'),output=path.join(root,'output','browser-preview');
await fs.mkdir(cache,{recursive:true});await fs.mkdir(output,{recursive:true});
const pages=new Map(),epoch=crypto.randomUUID();let browser;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const emit=(sid,result,open=false)=>process.stdout.write(JSON.stringify({event:'preview.changed',sid,result,open})+'\n');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex').slice(0,24);
async function getBrowser(){
 if(browser?.isConnected())return browser;
 browser=await chromium.launch({executablePath:await installedBrowser(chromium),headless:true,args:['--disable-gpu','--disable-background-networking','--disable-sync','--no-first-run','--disk-cache-dir='+path.join(root,'.cache','preview-browser','disk'),'--crash-dumps-dir='+path.join(root,'.cache','preview-browser','crashes')]});return browser;
}
async function pageFor(sid,create=false){
 let item=pages.get(sid);
 if(item&&!item.page.isClosed()){item.used=Date.now();return item}
 if(!create)return null;
 if(pages.size>=4){const[old,entry]=[...pages].sort((a,b)=>a[1].used-b[1].used)[0];await entry.context.close();pages.delete(old);process.stdout.write(JSON.stringify({event:'preview.closed',sid:old,reason:'evicted'})+'\n')}
 const context=await(await getBrowser()).newContext({viewport:{width:1280,height:800},deviceScaleFactor:1,locale:'ru-RU',acceptDownloads:false});
 const page=await context.newPage();item={context,page,used:Date.now(),width:1280,height:800,revision:0,errors:[],cursor:null,source:'user',action:'status',capture:null};pages.set(sid,item);
 context.on('page',popup=>{item.page=popup;wire(popup,item)});wire(page,item);return item;
}
function wire(page,item){page.on('pageerror',error=>{item.errors.push(String(error.message).slice(0,400));item.errors=item.errors.slice(-12)});page.on('dialog',dialog=>dialog.dismiss().catch(()=>{}))}
async function state(sid,item,frame=false){
 if(!item)return {state:'idle',url:'',title:'',width:1280,height:800,epoch,updated_at:Date.now()};
 const page=item.page;
 if(frame){
  if(!item.capture)item.capture=(async()=>{const target=path.join(cache,hash(sid)+'.jpg');const bytes=await page.screenshot({type:'jpeg',quality:72,timeout:12000});await fs.writeFile(target+'.new',bytes);await fs.rename(target+'.new',target);item.revision++})().finally(()=>item.capture=null);
  await item.capture;
 }
 return {state:'ready',url:page.url(),title:await page.title().catch(()=>''),width:item.width,height:item.height,revision:item.revision,errors:item.errors,epoch,updated_at:Date.now(),cursor:item.cursor,source:item.source,action:item.action};
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
  const controls=[...document.querySelectorAll('a,button,input,textarea,select,[role="button"],[contenteditable="true"]')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height}).slice(0,70);
  return {text:(document.body?.innerText||'').slice(0,11000),elements:controls.map((e,i)=>{const ref='p'+(i+1);e.setAttribute('data-freedom-preview',ref);return {ref,tag:e.tagName.toLowerCase(),label:(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.getAttribute('name')||'').slice(0,130),type:e.getAttribute('type')}})};
 });
}
async function command(data){
 const {sid,action}=data;
 if(action==='close'){const item=pages.get(sid);if(item)await item.context.close();pages.delete(sid);return {state:'idle'}}
 if(action==='adopt'){const item=pages.get(data.from);if(item&&!pages.has(sid)){pages.delete(data.from);pages.set(sid,item)}return state(sid,pages.get(sid),true)}
 let item=await pageFor(sid,action==='open');
 if(!item){if(action==='status')return state(sid,null);throw Error('Сначала откройте сайт в панели просмотра.')}
 let page=item.page;if(action!=='status'){item.source=data.source==='agent'?'agent':'user';item.action=action}
 let updating=false;
 const stream=setInterval(async()=>{if(updating||!pages.has(sid))return;updating=true;try{emit(sid,await state(sid,item,true),item.source==='agent')}catch{}finally{updating=false}},260);
 try{
 if(item.source==='agent')emit(sid,await state(sid,item),true);
 switch(action){
  case 'open':await page.goto(data.url,{waitUntil:'domcontentloaded',timeout:25000});break;
  case 'reload':await page.reload({waitUntil:'domcontentloaded',timeout:25000});break;
  case 'back':await page.goBack({waitUntil:'domcontentloaded',timeout:18000});break;
  case 'forward':await page.goForward({waitUntil:'domcontentloaded',timeout:18000});break;
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
if(browser)await browser.close();
