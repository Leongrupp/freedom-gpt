import {copyText} from './premium.js?v=seo-20261020-r1';
const en=document.documentElement.lang==='en';
const repository='https://github.com/Leongrupp/freedom-gpt';
const size=n=>(n/1024**3).toFixed(2)+(en?' GB':' ГБ');
const safeURL=file=>{
 const value=file.url||'';
 return value.startsWith('/downloads/platform/')||value.startsWith('/downloads/')||value.startsWith(repository+'/releases/download/')?value:null;
};
function versionLabel(version){
 if(!/^\d+\.\d+\.\d+$/.test(version||''))return;
 const hero=document.getElementById('hero-release'),details=document.getElementById('download-details');
 if(hero)hero.textContent='v'+version+' · Windows / macOS / Ubuntu · RU / EN';
 if(details)details.textContent='v'+version+' · '+(en?'Free to use · models download separately':'Бесплатное приложение · модели скачиваются отдельно');
}
async function release(){try{
 const response=await fetch('/api/release',{cache:'no-store'});if(!response.ok)return;
 const data=await response.json();if(data.status==='pending')return;
 versionLabel(data.version);
 const checksum=document.getElementById('checksum-download');if(checksum)checksum.href=data.public?repository+'/releases/latest/download/SHA256SUMS.txt':'/downloads/SHA256SUMS.txt';
}catch{/* The verified release links in HTML remain available without metadata. */}}
function label(file){
 if(file.name.endsWith('.exe'))return en?'Download for Windows':'Скачать для Windows';
 if(file.name.endsWith('.run'))return en?'Download for Ubuntu':'Скачать для Ubuntu';
 if(file.name.includes('macOS'))return en?'Download for Mac':'Скачать для Mac';
 if(file.name.endsWith('.deb'))return en?'DEB package':'Пакет DEB';
 if(file.name.endsWith('.tar.gz'))return en?'Portable TAR.GZ':'Переносимый TAR.GZ';
 return en?'Portable ZIP':'Переносимый ZIP';
}
const arrows=new Map([...document.querySelectorAll('[data-platform-card]')].map(card=>[card.dataset.platformCard,card.querySelector('.platform-primary svg')?.cloneNode(true)]));
async function platforms(){try{
 const response=await fetch('/api/platforms',{cache:'no-store'});if(!response.ok)return;
 const data=await response.json();if(!data.platforms?.length)return;
 for(const item of data.platforms){
  const card=[...document.querySelectorAll('[data-platform-card]')].find(node=>node.dataset.platformCard===item.id);if(!card)continue;
  const rank=file=>file.name.endsWith('.exe')||file.name.endsWith('.run')||file.name.includes('macOS')?0:file.name.endsWith('.zip')||file.name.endsWith('.deb')?1:2;
  const files=(item.files||[]).filter(file=>safeURL(file)&&Number.isFinite(file.bytes)&&file.bytes>0).sort((a,b)=>rank(a)-rank(b));if(!files.length)continue;
  const container=card.querySelector('.platform-files');const fragment=document.createDocumentFragment();
  files.forEach((file,index)=>{
   const link=document.createElement('a');link.href=safeURL(file);link.className=index===0?'platform-primary':'platform-alternative';
   const caption=document.createElement('span');caption.append(document.createTextNode(label(file)));const bytes=document.createElement('small');bytes.textContent=size(file.bytes);caption.append(bytes);link.append(caption);
   const arrow=arrows.get(item.id);if(arrow)link.append(arrow.cloneNode(true));fragment.append(link);
  });container.replaceChildren(fragment);
  const note=en?item.note_en:item.note_ru;if(note)card.querySelector('.platform-note').textContent=note;
  for(const quick of document.querySelectorAll('[data-platform-download]'))if(quick.dataset.platformDownload===item.id)quick.href=safeURL(files[0]);
 }
 versionLabel(data.version);
}catch{/* Static OS cards link to the last verified public release. */}}
async function mirrors(){try{
 const response=await fetch('/api/models',{cache:'no-store'});if(!response.ok)return;
 const data=await response.json(),container=document.getElementById('model-mirrors');if(!container)return;
 container.replaceChildren();let count=0;
 for(const model of data.models||[])for(const file of model.files||[]){
  if(!file.url?.startsWith('/models/'))continue;
  const link=document.createElement('a');link.href=file.url;link.className='mirror-file';link.textContent=model.name+' · '+file.name+' · '+size(file.bytes);container.append(link);count++;
 }
 if(count){const title=document.createElement('h3');title.textContent=en?'Download model files manually':'Скачать файлы моделей вручную';container.prepend(title)}container.hidden=!count;
}catch{/* A missing mirror does not affect official model download sources. */}}
document.getElementById('copy-donation')?.addEventListener('click',async event=>{
 const copied=event.currentTarget.dataset.copied;
 const success=await copyText('bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6');
 document.getElementById('copy-status').textContent=success?copied:(en?'Select the address and press Ctrl+C':'Выделите адрес и нажмите Ctrl+C');
});
function refresh(){return Promise.allSettled([release(),platforms(),mirrors()])}if(document.getElementById('platform-downloads')){refresh();setInterval(refresh,60000)}
for(const link of document.querySelectorAll('[data-guide-link]'))link.addEventListener('click',()=>{const guide=document.getElementById(link.dataset.guideLink);if(guide instanceof HTMLDetailsElement)guide.open=true});
function openLinkedGuide(){const guide=document.getElementById(location.hash.slice(1));if(guide?.classList.contains('installation-system'))guide.open=true}openLinkedGuide();window.addEventListener('hashchange',openLinkedGuide);
for(const button of document.querySelectorAll('[data-copy-command]'))button.addEventListener('click',async()=>{
 const code=document.getElementById(button.dataset.copyCommand);if(!code)return;
 const okay=await copyText(code.textContent);const status=button.closest('.install-command')?.querySelector('.command-copy-status');
 if(status)status.textContent=okay?(en?'Copied. Paste into your terminal.':'Скопировано. Вставьте в свой терминал.'):(en?'Select the commands and copy them manually.':'Выделите команды и скопируйте вручную.');
 button.textContent=okay?(en?'Copied ✓':'Скопировано ✓'):(en?'Select and copy':'Выделите и скопируйте');
});

for(const button of document.querySelectorAll('[data-select-command]'))button.addEventListener('click',()=>{
 const code=document.getElementById(button.dataset.selectCommand);if(!code)return;
 code.focus();const range=document.createRange();range.selectNodeContents(code);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
 const status=button.closest('.install-command')?.querySelector('.command-copy-status');if(status)status.textContent=en?'Selected. Press Ctrl+C (or Cmd+C on Mac).':'Выделено. Нажмите Ctrl+C (или Cmd+C на Mac).';
});
