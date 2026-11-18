export const pathKey=value=>String(value||'').replaceAll('\\','/').replace(/\/+$/,'').toLocaleLowerCase();
export const kindNames={workspace:'Пространство',idea:'Развитие',project:'Проект',chat:'Чат',task:'Задание',goal:'Цель',memory:'Память',file:'Файл',skill:'Навык',group:'Группа',activity:'Действие'};
const shorten=(text,limit=100)=>String(text||'').slice(0,limit);
export const MAX_SCENE_NODES=512;
export function buildNeuroGraph({index={},sid,snapshot={},memory={},skills=[],scope=null,query='',includeArchive=false,view='all'}){
 const nodes=[],links=[],crossLinks=[],ids=new Set();
 function add(node,parent){if(ids.has(node.id))return;nodes.push(node);ids.add(node.id);if(parent)links.push({from:parent,to:node.id})}
 add({id:'core',type:'workspace',title:'Freedom · Нейросфера',status:'idle',description:'Проекты, сохранённые связи и наблюдаемые события агента.'});
 const sessions=[...(index.sessions||[]),...(index.external_sessions||[])].filter(s=>includeArchive||!s.archived),projects=[...(index.projects||[])];
 const currentPath=snapshot.info?.cwd;
 let current=[...projects].sort((a,b)=>b.path.length-a.path.length).find(p=>pathKey(currentPath)===pathKey(p.path)||pathKey(currentPath).startsWith(pathKey(p.path)+'/'));
 if(currentPath&&!current){current={name:currentPath.split(/[\\/]/).filter(Boolean).at(-1),path:currentPath,exists:true};projects.push(current)}
 const bindings=new Map(sessions.map(s=>[s.id,s.project]));if(sid&&current)bindings.set(sid,current.path);
 for(const project of projects){
  const chats=sessions.filter(s=>pathKey(bindings.get(s.id))===pathKey(project.path));
  const id='project:'+pathKey(project.path);
  add({id,type:'project',title:project.name,path:project.path,status:chats.some(s=>s.running)?'active':'idle',chats,chatsCount:chats.length,missing:project.exists===false,readOnly:!!project.read_only,sources:project.sources||[]},'core');
 }
 const unbound=sessions.filter(s=>!bindings.get(s.id));
 if(unbound.length)add({id:'unbound',type:'group',title:'Чаты без привязки',description:'В сохранённых метаданных этих чатов нет подтверждённой папки проекта.',chats:unbound,chatsCount:unbound.length},'core');
 const currentProject=current?'project:'+pathKey(current.path):'unbound';
 const selectedProject=scope&&nodes.find(n=>n.id===scope&&['project','group'].includes(n.type));
 const shownChats=sessions;
 for(const chat of shownChats){
  const parent=bindings.get(chat.id)?'project:'+pathKey(bindings.get(chat.id)):'unbound';
  if(!ids.has(parent))add({id:parent,type:'group',title:'Чаты без привязки'},'core');
  add({id:'chat:'+chat.id,type:'chat',title:chat.title||'Чат',sid:chat.external?null:chat.id,external:!!chat.external,source:chat.source||'freedom',projectPath:chat.project,readOnly:!!projects.find(p=>pathKey(p.path)===pathKey(chat.project))?.read_only,status:(chat.id===sid?snapshot.running:chat.running)?'active':'idle',updated:chat.updated,description:chat.external?'Сохранённый чат '+(chat.source==='codex'?'Codex':'Claude Code')+'. История и выполнение задач остаются в исходной программе.':chat.archived?'В архиве':'Переписка и история работы'},parent);
 }
 if(sid){
  if(!ids.has('chat:'+sid))add({id:'chat:'+sid,type:'chat',title:snapshot.info?.title||sessions.find(s=>s.id===sid)?.title||'Текущий чат',sid,status:snapshot.running?'active':'idle'},ids.has(currentProject)?currentProject:'core');
  const parent='chat:'+sid,active=snapshot.work_active;
  if(active?.text)add({id:'task:active:'+sid,type:'task',title:shorten(active.text,240),sid,status:snapshot.running?'active':active.finished?'complete':'idle',description:'Текущий запрос пользователя'},parent);
  for(const [i,row] of (snapshot.queue||[]).entries())add({id:'task:queue:'+(row.admission_id||row.id||i),type:'task',title:shorten(row.text||row.prompt||'Задание в очереди',240),sid,status:'queued',description:'Ожидает выполнения'},parent);
  const goals=[...(snapshot.goal_state?.goal?[snapshot.goal_state.goal]:[]),...(snapshot.goal_state?.history||[])];
  for(const [i,row] of goals.entries()){const goal=row.goal||row;add({id:'goal:'+(row.id||goal.created_at||i),type:'goal',title:shorten(row.title||goal.title||goal.objective||row.fields?.objective||'Сохранённая цель',240),sid,status:goal.status==='active'?'active':['done','complete','completed','achieved'].includes(goal.status)?'complete':goal.status==='blocked'?'error':'idle',description:{active:'Цель в работе',paused:'Цель на паузе',done:'Цель завершена',blocked:'Цель требует внимания'}[goal.status]||'История целей'},parent)}
  const files=[...(snapshot.artifacts||[]),...(snapshot.attachments||[]).flatMap(a=>a.files||[])],seen=new Set();
  for(const f of files){const key=String(f.id||f.path||f.name);if(seen.has(key))continue;seen.add(key);add({id:'file:'+key,type:'file',title:f.name||f.path||'Файл',sid,status:'idle',description:'Файл текущего чата',url:f.url||null},parent)}
  if(memory.records||memory.items?.length)add({id:'memory-root:'+sid,type:'group',category:'memory',title:'Память проекта',sid,status:'idle',count:memory.records||memory.items.length,description:'Сохранённые записи. На карте показаны последние или найденные записи.'},parent);
  for(const [i,row] of (memory.items||[]).entries())add({id:'memory:'+(row.id||i),type:'memory',title:shorten(row.title||row.excerpt||row.kind||'Запись памяти'),sid,status:'idle',description:row.excerpt||'',kind:row.kind},'memory-root:'+sid);
  for(const [i,event] of (snapshot.activity?.events||[]).filter(e=>e.tool&&e.kind==='tool').slice(-8).entries())add({id:'activity:'+sid+':'+i,type:'activity',title:event.tool,sid,status:event.status==='done'?'complete':event.status==='error'?'error':'active',description:'Наблюдаемый вызов инструмента',at:event.at},parent);
  if(snapshot.pending?.some(p=>p.status==='unknown'))add({id:'activity:unknown:'+sid,type:'activity',title:'Результат действия неизвестен',sid,status:'error',description:'В истории есть прерванное действие. Проверьте результат в чате перед повтором.'},parent);
 }
 for(const idea of index.development||[]){
  const project=nodes.filter(n=>n.type==='project'&&(pathKey(idea.cwd)===pathKey(n.path)||pathKey(idea.cwd).startsWith(pathKey(n.path)+'/'))).sort((a,b)=>b.path.length-a.path.length)[0];
  const status=['active','analyzing'].includes(idea.state)?'active':idea.state==='done'?'complete':idea.state==='analysis_failed'?'error':['creating','submitting','analyzing','approved','starting'].includes(idea.state)?'queued':'idle';
  add({id:'development:'+idea.id,type:'idea',proposal_id:idea.id,title:idea.title,status,sid:idea.execution_sid||idea.analysis_sid||idea.source_sid,description:idea.idea,development_state:idea.state},idea.parent_id&&(index.development||[]).some(p=>p.id===idea.parent_id)?'development:'+idea.parent_id+(index.development.find(p=>p.id===idea.parent_id).execution_sid?':work':''):project?.id||'core');
  const root='development:'+idea.id;let parent=root;
  for(const [i,suggestion] of (idea.suggestions||[]).entries()){
   const key=root+':suggestion:'+i;add({id:key,type:'idea',proposal_id:idea.id,title:suggestion.title,status:'suggested',description:suggestion.why+' Проверка: '+suggestion.validation},root);
   let previous=key;for(const [j,step] of suggestion.steps.entries()){const next=key+':step:'+j;add({id:next,type:'task',proposal_id:idea.id,title:step,status:'suggested',description:'Предлагаемый этап. Работа ещё не запускалась.'},previous);previous=next}
   for(const linked of suggestion.projects||[]){const projectId='project:'+pathKey(linked.path);if(ids.has(projectId))crossLinks.push({from:projectId,to:key,suggested:true})}
  }
  if(idea.analysis_sid){const id=root+':plan';add({id,type:'activity',proposal_id:idea.id,title:'План · '+idea.title,sid:idea.analysis_sid,status:idea.state==='analyzing'?'active':idea.state==='analysis_failed'?'error':['creating','submitting'].includes(idea.state)?'queued':'complete',description:'Отдельный чат анализа и предложение владельцу.'},root);parent=id}
  if(['approved','starting','active','paused','done'].includes(idea.state)){const id=root+':approved';add({id,type:'activity',proposal_id:idea.id,title:'План согласован',status:'complete',description:'Владелец подтвердил план и цель ближайшего этапа.'},parent);parent=id}
  if(idea.execution_sid)add({id:root+':work',type:'chat',proposal_id:idea.id,title:'Рабочая ветка · '+idea.title,sid:idea.execution_sid,status:idea.state==='active'?'active':idea.state==='done'?'complete':'idle',description:'Выполнение согласованной цели. Пауза, уточнения и проверка результата — в чате.'},parent);

 }
 if(skills.length){
  add({id:'skills',type:'group',title:'Библиотека навыков',count:skills.length,description:'Установленные навыки. Наличие в библиотеке не означает использование в текущей задаче.'},'core');
  for(const skill of skills)add({id:'skill:'+(skill.name||skill.path),type:'skill',title:skill.name||skill.title,description:skill.description||'',status:'idle'},'skills');
 }
 const term=query.trim().toLocaleLowerCase();let candidates=nodes.filter(n=>n.id!=='core');
 if(view==='chat'){const allowed=new Set(sid?['chat:'+sid]:[]);for(let depth=0;depth<8;depth++)for(const link of links)if(allowed.has(link.from))allowed.add(link.to);candidates=candidates.filter(n=>allowed.has(n.id))}
 if(term)candidates=candidates.filter(n=>(n.title+' '+(n.path||'')+' '+(n.description||'')+' '+(n.sources||[]).join(' ')).toLocaleLowerCase().includes(term));
 else if(selectedProject)candidates=candidates.filter(n=>n.id===scope||n.type!=='project'&&n.type!=='group'&&(n.projectPath===selectedProject.path||n.sid&&selectedProject.chats.some(c=>c.id===n.sid)));
 else if(scope==='skills')candidates=candidates.filter(n=>n.id==='skills'||n.type==='skill');
 else if(view!=='chat')candidates=candidates.filter(n=>n.type==='project'||n.type==='group'||n.type==='idea'||n.status==='active'||n.sid===sid&&n.type==='goal');
 candidates.sort((a,b)=>(b.status==='active')-(a.status==='active')||a.id.localeCompare(b.id));
 let stage=candidates;
 if(!term&&!scope&&view!=='chat'){
  const roots=nodes.filter(n=>n.type==='project'||['unbound','skills'].includes(n.id));
  const chosen=new Set(roots.map(n=>n.id));
  for(const n of nodes)if(n.proposal_id||n.status==='active'||n.status==='error'||n.sid===sid&&['goal','memory','file','task'].includes(n.type)||n.id==='memory-root:'+sid)chosen.add(n.id);
  stage=nodes.filter(n=>chosen.has(n.id)).sort((a,b)=>!!b.proposal_id-!!a.proposal_id);
 }
 for(const edge of crossLinks){if(!stage.some(n=>n.id===edge.to))continue;const linked=nodes.find(n=>n.id===edge.from);if(linked&&!stage.includes(linked))stage.unshift(linked)}
 const visible=[nodes[0],...stage.slice(0,MAX_SCENE_NODES)],visibleIds=new Set(visible.map(n=>n.id)),parents=new Map(links.map(l=>[l.to,l.from])),edges=[];
 for(const node of visible){if(node.id==='core')continue;let parent=parents.get(node.id)||'core',guard=0;while(!visibleIds.has(parent)&&guard++<8)parent=parents.get(parent)||'core';edges.push({from:parent,to:node.id})}
 for(const edge of edges)if(nodes.find(n=>n.id===edge.to)?.status==='suggested')edge.proposed=true;
 for(const edge of crossLinks)if(visibleIds.has(edge.from)&&visibleIds.has(edge.to))edges.push(edge);
 return {nodes,visible,links:edges,hidden:Math.max(0,stage.length-MAX_SCENE_NODES),matches:candidates,projects:projects.length,chats:sessions.length,sceneLimit:MAX_SCENE_NODES,currentProject,records:memory.records||0,skills:skills.length};
}
export function positionsFor(nodes,links=[]){
 const positions=new Map([['core',[0,0,0]]]),parents=new Map(links.filter(l=>!l.suggested).map(l=>[l.to,l.from]));
 const hash=value=>{let n=2166136261;for(const c of value)n=Math.imul(n^c.charCodeAt(0),16777619);return n>>>0};
 const roots=nodes.filter(n=>n.id!=='core'&&(!parents.get(n.id)||parents.get(n.id)==='core'));
 for(const node of roots){const categoryIndex=roots.filter(n=>n.type==='category').findIndex(n=>n.id===node.id),a=node.type==='category'?categoryIndex/Math.max(1,roots.filter(n=>n.type==='category').length)*Math.PI*2:hash(node.id)/4294967296*Math.PI*2,z=node.type==='category'?(categoryIndex%2?.22:-.22):hash('height:'+node.id)/4294967296*1.6-.8,r=node.type==='category'?10:8+(hash('radius:'+node.id)%400)/100,plane=Math.sqrt(1-z*z);positions.set(node.id,[Math.cos(a)*plane*r,z*r,Math.sin(a)*plane*r])}
 for(let depth=0;depth<nodes.length;depth++){let changed=false;for(const node of nodes){if(positions.has(node.id))continue;const parentId=parents.get(node.id),parent=positions.get(parentId);if(!parent)continue;const h=hash(node.id),a=h/4294967296*Math.PI*2,isCluster=parentId?.startsWith('category:'),r=isCluster?1.4+(h%300)/100:node.visualChild?.35+(h%7)*.06:.6+(h%7)*.1;positions.set(node.id,[parent[0]+Math.cos(a)*r,parent[1]+(((h>>>8)%100)/100-.5)*(isCluster?6:node.visualChild?.65:1.7),parent[2]+Math.sin(a)*r]);changed=true}if(!changed)break}
 for(const node of nodes)if(!positions.has(node.id)){const a=hash(node.id)/4294967296*Math.PI*2;positions.set(node.id,[Math.cos(a)*5,0,Math.sin(a)*5])}
 return positions;
}
export function eventKind(tool){
 const value=String(tool||'');if(/memory|recall/.test(value))return 'memory';if(/skill/.test(value))return 'skill';if(/browser|web_search|web_extract/.test(value))return 'web';if(/write|patch|read_file|search_files/.test(value))return 'file';return value?'tool':null;
}
