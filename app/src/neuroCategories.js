// Presentation only: folders, chat ownership and execution state are never changed.
export const categories=[
 {id:'security',title:'Безопасность',color:'#ed9a8e',pattern:/security|pentest|vulnerab|php2shell|audit|безопас|уязвим|пентест/i},
 {id:'web',title:'Сайты и магазины',color:'#69c9e4',pattern:/website|web[-_ ]|nextjs|nextgen|landing|shop|store|market|сайт|магазин|лендинг|ozon|avtopro/i},
 {id:'ai',title:'ИИ и агенты',color:'#b49af4',pattern:/freedom|hermes|agent|llm|qwen|neuro|jarvis|arshi|assistant|нейро|агент|помощник|(?:^|[-_ ])ai(?:$|[-_ ])/i},
 {id:'media',title:'Медиа и 3D',color:'#e6a6cf',pattern:/video|audio|music|voice|photo|image|blender|avatar|cinema|3d|vr|видео|фото|музык|голос|аватар/i},
 {id:'business',title:'Бизнес и данные',color:'#e5c079',pattern:/crm|analytics|finance|invoice|business|data|excel|report|seo|integra|бизнес|аналит|отч[её]т|заказ/i},
 {id:'infra',title:'Сети и системы',color:'#78c7b1',pattern:/vpn|server|network|docker|relay|proxy|greenedge|сервер|сет[ьи]|инфра/i},
 {id:'tools',title:'Приложения',color:'#91afe8',pattern:/app|tool|desktop|game|utility|converter|прилож|игр|конверт/i},
 {id:'other',title:'Другие проекты',color:'#a6acbd'}
];
const key=p=>String(p||'').replaceAll('\\','/').replace(/\/+$/,'').toLowerCase();
export function categoryFor(project){
 const title=project.title||project.name||'';
 return categories.find(c=>c.pattern?.test(title))||categories.find(c=>c.pattern?.test((project.chats||[]).slice(0,8).map(c=>c.title||'').join(' ')))||categories.at(-1);
}
export function categoryGraph(graph,{enabled=true,nested=true,hidden=[],global=true}={}){
 if(!enabled)hidden=[];
 const byPath=new Map(),bySid=new Map(),counts={};
 for(const p of graph.nodes.filter(n=>n.type==='project')){const c=categoryFor(p);byPath.set(key(p.path),c);counts[c.id]=(counts[c.id]||0)+1;for(const chat of p.chats||[])bySid.set(chat.id,c)}
 const decorate=n=>{const c=n.type==='project'?byPath.get(key(n.path)):byPath.get(key(n.projectPath))||bySid.get(n.sid)||bySid.get(n.id.replace(/^chat:/,''));return {...n,visualCategory:c?.id,visualColor:enabled?c?.color:undefined}};
 let visible=graph.visible.map(decorate),links=graph.links.map(e=>({...e}));
 if(global&&nested){const ids=new Set(visible.map(n=>n.id));for(const n of graph.nodes){if(n.type!=='chat'||!n.projectPath||ids.has(n.id)||visible.length>=1000)continue;const parent='project:'+key(n.projectPath);if(ids.has(parent)){visible.push(decorate({...n,visualChild:true}));ids.add(n.id);links.push({from:parent,to:n.id})}}}
 if(enabled&&global){for(const c of categories){if(!counts[c.id])continue;visible.push({id:'category:'+c.id,type:'category',title:c.title,visualCategory:c.id,visualColor:c.color,count:counts[c.id],description:'Визуальная группировка по названиям проектов и заголовкам чатов. Исходные папки остаются на месте.'});links.push({from:'core',to:'category:'+c.id});}links=links.map(e=>{const n=visible.find(n=>n.id===e.to);return n?.type==='project'?{...e,from:'category:'+n.visualCategory}:e})}
 visible=visible.filter(n=>!hidden.includes(n.visualCategory));const ids=new Set(visible.map(n=>n.id));links=links.filter(e=>ids.has(e.from)&&ids.has(e.to));
 const decoratedNodes=graph.nodes.map(decorate);return {...graph,nodes:[...decoratedNodes,...visible.filter(n=>n.type==='category')],visible,links,matches:[...visible.filter(n=>n.type==='category'),...graph.matches.map(decorate).filter(n=>!hidden.includes(n.visualCategory))],categoryCounts:counts};
}
