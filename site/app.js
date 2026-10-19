import {copyText} from './premium.js?v=community-1.4.1';
const en=document.documentElement.lang==='en';
const size=n=>(n/1024**3).toFixed(2)+(en?' GB':' ГБ');
const originalDownloads=new Map([...document.querySelectorAll('.download-link,#portable-download,#checksum-download')].map(link=>[link,link.innerHTML]));
function downloadState(ready){for(const [link,label] of originalDownloads){
 if(ready){link.removeAttribute('aria-disabled');link.innerHTML=label}
 else{link.setAttribute('aria-disabled','true');link.removeAttribute('href');if(link.classList.contains('download-link'))link.textContent=en?'Installer is uploading':'Установщик загружается'}
}}
async function release(){try{
 const response=await fetch('/api/release',{cache:'no-store'});if(!response.ok)return;
 const data=await response.json(),exe=data.files.find(f=>f.name.endsWith('.exe')),zip=data.files.find(f=>f.name.includes('Windows-x64.zip'));
 if(data.status==='pending'||!exe){downloadState(false);document.getElementById('hero-release').textContent=en?'Windows installer upload in progress':'Установщик Windows загружается в GitHub';document.getElementById('download-details').textContent=en?'Downloads will become available automatically after verification.':'Скачивание появится автоматически после проверки файлов.';return}
 downloadState(true);
 const url=file=>file.url||'/downloads/'+encodeURIComponent(file.name);
 if(exe){for(const link of document.querySelectorAll('.download-link'))link.href=url(exe);document.getElementById('hero-release').textContent='v'+data.version+' · '+size(exe.bytes)+' · Windows x64';document.getElementById('download-details').textContent='v'+data.version+' · '+size(exe.bytes)+' · '+(en?'models download separately':'модели скачиваются отдельно')}
 if(zip)document.getElementById('portable-download').href=url(zip);
 document.getElementById('checksum-download').href=data.public?'https://github.com/Leongrupp/freedom-gpt/releases/latest/download/SHA256SUMS.txt':'/downloads/SHA256SUMS.txt';
}catch{/* Downloads remain linked to the repository if the local metadata is absent. */}}

async function mirrors(){try{
 const response=await fetch('/api/models',{cache:'no-store'});if(!response.ok)return;
 const data=await response.json(),container=document.getElementById('model-mirrors');if(!container)return;
 container.replaceChildren();let count=0;
 for(const model of data.models||[]){for(const file of model.files||[]){
  if(!file.url?.startsWith('/models/'))continue;
  const link=document.createElement('a');link.href=file.url;link.className='mirror-file';link.textContent=model.name+' · '+file.name+' · '+size(file.bytes);container.append(link);count++;
 }}
 if(count){const heading=document.createElement('h3');heading.textContent=en?'Download model files manually':'Скачать файлы моделей вручную';container.prepend(heading)}
 container.hidden=!count;
}catch{/* The optional file mirror does not affect the model sources in the app. */}}
document.getElementById('copy-donation').addEventListener('click',async event=>{
 const copied=event.currentTarget.dataset.copied;
 const text='bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6';
 const success=await copyText(text);
 document.getElementById('copy-status').textContent=success?copied:(en?'Select the address and press Ctrl+C':'Выделите адрес и нажмите Ctrl+C');
});
release();
mirrors();
async function platforms(){try{
 const r=await fetch('/api/platforms',{cache:'no-store'});if(!r.ok)return;
 const data=await r.json(),section=document.getElementById('platform-downloads');if(!section||!data.platforms?.length)return;
 section.replaceChildren();section.hidden=false;
 const title=document.createElement('h3');title.textContent=en?'Choose your operating system':'Выберите операционную систему';section.append(title);
 const grid=document.createElement('div');grid.className='platform-grid';section.append(grid);
 for(const item of data.platforms){
  const card=document.createElement('article'),heading=document.createElement('h4'),note=document.createElement('p');heading.textContent=item.name;note.textContent=en?item.note_en:item.note_ru;card.append(heading,note);
  for(const file of item.files||[]){if(!file.url?.startsWith('/downloads/platform/')&&!file.url?.startsWith('https://github.com/Leongrupp/freedom-gpt/releases/download/'))continue;
   const a=document.createElement('a');a.href=file.url;a.textContent=file.format+' · '+size(file.bytes);a.className='platform-file';card.append(a);
  }grid.append(card);
 }
 if(data.local_only){const p=document.createElement('p');p.className='platform-local-note';p.textContent=en?'Local build previews. These files have not been published.':'Локальные сборки для проверки. Эти файлы ещё не опубликованы.';section.append(p)}
}catch{/* A platform is offered only after verified metadata is available. */}}
platforms();
setInterval(()=>{release();mirrors()},60000);
