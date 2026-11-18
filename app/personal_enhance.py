"""Optional, private Windows photo/video enhancement. Never stops the model."""
from __future__ import annotations
import asyncio,concurrent.futures,contextlib,hashlib,json,math,os,pathlib,re,shutil,subprocess,threading,time,urllib.request,uuid,zipfile
from fractions import Fraction
from PIL import Image,ImageOps
import psutil
from aiohttp import web

FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)
ACTIVE={'queued','preparing','waiting','upscaling','interpolating','encoding','verifying'}
ASSETS={
 'esrgan':{'version':'20220424','bytes':45474481,'url':'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip','exe':'realesrgan-ncnn-vulkan.exe'},
 'rife':{'version':'20221029','bytes':431540241,'url':'https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip','exe':'rife-ncnn-vulkan.exe'},
}

def atomic_json(path,value):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix('.new');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)

class Cancelled(Exception):pass

class EnhanceTools:
 def __init__(self,root):
  self.root=pathlib.Path(root);self.base=self.root/'runtime/personal-enhance';self.lock=threading.Lock();self.state={};self.verified={}
 def folder(self,name):return self.base/(name+'-'+ASSETS[name]['version'])
 def executable(self,name):return self.folder(name)/ASSETS[name]['exe']
 def ready(self,name):
  folder=self.folder(name)
  try:
   manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
   if manifest['version']!=ASSETS[name]['version'] or not manifest['files'] or not self.executable(name).is_file():return False
   required=['models/realesrgan-x4plus.bin','models/realesrgan-x4plus.param','models/realesrgan-x4plus-anime.bin','models/realesrgan-x4plus-anime.param'] if name=='esrgan' else ['rife-v4.6/flownet.bin','rife-v4.6/flownet.param']
   if name=='rife' and not (folder/required[0]).is_file():required=['models/'+p for p in required]
   if not all((folder/p).is_file() for p in required):return False
   stamps=[]
   for item in manifest['files']:
    path=(folder/item['path']).resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file() or path.stat().st_size!=item['bytes']:return False
    stamps.append((item['path'],path.stat().st_size,path.stat().st_mtime_ns))
   stamp=tuple(stamps)
   if self.verified.get(name)!=stamp:
    for item in manifest['files']:
     with (folder/item['path']).open('rb') as stream:
      if hashlib.file_digest(stream,'sha256').hexdigest()!=item['sha256']:return False
    self.verified[name]=stamp
   return True
  except (OSError,ValueError,KeyError,TypeError):return False
 def snapshot(self):return {name:{'ready':self.ready(name),'bytes':spec['bytes'],**self.state.get(name,{})} for name,spec in ASSETS.items()}
 @contextlib.contextmanager
 def install_lock(self,cancel):
  lock=self.root/'.cache/enhance/install.lock';lock.parent.mkdir(parents=True,exist_ok=True)
  with lock.open('a+b') as stream:
   if os.name!='nt':yield;return
   import msvcrt
   stream.write(b'0');stream.flush()
   while True:
    if cancel and cancel.is_set():raise Cancelled()
    stream.seek(0)
    try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);break
    except OSError:
     if cancel:cancel.wait(.3)
     else:time.sleep(.3)
   try:yield
   finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
 def ensure(self,name,cancel=None):
  with self.lock,self.install_lock(cancel):
   if self.ready(name):return
   spec=ASSETS[name];folder=self.folder(name);folder.mkdir(parents=True,exist_ok=True)
   archive=self.root/'.cache/enhance'/(name+'-'+spec['version']+'.zip');archive.parent.mkdir(parents=True,exist_ok=True)
   part=archive.with_suffix('.part')
   for attempt in range(3):
    if cancel and cancel.is_set():raise Cancelled()
    have=part.stat().st_size if part.exists() else 0
    if archive.is_file() and archive.stat().st_size==spec['bytes']:break
    if have>=spec['bytes']:part.unlink();have=0
    headers={'User-Agent':'FreedomGPT-local-enhance'}
    if have:headers['Range']='bytes='+str(have)+'-'
    self.state[name]={'state':'downloading','downloaded':have,'percent':round(have/spec['bytes']*100)}
    try:
     with urllib.request.urlopen(urllib.request.Request(spec['url'],headers=headers),timeout=40) as response:
      append=have and response.status==206
      if response.status not in (200,206):raise ValueError('Сервер не отдал модуль улучшения.')
      if not append:have=0
      with part.open('ab' if append else 'wb') as stream:
       while True:
        if cancel and cancel.is_set():raise Cancelled()
        chunk=response.read(1024*512)
        if not chunk:break
        have+=len(chunk)
        if have>spec['bytes']:raise ValueError('Размер модуля отличается от официального релиза.')
        stream.write(chunk);self.state[name]={'state':'downloading','downloaded':have,'percent':round(have/spec['bytes']*100,1)}
     if have!=spec['bytes']:raise OSError('Incomplete module download')
     os.replace(part,archive);break
    except Cancelled:raise
    except Exception:
     if attempt==2:
      self.state[name]={'state':'error','error':'Загрузка прервалась. Повторное нажатие продолжит загрузку.'}
      raise ValueError('Не удалось скачать модуль. Частичная загрузка сохранена; можно продолжить позже.') from None
   if not archive.is_file():raise ValueError('Модуль не скачан.')
   self.state[name]={'state':'installing','percent':100}
   records=[]
   with zipfile.ZipFile(archive) as source:
    for entry in source.infolist():
     relative=pathlib.PurePosixPath(entry.filename)
     # The upstream archive has one enclosing directory; keep only executables,
     # libraries, notices and the selected models, never arbitrary archive paths.
     parts=relative.parts
     if not parts or entry.is_dir():continue
     if '..' in parts or relative.is_absolute() or any(':' in part for part in parts):raise ValueError('Некорректный путь в архиве модуля.')
     if len(parts)>1 and parts[0].startswith(('realesrgan-ncnn-','rife-ncnn-')):parts=parts[1:]
     rel=pathlib.Path(*parts);lower=rel.as_posix().lower()
     wanted=rel.name==spec['exe'] or rel.suffix.lower()=='.dll' or any(word in rel.name.lower() for word in ['license','notice','readme'])
     if name=='esrgan':wanted=wanted or (lower.startswith('models/') and any(model in lower for model in ['realesrgan-x4plus.','realesrgan-x4plus-anime.']))
     else:wanted=wanted or lower.startswith('rife-v4.6/') or lower.startswith('models/rife-v4.6/')
     if not wanted:continue
     target=(folder/rel).resolve()
     if not target.is_relative_to(folder.resolve()) or entry.file_size>300*1024**2:raise ValueError('Некорректный файл модуля.')
     target.parent.mkdir(parents=True,exist_ok=True)
     with source.open(entry) as reader,target.open('wb') as writer:shutil.copyfileobj(reader,writer)
     with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
     records.append({'path':rel.as_posix(),'bytes':target.stat().st_size,'sha256':digest})
   if not self.executable(name).is_file():raise ValueError('В архиве отсутствует исполняемый файл.')
   model='models/realesrgan-x4plus.bin' if name=='esrgan' else 'rife-v4.6/flownet.bin'
   if name=='rife' and not (folder/model).is_file():model='models/'+model
   if not (folder/model).is_file():raise ValueError('В архиве отсутствует модель улучшения.')
   with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
   atomic_json(folder/'manifest.json',{'version':spec['version'],'origin':spec['url'],'archive_bytes':spec['bytes'],'archive_sha256':digest,'verification':'Official HTTPS release, exact published asset size and ZIP CRC; upstream has no published digest. Local SHA256 records retained.','files':records})
   self.state[name]={'state':'ready','percent':100}
 def ffmpeg(self,name):
  candidates=[self.root/'runtime/ffmpeg/bin'/(name+'.exe'),self.root.parent/'local-llm/huihui-qwen3.8-coder/hermes-runtime/tools/ffmpeg-9.0.1-win32-x64/bin'/(name+'.exe')]
  return next((p for p in candidates if p.is_file()),pathlib.Path(shutil.which(name) or ''))

