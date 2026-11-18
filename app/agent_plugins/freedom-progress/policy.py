"""Evidence-based replay limits, independent of a model's claim of progress."""
import ast,contextlib,hashlib,json,pathlib,re,shlex,sqlite3,threading,time,uuid

READ_TOOLS={'read_file','search_files','session_search','skill_view','skills_list','web_search','web_extract','terminal','execute_code'}
VOLATILE={'duration_seconds','duration_ms','execution_count','updated_at','created_at','timestamp','sequence','revision','epoch','presentation_epoch','frame','screenshot_path','screenshot_url','navigation_attempts'}
SID=re.compile(r'^[A-Za-z0-9_-]{1,140}$')

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode('utf-8',errors='surrogatepass')).hexdigest()

def parsed_result(result):
 if isinstance(result,dict):return result
 text=str(result or '').strip()
 if text.startswith('<untrusted_tool_result'):
  start=text.find('\n{');end=text.rfind('}')
  if start>=0 and end>start:text=text[start+1:end+1]
 try:return json.JSONDecoder().raw_decode(text)[0]
 except (ValueError,TypeError):return {'text':text}

def stable(value):
 if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in VOLATILE}
 if isinstance(value,list):return [stable(v) for v in value]
 return value

def signature(tool,args):
 cleaned={k:v for k,v in args.items() if k not in {'timeout','background','notify','notify_on_complete','yield_time_ms'}}
 for key in ['command','code']:
  if isinstance(cleaned.get(key),str):
   cleaned[key]=cleaned[key].strip()
   if key=='code':
    try:cleaned[key]=ast.dump(ast.parse(cleaned[key]),include_attributes=False)
    except (SyntaxError,ValueError):pass
 return digest([tool,cleaned])

def evidence(args):
 """Only actual changes to referenced local files permit an unchanged retry."""
 values=[]
 def walk(item):
  if isinstance(item,dict):
   for v in item.values():walk(v)
  elif isinstance(item,list):
   for v in item:walk(v)
  elif isinstance(item,str):values.append(item)
 walk(args);candidates=[]
 base=args.get('workdir') or args.get('cwd') or args.get('_freedom_cwd')
 for value in values:
  candidates.append(value.strip('"\''))
  candidates.extend(re.findall(r'''[A-Za-z]:[\\/][^"'\r\n<>|;]+''',value))
  try:candidates.extend(token.strip('"\'') for token in shlex.split(value,posix=False))
  except ValueError:pass
 files={}
 for value in candidates:
  # Never probe UNC, device paths or URLs while classifying a tool call.
  if len(value)>1000 or value.startswith(('\\','//')) or '://' in value:continue
  if not re.match(r'^[A-Za-z]:[\\/]',value):
   if not base or not pathlib.Path(value).suffix or value.startswith('-'):continue
   value=str(pathlib.Path(base)/value)
  if not re.match(r'^[A-Za-z]:[\\/]',value):continue
  path=pathlib.Path(re.sub(r'\\{2,}',lambda m:'\\',value))
  try:
   if path.is_file():
    stat=path.stat();files[str(path.resolve()).casefold()]=digest(path.read_bytes().hex()) if stat.st_size<=2*1024**2 else [stat.st_size,stat.st_mtime_ns]
   elif path.suffix:files[str(path).casefold()]=None
  except (OSError,ValueError):continue
  if len(files)>=8:break
 return digest(files)

def failure(tool,data):
 code=data.get('exit_code',data.get('returncode'))
 failed=(isinstance(code,int) and code!=0) or data.get('success') is False or bool(data.get('error')) or data.get('not_found') is True
 stderr=str(data.get('stderr') or '')
 if tool in {'browser_exec','execute_code'} and re.search(r'Traceback \(most recent call last\)|(?:Error|Exception):',stderr):failed=True
 if tool=='web_extract' and data.get('results'):failed=all(r.get('error') for r in data['results'])
 if not failed:return False,''
 detail=str(data.get('error') or stderr or data.get('output') or data.get('text') or code)
 lines=[line.strip() for line in detail.splitlines() if line.strip()]
 cause=next((line for line in reversed(lines) if re.search(r'Error:|Exception:|not found|не найден|403|429|permission|denied|timed? out|timeout',line,re.I)),lines[-1] if lines else str(code))
 cause=re.sub(r'\b(?:0x[\da-f]+|\d{10,})\b','<id>',cause,flags=re.I)
 return True,digest([tool,cause[:350]])

