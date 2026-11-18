import React,{useEffect,useMemo,useRef,useState} from 'react';
import {ArrowRightLeft,Upload,Download,FolderOpen,X,LoaderCircle,CheckCircle2,Clock3,ShieldCheck,Files} from 'lucide-react';
import {api} from './api.js';
import './file-converter.css';

const labels={pdf:'PDF · документ',docx:'Word · DOCX',odt:'OpenDocument · ODT',rtf:'RTF · текст с оформлением',txt:'TXT · обычный текст',html:'HTML · веб-страница',epub:'EPUB · электронная книга',
  xlsx:'Excel · XLSX',ods:'OpenDocument · ODS',csv:'CSV · таблица',tsv:'TSV · таблица',json:'JSON · данные',yaml:'YAML · данные',pptx:'PowerPoint · PPTX',odp:'OpenDocument · ODP',
  jpg:'JPG · фото',png:'PNG · прозрачность',webp:'WebP · для сайтов',avif:'AVIF · компактные фото',bmp:'BMP · изображение',tif:'TIFF · изображение',gif:'GIF · изображение / анимация',ico:'ICO · иконка',
  mp4:'MP4 · видео',mkv:'MKV · видео',webm:'WebM · видео',mov:'MOV · видео',avi:'AVI · видео',mp3:'MP3 · звук',wav:'WAV · звук без сжатия',flac:'FLAC · звук без потерь',m4a:'M4A · звук',ogg:'OGG · звук',opus:'Opus · звук',aac:'AAC · звук',srt:'SRT · субтитры',vtt:'WebVTT · субтитры'};
