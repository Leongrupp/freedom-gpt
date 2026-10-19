const en=document.documentElement.lang==='en';
const header=document.querySelector('.header');
let scheduled=false;
function updateHeader(){header?.classList.toggle('scrolled',window.scrollY>15);scheduled=false}
window.addEventListener('scroll',()=>{if(!scheduled){scheduled=true;requestAnimationFrame(updateHeader)}},{passive:true});updateHeader();

const menu=document.querySelector('.menu-toggle'),mobile=document.getElementById('mobile-nav');
function closeMenu(){if(!menu||!mobile)return;menu.setAttribute('aria-expanded','false');mobile.hidden=true;document.body.classList.remove('menu-open')}
menu?.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));mobile.hidden=!open;document.body.classList.toggle('menu-open',open)});
mobile?.addEventListener('click',event=>{if(event.target.closest('a'))closeMenu()});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){const wasOpen=menu?.getAttribute('aria-expanded')==='true';closeMenu();if(wasOpen)menu.focus()}});
window.matchMedia('(min-width:961px)').addEventListener('change',event=>{if(event.matches)closeMenu()});

const tabs=[...document.querySelectorAll('[data-preview-tab]')];
function selectTab(target,focus=false){for(const tab of tabs){const selected=target===tab;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;const panel=document.getElementById(tab.getAttribute('aria-controls'));if(panel)panel.hidden=!selected}if(focus)target.focus()}
for(const tab of tabs){tab.addEventListener('click',()=>selectTab(tab));tab.addEventListener('keydown',event=>{let index=tabs.indexOf(tab);if(event.key==='ArrowRight')index=(index+1)%tabs.length;else if(event.key==='ArrowLeft')index=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=tabs.length-1;else return;event.preventDefault();selectTab(tabs[index],true)})}

export async function copyText(text){if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(text);return true}catch{}}
 const active=document.activeElement,field=document.createElement('textarea');field.value=text;field.readOnly=true;field.className='copy-buffer';document.body.append(field);field.focus();field.select();field.setSelectionRange(0,text.length);const supply=event=>{if(event.clipboardData){event.clipboardData.setData('text/plain',text);event.preventDefault()}};document.addEventListener('copy',supply);let copied=false;try{copied=document.execCommand('copy')}catch{}finally{document.removeEventListener('copy',supply);field.remove();if(active instanceof HTMLElement)active.focus()}return copied}
const copy=document.getElementById('copy-code');
copy?.addEventListener('click',async()=>{const label=copy.querySelector('span'),original=label.textContent;const okay=await copyText(document.getElementById('sample-code').textContent);label.textContent=okay?copy.dataset.copied:(en?'Select and copy':'Выделите и скопируйте');copy.setAttribute('aria-label',label.textContent);setTimeout(()=>{label.textContent=original;copy.setAttribute('aria-label',original)},2500)});

if('IntersectionObserver' in window&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
 const observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target)}},{threshold:.06,rootMargin:'0px 0px 40px 0px'});
 document.querySelectorAll('[data-reveal]').forEach(element=>observer.observe(element));document.documentElement.classList.add('reveal-ready');
}