class Ledger:
 def __init__(self,folder):
  self.folder=pathlib.Path(folder);self.folder.mkdir(parents=True,exist_ok=True);self.requests=self.folder/'requests';self.requests.mkdir(exist_ok=True)
  self.db_path=self.folder/'calls.sqlite';self.lock=threading.RLock()
  with self.db() as db:db.executescript('''
   CREATE TABLE IF NOT EXISTS calls(sid TEXT,key TEXT,evidence TEXT,turn TEXT,failed INTEGER,repeats INTEGER,result_hash TEXT,background TEXT,updated REAL,PRIMARY KEY(sid,key));
   CREATE TABLE IF NOT EXISTS budgets(sid TEXT,turn TEXT,violations INTEGER DEFAULT 0,PRIMARY KEY(sid,turn));
   CREATE TABLE IF NOT EXISTS causes(sid TEXT,turn TEXT,cause TEXT,count INTEGER,PRIMARY KEY(sid,turn,cause));
   CREATE TABLE IF NOT EXISTS epochs(sid TEXT PRIMARY KEY,revision INTEGER);
  ''')
 @contextlib.contextmanager
 def db(self):
  db=sqlite3.connect(self.db_path,timeout=3);db.row_factory=sqlite3.Row
  try:
   with db:yield db
  finally:db.close()
 def violation(self,db,sid,turn,tool,reason):
  db.execute('INSERT INTO budgets VALUES(?,?,1) ON CONFLICT(sid,turn) DO UPDATE SET violations=violations+1',(sid,turn))
  count=db.execute('SELECT violations FROM budgets WHERE sid=? AND turn=?',(sid,turn)).fetchone()[0]
  if count>=4 and SID.fullmatch(sid):
   target=self.requests/(sid+'.json');temporary=target.with_suffix('.'+uuid.uuid4().hex+'.new')
   temporary.write_text(json.dumps({'sid':sid,'turn_id':turn,'created':time.time(),'tool':tool,'reason':reason,'count':count}),encoding='utf-8');temporary.replace(target)
  return count
 def repaired(self,db,sid,turn):
  db.execute('DELETE FROM budgets WHERE sid=? AND turn=?',(sid,turn))
  db.execute('DELETE FROM causes WHERE sid=? AND turn=?',(sid,turn))
  request=self.requests/(sid+'.json')
  try:
   if json.loads(request.read_text(encoding='utf-8')).get('turn_id')==turn:request.unlink(missing_ok=True)
  except FileNotFoundError:pass
 def note_file_change(self,sid,args,before):
  path=str(args.get('path') or '')
  source_suffixes={'.py','.js','.jsx','.ts','.tsx','.mjs','.html','.css','.rs','.go','.c','.cpp','.h','.java','.cs','.json','.toml','.yaml','.yml','.csproj'}
  if pathlib.Path(path).suffix.lower() in source_suffixes and before!=evidence(args):
   self.note_source_change(sid)
 def note_source_change(self,sid):
  with self.lock,self.db() as db:db.execute('INSERT INTO epochs VALUES(?,1) ON CONFLICT(sid) DO UPDATE SET revision=revision+1',(sid,))
 def proof(self,db,sid,args):
  result=evidence(args)
  # A test command may name only python.exe, while importing changed sources.
  # Include the observed source revision even when executable/file evidence exists.
  row=db.execute('SELECT revision FROM epochs WHERE sid=?',(sid,)).fetchone()
  return digest([result,row[0] if row else 0])
 def process_result(self,sid,process_id,result):
  data=parsed_result(result);code=data.get('exit_code') if isinstance(data,dict) else None
  if process_id and isinstance(code,int):
   with self.lock,self.db() as db:
    db.execute('UPDATE calls SET background=?,failed=?,updated=? WHERE sid=? AND background=?',('',int(code!=0),time.time(),sid,process_id))
 def before(self,sid,turn,tool,args):
  key=signature(tool,args);now=time.time()
  with self.lock,self.db() as db:
   proof=self.proof(db,sid,args)
   row=db.execute('SELECT * FROM calls WHERE sid=? AND key=?',(sid,key)).fetchone()
   if row and not row['background'] and (now-row['updated']>1800 or row['evidence']!=proof):
    if row['evidence']!=proof:self.repaired(db,sid,turn)
    db.execute('DELETE FROM calls WHERE sid=? AND key=?',(sid,key));row=None
   reason=None
   if row:
    if row['background']:reason='already_running'
    elif row['failed']:reason='repeated_failure'
    elif row['turn'] in {turn,'seed'} and row['repeats']>=2 and tool in READ_TOOLS:reason='unchanged_result'
   if reason:
    count=self.violation(db,sid,turn,tool,reason)
    return {'success':False,'exit_code':125,'error':'freedom_no_progress','reason':reason,'repeated_call_not_executed':True,
     'message':'Этот вызов уже не дал нового результата и не выполнен повторно. Это блокировка повторного вызова, а не отмена задачи. Не меняй только таймаут или оформление. Сформулируй другую проверяемую гипотезу, исправь исходную причину либо выбери другой инструмент; выполни независимую часть цели, пока внешний шаг ожидает. Проверка синтаксиса, запись заметки и слова «меняю подход» сами по себе не исправляют прежний вызов. Сохрани проверенные факты и следующий шаг. Обращайся к владельцу только при конкретном препятствии, которое не можешь устранить доступными средствами.',
     'blocked_attempts':count,'existing_process':row['background'] or None}
  return None
 def after(self,sid,turn,tool,args,result):
  data=parsed_result(result)
  if not isinstance(data,dict):data={'result':data}
  failed,cause=failure(tool,data);key=signature(tool,args);result_hash=digest(stable(data));now=time.time()
  background=str(data.get('session_id') or '') if data.get('status')=='running' or (data.get('session_id') and data.get('exit_code') is None) else ''
  poll=tool in {'process','process_manage'} and args.get('action') in {'poll','log','list','status','wait'}
  if poll:return None
  with self.lock,self.db() as db:
   proof=self.proof(db,sid,args)
   previous=db.execute('SELECT * FROM calls WHERE sid=? AND key=?',(sid,key)).fetchone()
   repeats=previous['repeats']+1 if previous and previous['turn'] in {turn,'seed'} and previous['evidence']==proof and previous['result_hash']==result_hash else 1
   db.execute('INSERT OR REPLACE INTO calls VALUES(?,?,?,?,?,?,?,?,?)',(sid,key,proof,turn,int(failed),repeats,result_hash,background,now))
   if failed:
    db.execute('INSERT INTO causes VALUES(?,?,?,1) ON CONFLICT(sid,turn,cause) DO UPDATE SET count=count+1',(sid,turn,cause))
    family_count=db.execute('SELECT count FROM causes WHERE sid=? AND turn=? AND cause=?',(sid,turn,cause)).fetchone()[0]
    if family_count>=3:self.violation(db,sid,turn,tool,'same_error_cause')
   if now%60<2:
    db.execute('DELETE FROM calls WHERE updated<?',(now-86400,))
  if failed:return 'Вызов завершился ошибкой. Не повторяй его без исправления причины. Следующий шаг должен проверять другую гипотезу или использовать другой способ; новый таймаут, диагностика и заметка не разрешают прежний вызов.'
  if repeats>=2 and tool in READ_TOOLS:return 'Результат не изменился. Используй уже полученные данные; третье одинаковое чтение или проверка будет пропущена, пока исходный файл не изменится.'
  return None
