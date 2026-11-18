const by=id=>document.getElementById(id),token=location.pathname.split('/').pop();let timer;
const params=new URLSearchParams(location.search),english=(params.get('lang')||navigator.language||'ru').toLowerCase().startsWith('en');
const text=(ru,en)=>english?en:ru;
document.documentElement.lang=english?'en':'ru';
if(english){
 document.querySelectorAll('[data-en]').forEach(element=>element.innerHTML=element.dataset.en);
 document.title=by('connect')?'Connect your phone · Freedom GPT':'Freedom GPT · Phone access';
}
if(by('language')){by('language').textContent=english?'RU':'EN';by('language').href='?lang='+(english?'ru':'en')}
async function request(path,options={}){
 const r=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
 if(!r.ok){const detail=await r.text();throw Error(english?'Connection unavailable. Check the invitation on your PC and try again. ('+r.status+')':detail)}
 return r.json();
}
async function poll(){
 try{
  const state=await request('/phone/claim');by('code').textContent=state.code;
  if(state.state==='approved'){
   clearInterval(timer);by('status').textContent=text('Компьютер разрешил доступ. Подключение готово.','Your computer approved access. Ready to connect.');
   by('waiting').classList.add('hidden');by('open').classList.remove('hidden');setTimeout(()=>location.replace('/'),700);
  }else if(state.state==='rejected'){
   clearInterval(timer);by('waiting').classList.add('hidden');by('error').textContent=text('Подключение отклонено на компьютере. Создайте новый QR-код, если это ваш телефон.','Your PC rejected this connection. Create a new QR code if this is your phone.');
  }
 }catch(e){clearInterval(timer);by('error').textContent=e.message}
}
if(by('connect')){
 by('connect').onclick=async()=>{
  try{
   by('connect').disabled=true;
   const state=await request('/phone/claim',{method:'POST',body:JSON.stringify({token})});
   by('connect').classList.add('hidden');by('waiting').classList.remove('hidden');
   by('status').textContent=text('Ждём подтверждение на вашем компьютере.','Waiting for approval on your computer.');
   by('code').textContent=state.code;timer=setInterval(poll,1000);
  }catch(e){by('error').textContent=e.message;by('connect').disabled=false}
 };
 request('/phone/pair-info/'+encodeURIComponent(token)).then(value=>{
  by('label').textContent=value.label;
  by('status').textContent=text('Разрешите этому телефону подключиться к вашему агенту.','Allow this phone to connect to your agent.');
  by('connect').disabled=false;
 }).catch(e=>by('error').textContent=e.message);
}
