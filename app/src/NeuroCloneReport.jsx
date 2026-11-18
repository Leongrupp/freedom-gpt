import React from 'react';
import {GitBranch} from 'lucide-react';
import MessageMarkdown from './MessageMarkdown.jsx';
export default function NeuroCloneReport({row,onChoose,onRefresh}){
 const c=row.coverage||{};
 const projectNames=new Map((row.suggestions||[]).flatMap(idea=>idea.projects.map(p=>[p.id,p.name])));
 const readable=text=>String(text||'').replace(/\bproject_ids\s*:/g,'Связанные проекты:').replace(/\bp[a-f0-9]{10}\b/g,id=>projectNames.get(id)||id);
 return <section className="clone-report" aria-label="Стратегия нейроклона">
  <p className="clone-coverage">Охват: каталог {c.projects_catalogued} из {c.projects_total} проектов · {c.chat_titles_read} заголовков · {c.documents_read} документов · {c.freedom_chats_read} переписок Freedom. Codex и Claude — метаданные, без полного текста чатов.</p>
  {row.plan&&<div className="development-plan"><MessageMarkdown text={readable(row.plan.replace(/```neuro-clone\s*\n[\s\S]*?```/g,''))}/></div>}
  <div className="clone-suggestions">{(row.suggestions||[]).map((idea,i)=><article key={i}>
   <small>ГИПОТЕЗА {i+1} · НУЖНА ПРОВЕРКА</small><h3>{idea.title}</h3>
   <div className="clone-projects">{idea.projects.map(p=><span key={p.id}>{p.name}</span>)}</div>
   <p>{readable(idea.why)}</p><p><strong>Кто и за что платит: </strong>{readable(idea.monetization)}</p>
   <p><strong>Проверка спроса: </strong>{idea.validation}</p><p><strong>Усилия: </strong>{idea.effort}</p>
   <ol>{idea.steps.map((step,j)=><li key={j}>{step}</li>)}</ol>
   <button className="secondary-panel-button" onClick={()=>onChoose(idea)}><GitBranch size={14}/>Выбрать идею и уточнить план</button>
  </article>)}</div>
  {row.state==='review'&&!row.suggestions?.length&&<p className="panel-error">Анализ сохранён, но цепочки не распознаны. Уточните ответ в чате анализа — неподтверждённые связи не добавлены.</p>}
  {row.state==='review'&&<button className="secondary-panel-button" onClick={onRefresh}>Обновить анализ моих проектов</button>}
 </section>
}