const ext=name=>name.split('.').at(-1).toLowerCase();
const size=n=>n>=1024**3?(n/1024**3).toFixed(2)+' ГБ':n>=1024**2?(n/1024**2).toFixed(1)+' МБ':n>=1024?Math.round(n/1024)+' КБ':n+' Б';
const statusNames={queued:'В очереди',working:'В работе',ready:'Готово',error:'Ошибка',cancelled:'Остановлено'};
export function FileConverterPanel({sid}){
  const [info,setInfo]=useState(null),[files,setFiles]=useState([]),[target,setTarget]=useState('pdf'),[jobs,setJobs]=useState([]),[error,setError]=useState(''),[sending,setSending]=useState(false),[drag,setDrag]=useState(false),[attach,setAttach]=useState(false);
  const [options,setOptions]=useState({quality:'balanced',image_size:0,video_size:0,ocr:false,merge:false});
  const [saved,setSaved]=useState({}),[saving,setSaving]=useState(null),[showAll,setShowAll]=useState(false);
  const input=useRef(),mounted=useRef(true);
  const common=useMemo(()=>!files.length?[]:(info?.formats?.[ext(files[0].name)]||[]).filter(format=>files.every(f=>info?.formats?.[ext(f.name)]?.includes(format))),[files,info]);
  const hasMedia=files.some(f=>/\.(mp4|mkv|mov|avi|webm|m4v|mpeg|mpg|wmv|ts|mts)$/i.test(f.name));
  useEffect(()=>{mounted.current=true;api('/converter').then(v=>{if(mounted.current)setInfo(v)}).catch(e=>setError(e.message));
    const refresh=()=>api('/converter/jobs').then(v=>{if(mounted.current)setJobs(v.jobs)}).catch(e=>{if(mounted.current)setError(e.message)});
    refresh();const timer=setInterval(refresh,1500);return()=>{mounted.current=false;clearInterval(timer)}},[]);
  useEffect(()=>{if(common.length&&!common.includes(target))setTarget(common[0])},[common,target]);
  function add(items){
    setError('');const incoming=Array.from(items);
    if(incoming.some(f=>!info?.formats?.[ext(f.name)])){setError('Один из форматов пока не поддерживается. Выберите документ, изображение, аудио, видео, таблицу или субтитры.');return}
    if(incoming.some(f=>f.size>2*1024**3)){setError('Один файл должен быть меньше 2 ГБ.');return}
    if(incoming.some(f=>/\.(json|yaml|yml|csv|tsv|html|htm|md|txt)$/i.test(f.name)&&f.size>50*1024**2)){setError('Текстовые файлы и данные — до 50 МБ.');return}
    if(incoming.some(f=>!(/\.(mp3|wav|flac|m4a|aac|ogg|opus|wma|aiff|aif|mp4|mkv|mov|avi|webm|m4v|mpeg|mpg|wmv|ts|mts)$/i.test(f.name))&&f.size>200*1024**2)){setError('Документы и изображения — до 200 МБ.');return}
    const combined=[...files,...incoming].filter((f,i,all)=>all.findIndex(other=>other.name===f.name&&other.size===f.size&&other.lastModified===f.lastModified)===i);
    if(combined.length>12||combined.reduce((n,f)=>n+f.size,0)>4*1024**3){setError('Выберите до 12 файлов, суммарно до 4 ГБ.');return}
    if(!files.length&&incoming.length){const type=ext(incoming[0].name);setTarget(type==='pdf'?'docx':/heic|heif|png|jpg|jpeg|webp|avif|tif|tiff|svg|psd/.test(type)?'jpg':/mp4|mkv|mov|avi|webm/.test(type)?'mp4':/mp3|wav|m4a|flac|ogg|opus/.test(type)?'mp3':type==='json'?'xlsx':type==='yaml'||type==='yml'?'json':'pdf')}
    setFiles(combined);
  }
  async function convert(){
    setSending(true);setError('');try{
      const body=new FormData();files.forEach(f=>body.append('files',f));body.append('options',JSON.stringify({target,options:{...options,merge:target==='pdf'&&options.merge},session_id:attach?sid:null}));
      const job=await api('/converter/jobs',{method:'POST',body});if(!mounted.current)return;
      setJobs(rows=>[job,...rows.filter(r=>r.id!==job.id)]);setFiles([]);
    }catch(e){if(mounted.current)setError(e.message)}finally{if(mounted.current)setSending(false)}
  }
  async function cancel(id){try{const job=await api('/converter/jobs/'+id+'/cancel',{method:'POST',body:'{}'});setJobs(rows=>rows.map(r=>r.id===id?job:r))}catch(e){setError(e.message)}}
  async function saveFile(job,file){
    const index=job.files.indexOf(file);setSaving(job.id+'-'+index);setError('');
    try{const result=await api('/converter/jobs/'+job.id+'/export/'+index,{method:'POST',body:'{}'});setSaved(value=>({...value,[job.id]:result.path}))}
    catch(e){setError(e.message)}finally{setSaving(null)}
  }
  function resultFile(job,file){return <button className="converter-result-file" type="button" title="Сохранить копию в папку Экспорт" key={file.url} disabled={!!saving} onClick={()=>saveFile(job,file)}>{saving===job.id+'-'+job.files.indexOf(file)?<LoaderCircle size={13} className="spin"/>:<Download size={13}/>}<span>{file.name}</span><small>{size(file.bytes)}</small></button>}
  return <section className="file-converter" aria-label="Конвертер файлов">
    <header className="converter-intro"><span className="converter-symbol"><ArrowRightLeft size={22}/></span><div><strong>Один конвертер для ваших файлов</strong><p>Документы, фото, аудио и видео. Бесплатно, на вашем ПК.</p></div><span className={'converter-local '+(!info?.ready?'pending':'')}><ShieldCheck size={13}/>{info?.ready?'Локально':'Подготовка'}</span></header>
    <div className={'converter-drop '+(drag?'drag':'')} onDragOver={e=>{e.preventDefault();e.stopPropagation();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();e.stopPropagation();setDrag(false);add(e.dataTransfer.files)}}>
      <Upload size={25}/><strong>Перетащите файлы сюда</strong><span>или выберите их на компьютере</span><button type="button" className="primary" disabled={!info||sending} onClick={()=>input.current?.click()}>Выбрать файлы</button>
      <small>До 12 файлов · до 2 ГБ каждый · оригиналы сохраняются</small>
      <input ref={input} type="file" multiple hidden accept={Object.keys(info?.formats||{}).map(e=>'.'+e).join(',')} onChange={e=>{add(e.target.files);e.target.value=''}}/>
    </div>
    {!files.length&&<div className="converter-examples"><span>Word ↔ PDF</span><span>HEIC → JPG</span><span>Видео → MP3</span><span>Фото → PDF</span><span>CSV ↔ Excel</span></div>}
    {!!files.length&&<div className="converter-selected">{files.map((f,i)=><div key={f.name+f.size}><Files size={15}/><span title={f.name}>{f.name}</span><small>{size(f.size)}</small><button type="button" disabled={sending} onClick={()=>setFiles(all=>all.filter((_,n)=>n!==i))} aria-label={'Убрать '+f.name}><X size={13}/></button></div>)}</div>}
    {!!files.length&&<div className="converter-form">
      <label className="converter-target">Формат результата<select aria-label="Формат результата" value={target} disabled={sending||!common.length} onChange={e=>setTarget(e.target.value)}>{common.map(format=><option key={format} value={format}>{labels[format]||format.toUpperCase()}</option>)}</select></label>
      {!common.length&&<p className="error-text">У выбранных файлов нет общего формата. Преобразуйте их отдельными пакетами.</p>}
      <details className="converter-options"><summary>Параметры преобразования</summary><div className="converter-options-grid">
        <label>Качество фото и видео<select aria-label="Качество преобразования" value={options.quality} onChange={e=>setOptions(v=>({...v,quality:e.target.value}))}><option value="balanced">Баланс размера и качества</option><option value="high">Выше качество</option><option value="small">Меньше файл</option></select></label>
        <label>Размер фото<select aria-label="Размер фото" value={options.image_size} onChange={e=>setOptions(v=>({...v,image_size:Number(e.target.value)}))}>{[[0,'Исходный'],[4096,'До 4096 px'],[2048,'До 2048 px'],[1024,'До 1024 px']].map(([n,label])=><option key={n} value={n}>{label}</option>)}</select></label>
        {hasMedia&&<label>Высота видео<select aria-label="Высота видео" value={options.video_size} onChange={e=>setOptions(v=>({...v,video_size:Number(e.target.value)}))}><option value="0">Исходная</option><option value="1080">До 1080p</option><option value="720">До 720p</option></select></label>}
      </div><label className="converter-check"><input type="checkbox" checked={options.ocr} onChange={e=>setOptions(v=>({...v,ocr:e.target.checked}))}/>Распознавать текст сканов · русский + английский</label>
        {target==='pdf'&&files.length>1&&<label className="converter-check"><input type="checkbox" checked={options.merge} onChange={e=>setOptions(v=>({...v,merge:e.target.checked}))}/>Объединить результаты в один PDF</label>}
        {sid&&<label className="converter-check"><input type="checkbox" checked={attach} onChange={e=>setAttach(e.target.checked)}/>Добавить результат в файлы текущего чата</label>}
      </details>
      <div className="converter-submit"><span>{files.length} файл(ов) · {size(files.reduce((n,f)=>n+f.size,0))}</span><button type="button" className="primary" disabled={!info?.ready||sending||!common.length} onClick={convert}>{sending?<LoaderCircle size={15} className="spin"/>:<ArrowRightLeft size={15}/>}<span>{sending?'Передаю файлы…':'Преобразовать'}</span></button></div>
    </div>}
    {error&&<p className="converter-error" role="alert">{error}</p>}
    <p className="converter-help">Можно закрыть это окно: обработка продолжится. Нажмите результат, чтобы сохранить копию в «Экспорт», или откройте его папку. PDF → Word со сложной вёрсткой нужно проверить; для сканов включите распознавание. JSON/CSV сохраняет один лист таблицы.</p>
    <div className="converter-history"><header><strong>Мои преобразования</strong><span>{jobs.length}</span></header>
      {!jobs.length&&<p className="converter-empty">Здесь появятся результаты и кнопки скачивания.</p>}
      {(showAll?jobs:jobs.slice(0,5)).map(job=><article className={'converter-job '+job.state} key={job.id}><div className="converter-job-top">
        {job.state==='ready'?<CheckCircle2 size={17}/>:job.state==='working'?<LoaderCircle size={17} className="spin"/>:<Clock3 size={17}/>}
        <div><strong title={job.names.join(', ')}>{job.names[0]}{job.names.length>1?' + '+(job.names.length-1):''}<span> → {job.target.toUpperCase()}</span></strong><small>{job.state==='working'?job.progress:statusNames[job.state]}{job.seconds?' · '+job.seconds.toFixed(1)+' с':''}</small></div>
        {['working','queued'].includes(job.state)&&<button type="button" className="converter-icon" aria-label={'Остановить '+job.names[0]} title="Остановить" onClick={()=>cancel(job.id)}><X size={15}/></button>}
      </div>
      {job.state==='working'&&<div className="converter-progress"><i style={{width:(job.percent||3)+'%'}}/></div>}
      {job.error&&<p className="converter-error">{job.error}</p>}
      {!!job.files?.length&&<div className="converter-results">{job.files.slice(0,4).map(file=>resultFile(job,file))}
        {job.files.length>4&&<details><summary>Ещё файлов: {job.files.length-4}</summary>{job.files.slice(4).map(file=>resultFile(job,file))}</details>}
        {saved[job.id]&&<small className="converter-saved" title={saved[job.id]}>Копия сохранена в папку «Экспорт»</small>}
        <button type="button" className="converter-folder" onClick={()=>api('/converter/jobs/'+job.id+'/folder',{method:'POST',body:JSON.stringify({exported:!!saved[job.id]})}).catch(e=>setError(e.message))}><FolderOpen size={13}/>Открыть папку</button></div>}
      {!!job.warnings?.length&&<details className="converter-notes"><summary>Примечания · {job.warnings.length}</summary>{job.warnings.map(note=><p key={note}>{note}</p>)}</details>}
      </article>)}
      {jobs.length>5&&<button type="button" className="converter-more" onClick={()=>setShowAll(v=>!v)}>{showAll?'Свернуть историю':'Показать ещё · '+(jobs.length-5)}</button>}
    </div>
  </section>;
}
