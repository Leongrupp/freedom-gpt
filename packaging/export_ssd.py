"""Personal SSD export. The public installer is never used as a history store."""
import argparse,hashlib,json,os,pathlib,shutil,sqlite3,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parent.parent;BUNDLE=ROOT/'build'/('FreedomGPT-'+json.loads((ROOT/'app/version.json').read_text())['version'])
LEGACY=pathlib.Path('A:/CodexProjects/local-llm/huihui-qwen3.8-coder');UI=pathlib.Path('A:/CodexProjects/freedom-gpt')
def copy_sqlite(source,dest):
 dest.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(source) as src,sqlite3.connect(dest) as target:src.backup(target)
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--destination');parser.add_argument('--include-models',action='store_true');parser.add_argument('--include-history',action='store_true');args=parser.parse_args()
 if not args.destination:
  import tkinter as tk
  from tkinter import filedialog
  root=tk.Tk();root.withdraw();selected=filedialog.askdirectory(title='Выберите внешний SSD или папку для нового Freedom GPT');root.destroy()
  if not selected:return
  args.destination=str(pathlib.Path(selected)/'FreedomGPT-Personal')
 dest=pathlib.Path(args.destination).resolve()
 if dest==dest.parent or dest.is_relative_to(BUNDLE) or BUNDLE.is_relative_to(dest) or dest.is_relative_to(LEGACY) or dest.is_relative_to(UI):raise ValueError('Выберите новую отдельную папку на SSD.')
 if dest.exists() and any(dest.iterdir()):raise ValueError('Папка назначения должна быть пустой. Существующие файлы не заменяются.')
 catalog=json.loads((BUNDLE/'catalog.json').read_text(encoding='utf8'));sources=[]
 if args.include_models:
  for model in [m for m in catalog if m.get('default')]:
   for file in model['files']:
    source=LEGACY/'creative-kit/models'/file['name'] if model['kind']=='image' else LEGACY/'models'/('Huihui-Qwen3.8-27B-Coder-IQ3_S3.gguf' if file['name']=='model.gguf' else file['name'])
    target=pathlib.Path('stack/creative-kit/models')/file['name'] if model['kind']=='image' else pathlib.Path('stack/models')/model['id']/file['name']
    if not source.is_file() or source.stat().st_size!=file['bytes']:raise ValueError('Модель ещё не скачана полностью: '+str(source)+'. Экспорт не начат.')
    sources.append((source,target,file))
 base_bytes=sum(p.stat().st_size for p in BUNDLE.rglob('*') if p.is_file());need=base_bytes+sum(f['bytes'] for _,_,f in sources)+2*1024**3
 probe=dest
 while not probe.exists():probe=probe.parent
 if shutil.disk_usage(probe).free<need:raise ValueError('Недостаточно места для экспорта: нужно как минимум '+str(round(need/1024**3,1))+' ГБ плюс история и вложения.')
 # This copies only the clean base. Personal content is added to this separate destination.
 shutil.copytree(BUNDLE,dest,dirs_exist_ok=True)
 sys.path.insert(0,str(BUNDLE/'runtime/hermes'));sys.path.insert(0,str(BUNDLE/'runtime/python/Lib/site-packages'))
 marks={}
 for source,target,file in sources:
  output=dest/target;output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,output);h=hashlib.sha256()
  with output.open('rb') as stream:
   for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
  if h.hexdigest()!=file['sha256']:raise ValueError('SHA256 не совпал после копирования: '+str(output)+'. Источник сохранён.')
  marks.setdefault(output.parent,{})[output.name]={'sha256':file['sha256'],'mtime_ns':output.stat().st_mtime_ns}
 for folder,data in marks.items():(folder/'.verified.json').write_text(json.dumps(data,indent=2),encoding='utf8')
 (dest/'data').mkdir(exist_ok=True);(dest/'data/settings.json').write_text(json.dumps({'active':'huihui-qwen38-coder' if args.include_models else None,'model_port':19135,'ui_port':19166,'onboarded':False}),encoding='utf8')
 if args.include_models:
  images=next(m for m in catalog if m['kind']=='image')
  (dest/'stack/creative-kit/manifest.json').write_text(json.dumps([{'path':str(dest/'stack/creative-kit/models'/f['name']),**f} for f in images['files']],indent=2),encoding='utf8')
 if args.include_history:
  # Use upstream's export/import format to avoid copying process ownership or API credentials.
  os.environ['HERMES_HOME']=str(LEGACY/'hermes-runtime')
  from hermes_state import SessionDB
  donor=SessionDB(LEGACY/'hermes-runtime/state.db',read_only=True)
  sessions=donor.export_all(include_inactive=True);donor.close()
  for session in sessions:
   session.update(cwd=str(dest/'workspaces'),source='cli',user_id=None,model='freedom-local',
       model_config=json.dumps({'provider':'custom','base_url':'http://127.0.0.1:19135/v1'}))
  (dest/'data/history-to-import.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  if (UI/'data/interface.sqlite').is_file():
   copy_sqlite(UI/'data/interface.sqlite',dest/'data/interface.sqlite')
   with sqlite3.connect(dest/'data/interface.sqlite') as conn:
    for table in ['files','artifacts']:
     for identifier,path in conn.execute(f'SELECT id,path FROM {table}').fetchall():
      src=pathlib.Path(path)
      if not src.is_file():continue
      output=dest/'data/imported-files'/identifier/src.name;output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,output)
      conn.execute(f'UPDATE {table} SET path=? WHERE id=?',(str(output),identifier))
  for name in ['memories','continuity','attachments']:
   source=LEGACY/'hermes-runtime'/name
   if source.is_dir():shutil.copytree(source,dest/'stack/hermes-runtime'/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.lock'))
  (dest/'workspaces').mkdir(exist_ok=True)
  for binding in (dest/'stack/hermes-runtime/continuity').glob('*/project.json'):
   try:
    item=json.loads(binding.read_text(encoding='utf8'));item['project']=str(dest/'workspaces');binding.write_text(json.dumps(item,ensure_ascii=False),encoding='utf8')
   except (ValueError,OSError):pass
  if (LEGACY/'work').is_dir():shutil.copytree(LEGACY/'work',dest/'workspaces/Imported',dirs_exist_ok=True,ignore=shutil.ignore_patterns('node_modules','.venv','venv','__pycache__'))
  (dest/'PRIVATE-PERSONAL-COPY.txt').write_text('PRIVATE: this copy includes your chat history and files. Do not publish it or use it as the public installer. API credentials and personal browser profiles were not copied.\n',encoding='utf8')
 (dest/'data/install-root.json').write_text(json.dumps({'root':str(dest)}),encoding='utf8')
 report={'destination':str(dest),'models':args.include_models,'history':args.include_history,'date':time.strftime('%Y-%m-%d %H:%M:%S'),'source_preserved':True,'physical_ssd_verified':False}
 (dest/'personal-export.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
