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
 const field=document.createElement('textarea');field.value=text;field.readOnly=true;field.style.cssText='position:fixed;left:-10000px';document.body.appendChild(field);field.focus();field.select();let success=false;
 try{success=document.execCommand('copy')}finally{field.remove()}
 if(!success){try{await navigator.clipboard.writeText(text);success=true}catch{}}
 document.getElementById('copy-status').textContent=success?copied:(en?'Select the address and press Ctrl+C':'Выделите адрес и нажмите Ctrl+C');
});
release();
mirrors();
setInterval(()=>{release();mirrors()},60000);
