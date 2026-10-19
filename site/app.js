const en=document.documentElement.lang==='en';
const size=n=>(n/1024**3).toFixed(2)+(en?' GB':' ГБ');
async function release(){try{
 const response=await fetch('/api/release',{cache:'no-store'});if(!response.ok)return;
 const data=await response.json(),exe=data.files.find(f=>f.name.endsWith('.exe')),zip=data.files.find(f=>f.name.includes('Windows-x64.zip'));
 const url=file=>file.url||'/downloads/'+encodeURIComponent(file.name);
 if(exe){for(const link of document.querySelectorAll('.download-link'))link.href=url(exe);document.getElementById('hero-release').textContent='v'+data.version+' · '+size(exe.bytes)+' · Windows x64';document.getElementById('download-details').textContent='v'+data.version+' · '+size(exe.bytes)+' · '+(en?'models download separately':'модели скачиваются отдельно')}
 if(zip)document.getElementById('portable-download').href=url(zip);
 document.getElementById('checksum-download').href=data.public?'https://github.com/Leongrupp/freedom-gpt/releases/latest/download/SHA256SUMS.txt':'/downloads/SHA256SUMS.txt';
}catch{/* Downloads remain linked to the repository if the local metadata is absent. */}}
document.getElementById('copy-donation').addEventListener('click',async event=>{
 const copied=event.currentTarget.dataset.copied;
 const text='bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6';
 try{await navigator.clipboard.writeText(text)}catch{const field=document.createElement('textarea');field.value=text;document.body.appendChild(field);field.select();document.execCommand('copy');field.remove()}
 document.getElementById('copy-status').textContent=copied;
});
release();