class PersonalEnhance:
 def __init__(self,root,enabled=False):
  self.root=pathlib.Path(root).resolve();self.enabled=bool(enabled and os.name=='nt');self.tools=EnhanceTools(self.root)
  self.folder=self.root/'data/enhance-jobs';self.folder.mkdir(parents=True,exist_ok=True)
  self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='FreedomEnhance')
  self.lock=threading.RLock();self.jobs={};self.cancel_events={};self.process=None;self.closing=threading.Event();self.app=None;self.loop=None
  self.resolver=None;self.on_complete=None;self.gate=lambda:'';self.current=None;self.installing=False
  for p in sorted(self.folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
   try:
    job=json.loads(p.read_text(encoding='utf-8'))
    if job.get('state') in ACTIVE:job.update(state='interrupted',error='Улучшение было прервано закрытием программы. Оригинал сохранён.')
    self.jobs[job['id']]=job
   except (OSError,ValueError,KeyError):pass
 def public(self,job):
  with self.lock:job=dict(job)
  result={k:v for k,v in job.items() if k not in {'source_path','output_path','before_path','log_path','temp_path','input_stat','dedupe'}}
  if job.get('state')=='complete':result['url']='/api/enhance/files/'+job['id']
  result['before_url']='/api/enhance/files/'+job['id']+'/before' if job.get('before_path') else job['source_url']
  return result
 def save(self,job,**change):
  with self.lock:job.update(change,updated=time.time());atomic_json(self.folder/(job['id']+'.json'),job)
 def snapshot(self):
  with self.lock:jobs=sorted(self.jobs.values(),key=lambda v:v['created'],reverse=True)[:30]
  return {'enabled':self.enabled,'offline':True,'tools':self.tools.snapshot(),'installing':self.installing,'jobs':[self.public(j) for j in jobs], 'gpu_busy':bool(self.app and self.app.get('enhance_gpu_busy'))}
 def has_active(self):
  with self.lock:return any(j['state'] in ACTIVE for j in self.jobs.values())
 def _capture(self,args,timeout=20):
  p=subprocess.run(list(map(str,args)),capture_output=True,timeout=timeout,creationflags=FLAGS)
  if p.returncode:raise ValueError('Не удалось прочитать медиафайл.')
  return p.stdout
 def inspect(self,source):
  path=pathlib.Path(source['path']).resolve()
  if not path.is_file() or path.stat().st_size>2*1024**3:raise ValueError('Файл отсутствует или превышает 2 ГБ.')
  suffix=path.suffix.lower()
  if suffix in {'.png','.jpg','.jpeg','.webp','.bmp','.tiff','.tif'}:
   with Image.open(path) as image:
    if getattr(image,'n_frames',1)>1:raise ValueError('Анимированные изображения пока не поддерживаются. Используйте видео.')
    width,height=image.size
    if image.getexif().get(274) in (5,6,7,8):width,height=height,width
    if width*height>64_000_000:raise ValueError('Исходное изображение превышает 64 мегапикселя.')
   return {'kind':'image','width':width,'height':height,'bytes':path.stat().st_size}
  if suffix not in {'.mp4','.webm','.mov','.mkv','.m4v','.avi'}:raise ValueError('Поддерживаются фото PNG/JPEG/WebP/BMP/TIFF и готовые видео MP4/WebM/MOV/MKV/AVI.')
  probe=self.tools.ffmpeg('ffprobe')
  if not probe.is_file():raise ValueError('FFprobe не найден. Требуется локальный FFmpeg.')
  data=json.loads(self._capture([probe,'-v','error','-show_streams','-show_format','-of','json',path]))
  stream=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),None)
  if not stream:raise ValueError('В файле нет видеодорожки.')
  if stream.get('color_transfer') in {'smpte2084','arib-std-b67'}:raise ValueError('Для этой версии сначала экспортируйте HDR-видео в SDR. Исходный файл сохранён.')
  width,height=int(stream['width']),int(stream['height']);duration=float(stream.get('duration') or data.get('format',{}).get('duration') or 0)
  try:fps=Fraction(stream.get('avg_frame_rate') or stream.get('r_frame_rate'))
  except (ValueError,ZeroDivisionError,TypeError):raise ValueError('Не удалось определить частоту кадров.')
  rotation=next((int(s.get('rotation',0)) for s in stream.get('side_data_list',[]) if 'rotation' in s),0)
  if abs(rotation)%180==90:width,height=height,width
  if not 0<duration<=300 or not 1<=float(fps)<=120:raise ValueError('Для этой версии доступны ролики до 5 минут и 120 кадров/с.')
  frames=int(stream.get('nb_frames') or math.ceil(duration*float(fps)))
  packets=json.loads(self._capture([probe,'-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts_time,duration_time','-of','json',path],45)).get('packets',[])
  points=[(float(p['pts_time']),float(p.get('duration_time') or 1/float(fps))) for p in packets if p.get('pts_time') not in (None,'N/A')]
  first=min((p[0] for p in points),default=float(stream.get('start_time') or 0))
  offset=first-float(data.get('format',{}).get('start_time') or 0)
  if points:
   duration=max(max(p[0]+(p[1] if p[1]>0 else 1/float(fps)) for p in points)-first,duration-offset)
   frames=max(frames,len(points))
  if duration>300:raise ValueError('Для этой версии доступны ролики до 5 минут.')
  if frames>18000:raise ValueError('Слишком много кадров для одного задания.')
  sar=Fraction(stream.get('sample_aspect_ratio','1:1').replace(':','/')) if stream.get('sample_aspect_ratio') not in (None,'N/A','0:1') else Fraction(1)
  if sar!=1:raise ValueError('Сначала экспортируйте видео с квадратным пикселем. Анаморфные ролики пока не поддерживаются.')
  return {'kind':'video','width':width,'height':height,'duration':duration,'audio_offset':offset,'fps':str(fps),'frames':frames,'bytes':path.stat().st_size,'audio':any(s.get('codec_type')=='audio' for s in data['streams'])}
 def start(self,value):
  if not self.enabled:raise ValueError('Улучшение доступно только в этой Windows-сборке.')
  url=str(value.get('url',''));source=self.resolver(url);info=self.inspect(source)
  scale=value.get('scale',2);profile=value.get('profile','photo');smooth=value.get('smooth',False);preview=value.get('preview',False)
  if type(scale) is not int or scale not in (2,4) or profile not in ('photo','illustration') or type(smooth) is not bool or type(preview) is not bool:raise ValueError('Некорректные параметры улучшения.')
  if info['kind']=='image' and smooth:raise ValueError('Повышение плавности доступно для видео.')
  width=min(512,info['width']) if preview and info['kind']=='image' else info['width'];height=min(512,info['height']) if preview and info['kind']=='image' else info['height']
  if info['kind']=='image' and width*height*16>160_000_000:raise ValueError('Для полного улучшения выберите исходник до 10 мегапикселей. Можно проверить центральный фрагмент кнопкой «Проба».')
  if info['kind']=='video' and info['width']*info['height']*scale**2>3840*2160:raise ValueError('В этой версии видео можно увеличить максимум до 4K. Выберите ×2 или меньший исходник.')
  if max(width,height)*scale>16384 or width*height*scale**2>64_000_000:raise ValueError('Результат превышает 64 мегапикселя или 16384 пикселя по стороне.')
  sid=str(value.get('sid') or source.get('sid') or '')[:128];request_id=str(value.get('request_id') or uuid.uuid4().hex)[:100]
  stat=pathlib.Path(source['path']).stat();key=[str(source['path']),stat.st_size,stat.st_mtime_ns,scale,profile,smooth,preview]
  with self.lock:
   for job in self.jobs.values():
    if job.get('request_id')==request_id:
     if job.get('dedupe')!=key or job.get('sid')!=sid:raise ValueError('Параметры этого запроса изменились. Запустите новое улучшение.')
     return self.public(job)
    if job.get('dedupe')==key and job.get('sid')==sid and job['state'] in ACTIVE:return self.public(job)
   if sum(j['state'] in ACTIVE for j in self.jobs.values())>=8:raise ValueError('В очереди уже восемь улучшений. Дождитесь завершения или отмените лишние.')
   ident=uuid.uuid4().hex;output=self.root/'output/enhanced'/ident;output.mkdir(parents=True)
   job={'id':ident,'request_id':request_id,'dedupe':key,'source_url':url,'source_path':str(source['path']),'source_name':pathlib.Path(source['path']).name,'sid':sid,**info,
    'scale':scale,'profile':profile,'smooth':smooth,'preview':preview,'width':width*scale,'height':height*scale,'source_width':info['width'],'source_height':info['height'],
    'state':'queued','progress':0,'created':time.time(),'output_path':str(output/('enhanced-x'+str(scale)+('.png' if info['kind']=='image' else '.mp4'))),
    'input_stat':[stat.st_size,stat.st_mtime_ns],'temp_path':str(self.root/'.tmp/enhance'/ident),'log_path':str(self.root/'logs'/('enhance-'+ident+'.log'))}
   self.jobs[ident]=job;self.cancel_events[ident]=threading.Event();self.save(job);self.pool.submit(self.work,job)
   return self.public(job)
 def _stopped(self,job):return self.closing.is_set() or self.cancel_events[job['id']].is_set()
 def _check(self,job):
  if self._stopped(job):raise Cancelled()
 def _wait(self,job):
  while True:
   self._check(job);reason=self.gate()
   if not reason:return
   self.save(job,state='waiting',reason=reason)
   self.cancel_events[job['id']].wait(1)
 def _flag(self,value):
  if self.app is not None:self.app['enhance_gpu_busy']=value
 def _terminate(self,process):
  if process and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=6)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=6)
 def run(self,args,job,phase,gpu=False,progress=None):
  while True:
   self._check(job)
   if gpu:self._wait(job)
   self.save(job,state=phase,reason='')
   with open(job['log_path'],'ab') as log:
    child=subprocess.Popen(list(map(str,args)),cwd=self.root,stdout=log,stderr=log,creationflags=FLAGS)
    self.process=child;started=time.monotonic();yielded=False
    if gpu:self._flag(True)
    try:
     while child.poll() is None:
      self._check(job)
      if time.monotonic()-started>600:raise ValueError('Модуль не завершил шаг за 10 минут. Оригинал сохранён.')
      if progress:progress()
      if gpu and self.gate():yielded=True;break
      self.cancel_events[job['id']].wait(.2)
     if not yielded and child.returncode:
      text=pathlib.Path(job['log_path']).read_bytes()[-3000:].decode('utf-8','replace')
      if re.search(r'out of memory|outofdevicememory|failed to allocate|vkAllocateMemory',text,re.I):raise MemoryError('Недостаточно видеопамяти для выбранного режима.')
      raise ValueError('Модуль не смог обработать файл. Оригинал сохранён. Попробуйте другой профиль или меньший исходник.')
    finally:
     self._terminate(child);self.process=None
     if gpu:self._flag(False)
   if not yielded:return
   self.save(job,state='waiting',reason='Приоритет у текущей задачи агента. Улучшение продолжится автоматически.')
 def _enhance_image(self,source,target,job,index=0,total=1):
  with Image.open(source) as image:pixels=image.width*image.height;source_size=image.size
  if psutil.virtual_memory().available<pixels*128+job['width']*job['height']*12+256*1024**2:raise ValueError('Недостаточно свободной оперативной памяти. Попробуйте пробный фрагмент или меньший исходник. Модель остаётся запущенной.')
  model='realesrgan-x4plus-anime' if job['profile']=='illustration' else 'realesrgan-x4plus'
  native=pathlib.Path(job['temp_path'])/('native-'+str(index)+'.png')
  offset=pathlib.Path(job['log_path']).stat().st_size if pathlib.Path(job['log_path']).is_file() else 0
  def tile_progress():
   with pathlib.Path(job['log_path']).open('rb') as stream:
    stream.seek(0,2);end=stream.tell();stream.seek(max(offset,end-8000));text=stream.read().decode('utf-8','replace')
   values=re.findall(r'(?m)^\s*(\d+(?:[.,]\d+)?)%\s*$',text)
   if values:
    value=round(8+(index+min(100,float(values[-1].replace(',','.')))/100)/total*(59 if job['smooth'] else 78),1)
    if abs(value-job.get('progress',0))>=.8:self.save(job,progress=value,processed_frames=index,total_frames=total)
  for tile in (64,32):
   try:
    self.run([self.tools.executable('esrgan'),'-i',source,'-o',native,'-m',self.tools.folder('esrgan')/'models','-n',model,'-s','4','-t',str(tile),'-j','1:1:1','-g','0','-f','png'],job,'upscaling',gpu=True,progress=tile_progress)
    break
   except MemoryError:
    native.unlink(missing_ok=True)
    if tile==32:raise ValueError('Не хватает видеопамяти даже для малого блока. Закройте лишние GPU-программы или повторите позже.')
  with Image.open(native) as image:
   if image.size!=(source_size[0]*4,source_size[1]*4):raise ValueError('Нейросеть вернула неверный размер изображения. Оригинал сохранён.')
   image.load()
   if image.size!=(job['width'],job['height']):image=image.resize((job['width'],job['height']),Image.Resampling.LANCZOS)
   image.save(target,format='PNG')
  native.unlink(missing_ok=True)
  self.save(job,progress=round(8+(index+1)/total*(59 if job['smooth'] else 78),1),processed_frames=index+1,total_frames=total)
 def _video_times(self,source,job):
  data=json.loads(self._capture([self.tools.ffmpeg('ffprobe'),'-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',source],60))
  times=[float(frame['best_effort_timestamp_time']) for frame in data.get('frames',[]) if 'best_effort_timestamp_time' in frame]
  if times:
   first=times[0];times=[max(0,t-first) for t in times]
  if job['preview']:times=[t for t in times if t<3]
  return times
 def _video(self,job,temp):
  source=pathlib.Path(job['source_path']);duration=min(3,job['duration']) if job['preview'] else job['duration']
  ffmpeg=self.tools.ffmpeg('ffmpeg');original=temp/'input';enhanced=temp/'frames';original.mkdir();enhanced.mkdir()
  times=self._video_times(source,job)
  if not times:raise ValueError('Не удалось прочитать временные метки кадров.')
  estimate=len(times)*(job['source_width']*job['source_height']+job['width']*job['height'])*4+1024**3
  if shutil.disk_usage(self.root).free<estimate:raise ValueError('Не хватает места для временных кадров. Выберите пробный фрагмент или меньший размер.')
  self.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-threads','2','-i',source,'-t',str(duration),'-an','-fps_mode','passthrough',original/'%08d.png'],job,'preparing')
  frames=sorted(original.glob('*.png'))
  if not frames:raise ValueError('Не удалось извлечь кадры.')
  times=times[:len(frames)]
  if len(times)!=len(frames):raise ValueError('Количество кадров не совпало с временными метками. Оригинал сохранён.')
  if job['preview']:
   before=pathlib.Path(job['output_path']).parent/'before.mp4'
   self.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-i',source,'-t',str(duration),'-map','0:v:0','-map','0:a:0?','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-threads','2',before],job,'preparing')
   self.save(job,before_path=str(before))
  for index,frame in enumerate(frames):
   self._check(job);self._enhance_image(frame,enhanced/frame.name,job,index,len(frames));frame.unlink()
  durations=[max(.000001,times[i+1]-times[i]) for i in range(len(times)-1)]+[max(.000001,duration-times[-1])]
  if job['smooth'] and len(frames)>1:
   self._wait(job);target=temp/'smooth';target.mkdir();count=len(frames)*2-1
   model=self.tools.folder('rife')/'rife-v4.6'
   if not model.is_dir():model=self.tools.folder('rife')/'models/rife-v4.6'
   self.run([self.tools.executable('rife'),'-i',enhanced,'-o',target,'-m',model,'-n',str(count),'-g','0','-j','1:1:1','-f','%08d.png'],job,'interpolating',gpu=True,progress=lambda:self.save(job,progress=round(68+min(count,len(list(target.glob('*.png'))))/count*19,1)))
   rendered=sorted(target.glob('*.png'))
   if len(rendered)!=count:raise ValueError('Модуль плавности создал неполный набор кадров.')
   new_durations=[]
   for value in durations[:-1]:new_durations.extend([value/2,value/2])
   durations=new_durations+[durations[-1]]
  else:rendered=sorted(enhanced.glob('*.png'))
  listing=temp/'frames.ffconcat';lines=['ffconcat version 1.0']
  # A final identical anchor closes the last frame at its real end time.
  # Otherwise the image demuxer's one-microsecond packet truncates that frame.
  durations[-1]=max(.000001,durations[-1]-.000001)
  for frame,span in zip(rendered,durations):
   relative=frame.relative_to(temp).as_posix();lines+=['file '+"'"+relative+"'",'option framerate 1000000','duration '+format(span,'.9f')]
  lines+=['file '+"'"+rendered[-1].relative_to(temp).as_posix()+"'",'option framerate 1000000']
  listing.write_text('\n'.join(lines)+'\n',encoding='utf-8')
  self.save(job,progress=89,output_frames=len(rendered)+1,output_duration=duration)
  self.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-f','concat','-safe','0','-i',listing,'-itsoffset',str(-job.get('audio_offset',0)),'-i',source,'-map','0:v:0','-map','1:a:0?','-t',str(duration),'-fps_mode','vfr','-enc_time_base','1:1000000','-c:v','libx264','-bf','0','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-map_metadata','-1','-metadata:s:v:0','rotate=0','-video_track_timescale','1000000','-movflags','+faststart','-threads','2',job['output_path']],job,'encoding')
  data=json.loads(self._capture([self.tools.ffmpeg('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',job['output_path']]))
  video=next(s for s in data['streams'] if s.get('codec_type')=='video');actual=float(data['format']['duration'])
  if (int(video['width']),int(video['height']))!=(job['width'],job['height']) or abs(actual-duration)>.025:raise ValueError('Проверка размера или длительности результата не прошла.')
  if job['audio'] and not any(s.get('codec_type')=='audio' for s in data['streams']):raise ValueError('Не удалось сохранить звуковую дорожку.')
  self.save(job,result_fps=video.get('avg_frame_rate'),output_duration=actual)
 def work(self,job):
  self.current=job['id'];temp=pathlib.Path(job['temp_path'])
  try:
   self._check(job);self.save(job,state='preparing',reason='Проверяем локальные модули')
   self.tools.ensure('esrgan',self.cancel_events[job['id']])
   if job['smooth']:self.tools.ensure('rife',self.cancel_events[job['id']])
   self._check(job);source=pathlib.Path(job['source_path']);stat=source.stat()
   if [stat.st_size,stat.st_mtime_ns]!=job['input_stat']:raise ValueError('Исходный файл изменился. Откройте его заново перед улучшением.')
   with source.open('rb') as stream:self.save(job,source_sha256=hashlib.file_digest(stream,'sha256').hexdigest())
   temp.mkdir(parents=True,exist_ok=False)
   if job['kind']=='image':
    if shutil.disk_usage(self.root).free<1024**3+job['width']*job['height']*32:raise ValueError('Недостаточно свободного места для результата.')
    prepared=temp/'source.png'
    with Image.open(source) as raw:
     image=ImageOps.exif_transpose(raw);image=image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
     if job['preview']:
      w=min(512,image.width);h=min(512,image.height);left=(image.width-w)//2;top=(image.height-h)//2;image=image.crop((left,top,left+w,top+h))
      before=pathlib.Path(job['output_path']).parent/'before.png';image.save(before);self.save(job,before_path=str(before))
     image.save(prepared)
    self._enhance_image(prepared,job['output_path'],job)
    with Image.open(job['output_path']) as image:
     image.verify()
   else:self._video(job,temp)
   self._check(job);self.save(job,state='verifying',progress=96)
   with source.open('rb') as stream:
    if hashlib.file_digest(stream,'sha256').hexdigest()!=job['source_sha256']:raise ValueError('Исходник изменился во время обработки; результат не принят.')
   target=pathlib.Path(job['output_path'])
   if not target.is_file() or not target.stat().st_size:raise ValueError('Результат не сохранён.')
   with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
   self.save(job,state='complete',progress=100,finished=time.time(),bytes=target.stat().st_size,sha256=digest,reason='')
   if self.on_complete:
    try:self.on_complete(dict(job))
    except Exception:self.save(job,presentation_error='Файл готов. Если он не появился в чате, скачайте его из окна улучшения.')
  except Cancelled:self.save(job,state='cancelled',reason='',finished=time.time())
  except Exception as exc:self.save(job,state='error',reason='',error=str(exc)[:600],finished=time.time())
  finally:
   self._flag(False);self.current=None
   base=(self.root/'.tmp/enhance').resolve()
   if re.fullmatch('[a-f0-9]{32}',job['id']) and temp.exists() and not temp.is_symlink() and temp.resolve().is_relative_to(base):
    with contextlib.suppress(OSError):shutil.rmtree(temp)
 def cancel(self,ident):
  with self.lock:
   job=self.jobs.get(ident)
   if not job:raise ValueError('Задание не найдено.')
   if job['state'] in ACTIVE:
    self.cancel_events[ident].set()
    if job['state']=='queued':self.save(job,state='cancelled',finished=time.time())
   return self.public(job)
 async def close(self):
  self.closing.set()
  for event in self.cancel_events.values():event.set()
  self._terminate(self.process);self.pool.shutdown(wait=False,cancel_futures=True)
 def register(self,app,resolver,completed,gate):
  self.app=app;self.resolver=resolver;self.gate=gate
  app['enhance_service']=self
  def done(job):
   if self.loop and not self.loop.is_closed():asyncio.run_coroutine_threadsafe(completed(job),self.loop)
  self.on_complete=done
  async def status(request):return web.json_response(self.snapshot())
  async def source(request):return web.json_response(await asyncio.to_thread(self.inspect,self.resolver(request.query.get('url',''))))
  async def start(request):
   self.loop=asyncio.get_running_loop();return web.json_response(await asyncio.to_thread(self.start,await request.json()))
  async def cancel(request):return web.json_response(self.cancel(request.match_info['job']))
  async def file(request):
   job=self.jobs.get(request.match_info['job'])
   before=request.path.endswith('/before')
   if not job or (not before and job.get('state')!='complete'):raise web.HTTPNotFound()
   path=pathlib.Path(job.get('before_path' if before else 'output_path','')).resolve()
   if not path.is_file() or not path.is_relative_to((self.root/'output/enhanced'/job['id']).resolve()):raise web.HTTPNotFound()
   return web.FileResponse(path,headers={'Content-Disposition':'inline; filename="'+path.name+'"'})
  if self.enabled:
   app.router.add_get('/api/enhance/status',status);app.router.add_get('/api/enhance/source',source);app.router.add_post('/api/enhance/jobs',start)
   app.router.add_post('/api/enhance/jobs/{job}/cancel',cancel);app.router.add_get('/api/enhance/files/{job}',file);app.router.add_get('/api/enhance/files/{job}/before',file)
