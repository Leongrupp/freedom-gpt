"""Publish one explicitly approved, verified platform release; keep older transfer holds."""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess,time
from publish import github_env
ROOT=pathlib.Path(__file__).resolve().parent.parent
SAFE=['.gitignore','.gitattributes','.github','README.md','README.ru.md','BUILD.md','CROSS-PLATFORM.md','VERIFICATION.md','LICENSE','NOTICE','SECURITY.md','CONTRIBUTING.md','Start-Website.cmd','Export-to-SSD.cmd','FILEZILLA-MODELS.txt','deploy','app','packaging','site','assets','licenses']

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-version',required=True);p.add_argument('--phase',choices=['source','upload','publish'],required=True);a=p.parse_args()
 meta=json.loads((ROOT/'app/version.json').read_text());v=meta['version'];repo=meta['repository'];tag='v'+v
 if a.approved_version!=v or not re.fullmatch(r'\d+\.\d+\.\d+',v):raise ValueError('Exact approved version required')
 approval=ROOT/'.private'/('publication-approval-'+v+'.json')
 if not approval.is_file() or json.loads(approval.read_text()).get('version')!=v:raise RuntimeError('Version-scoped owner authorization is required. Older holds are preserved.')
 out=ROOT/'release/platforms'/v;status=ROOT/'logs'/('publication-'+v+'.json');env=github_env();gh=shutil.which('gh')
 if not gh:
  gh=next((pathlib.Path(os.environ['LOCALAPPDATA'])/'Microsoft/WinGet/Packages').glob('GitHub.cli_*/bin/gh.exe'),None)
 if not gh:raise RuntimeError('GitHub CLI unavailable')
 def run(args,timeout=180,check=True):
  r=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
  if check and r.returncode:raise RuntimeError('Command failed: '+str(args[:3])+' '+r.stderr[-900:])
  return r
 def api(path):return json.loads(run([gh,'api',path]).stdout)
 def state(**kw):
  status.write_text(json.dumps({'version':v,'phase':a.phase,'time':time.time(),**kw},indent=2));print(json.dumps(kw),flush=True)
 if a.phase=='source':
  run(['git','add','--',*SAFE]);names=run(['git','diff','--cached','--name-only']).stdout.splitlines()
  forbidden={'.private','.tmp','.cache','node_modules','vendor','runtime','data'}
  for name in names:
   path=pathlib.PurePosixPath(name)
   if forbidden.intersection(path.parts) or path.name in {'auth.json','.env','state.db','interface.sqlite','private-runtime.json'} or path.suffix in {'.pem','.gguf','.safetensors','.pyc'}:raise ValueError('Private source path staged: '+name)
  staged=run(['git','diff','--cached','--quiet'],check=False)
  if staged.returncode==1:run(['git','commit','-m','Release Freedom GPT '+v+' for Windows, Ubuntu and Apple Silicon'])
  elif staged.returncode!=0:raise RuntimeError('Cannot inspect staged source')
  commit=run(['git','rev-parse','HEAD']).stdout.strip();run(['git','push','origin','main'],timeout=300)
  run([gh,'repo','edit',repo,'--description','Free local AI workspace: code, chat, files and images. Windows, Ubuntu and an experimental Apple Silicon build. English / Русский.','--homepage','http://aionpc.ru'])
  state(source_pushed=True,commit=commit);return
 for kind in ['windows-clean-pc-verification','ubuntu-clean-pc-verification','ubuntu-installers-verification','platform-artifacts-verification']:
  if not json.loads((ROOT/'logs'/(kind+'-'+v+'.json')).read_text()).get('passed'):raise ValueError('Verification required: '+kind)
 manifest=json.loads((out/'release.json').read_text());assets=[out/f['name'] for f in manifest['files']]+[out/'release.json',out/'platforms.json',out/'SHA256SUMS.txt',out/'README-BUILDS.md']
 if len({f.name for f in assets})!=len(assets):raise ValueError('Duplicate release assets')
 expected={f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in assets}
 notes=ROOT/'release'/('notes-'+tag+'.md')
 notes.write_text(f'''# Freedom GPT {v} 💛

## English
Free local AI workspace: chat, code, files, images and model discovery.
Windows EXE/ZIP and Ubuntu .run/DEB/TAR.GZ include Python, Node.js, agent libraries and engines. Model weights download separately. Signed updates preserve chats and models.

**macOS candidate:** Apple Silicon M1+, macOS 26.2+. Unsigned, not notarized; native Mac execution is not verified. **Video Studio is experimental** and full rendering validation remains pending. No universal generation-speed guarantee.

Choose your OS asset below. See README for commands and SHA256SUMS.txt for checksums.
[Website](http://aionpc.ru) · [Telegram support](https://t.me/AI1rus) · [English guide](https://github.com/{repo}#readme)

## Русский
Бесплатные локальные чаты, код, файлы, изображения и поиск моделей.
В пакетах Windows и Ubuntu уже есть Python, Node.js, библиотеки агента и движки. Модели скачиваются отдельно. Подписанные обновления сохраняют чаты и модели.

**macOS — кандидат:** M1+, macOS 26.2+, без подписи и нотарификации; запуск на Mac ещё не проверен. **Видеостудия экспериментальная**, полная проверка генерации впереди. Скорость зависит от компьютера и задачи.

[Установка на русском](https://github.com/{repo}/blob/main/README.ru.md) · [Поддержка](https://t.me/AI1rus)

Спасибо за отзывы и звёзды 💛 Развиваю агента, новые модели и локальную генерацию видео. Добровольная поддержка: [страница проекта](https://github.com/{repo}#support-development).
''',encoding='utf-8')
 result=run([gh,'release','view',tag,'--repo',repo,'--json','isDraft,tagName'],check=False)
 if result.returncode:
  if a.phase!='upload':raise RuntimeError('Create and upload a draft first')
  commit=run(['git','rev-parse','HEAD']).stdout.strip();run([gh,'release','create',tag,'--repo',repo,'--draft','--target',commit,'--title','Freedom GPT '+v+' · Windows / Ubuntu / macOS candidate','--notes-file',notes])
 release_id=json.loads(run([gh,'release','view',tag,'--repo',repo,'--json','databaseId']).stdout)['databaseId']
 release_path='repos/'+repo+'/releases/'+str(release_id)
 release=api(release_path)
 if a.phase=='upload':
  if not release.get('draft'):raise RuntimeError('Refusing to change already-public release assets')
  run([gh,'release','edit',tag,'--repo',repo,'--notes-file',notes])
  for number,file in enumerate(assets):
   release=api(release_path);existing=next((x for x in release['assets'] if x['name']==file.name),None);good=existing and existing.get('state')=='uploaded' and existing['size']==expected[file.name]['bytes'] and existing.get('digest')=='sha256:'+expected[file.name]['sha256']
   if not good:
    if existing:run([gh,'api','--method','DELETE','repos/'+repo+'/releases/assets/'+str(existing['id'])])
    for attempt in range(3):
     state(uploading=file.name,completed=number,total=len(assets),attempt=attempt+1)
     r=run([gh,'release','upload',tag,file,'--repo',repo],timeout=3600,check=False)
     if not r.returncode:break
     if attempt==2:raise RuntimeError('Upload failed: '+file.name+' '+r.stderr[-500:])
     current=api(release_path);partial=next((x for x in current['assets'] if x['name']==file.name),None)
     if partial:run([gh,'api','--method','DELETE','repos/'+repo+'/releases/assets/'+str(partial['id'])])
  state(draft_uploaded=True,total=len(assets));return
 uploaded={f['name']:f for f in release['assets']}
 for name,info in expected.items():
  actual=uploaded.get(name)
  if not actual or actual.get('state')!='uploaded' or actual['size']!=info['bytes'] or actual.get('digest')!='sha256:'+info['sha256']:raise ValueError('GitHub asset verification failed: '+name)
 if set(uploaded)!=set(expected):raise ValueError('Unexpected release asset')
 run([gh,'release','edit',tag,'--repo',repo,'--draft=false','--latest']);latest=api('repos/'+repo+'/releases/latest')
 if latest['tag_name']!=tag or latest['draft']:raise RuntimeError('Published latest release differs')
 state(published=True,url=latest['html_url'],verified_assets=len(expected))
if __name__=='__main__':main()
