import React,{useEffect,useRef,useState} from 'react';
import catalog from '../../messenger/stickers.json';
export {catalog};
export function useMotion(){const [reduce,set]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);useEffect(()=>{const m=matchMedia('(prefers-reduced-motion: reduce)'),change=()=>set(m.matches);m.addEventListener('change',change);return()=>m.removeEventListener('change',change)},[]);return reduce}
export function Sticker({id,animate=true,small=false}){
 const item=catalog.find(x=>x.id===id),ref=useRef(null),[visible,V]=useState(false);
 useEffect(()=>{const observer=new IntersectionObserver(([entry])=>V(entry.isIntersecting),{rootMargin:'100px'});if(ref.current)observer.observe(ref.current);return()=>observer.disconnect()},[]);
 if(!item)return <span className="fm-sticker-missing">[GIF недоступен в этой версии]</span>;
 return <span ref={ref} className={'fm-sticker '+(small?'compact':'')+(item.width/item.height>2?' wide':'')} title={item.title}>{visible&&animate?<img src={'/messenger/stickers/'+item.id+'.gif'} alt={item.title} width={item.width} height={item.height} loading="lazy"/>:<span role="img" aria-label={item.title}>GIF</span>}</span>
}
export function StickerPicker({onChoose,animate}){
 const [query,Q]=useState(''),[category,C]=useState('Все');const visible=catalog.filter(s=>(category==='Все'||s.category===category)&&s.title.toLocaleLowerCase('ru').includes(query.toLocaleLowerCase('ru')));
 return <section className="fm-sticker-picker" aria-label="Фирменные GIF Freedom"><header><strong>Фирменные GIF <small>{catalog.length}</small></strong><input aria-label="Найти GIF" placeholder="Найти смайл…" value={query} onChange={e=>Q(e.target.value)}/></header><div className="fm-sticker-tabs">{['Все','Эмоции','Общение','Ретро','Наборы'].map(c=><button key={c} aria-pressed={category===c} onClick={()=>C(c)}>{c}</button>)}</div><div className="fm-sticker-grid">{visible.map(item=><button type="button" key={item.id} title={item.title} aria-label={'GIF: '+item.title} onClick={()=>onChoose(item.id)}><Sticker id={item.id} small animate={animate}/><span>{item.title}</span></button>)}</div><small>Выберите GIF, затем нажмите «Отправить».</small></section>
}
