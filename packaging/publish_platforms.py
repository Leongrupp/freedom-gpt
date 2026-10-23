"""Publish one explicitly approved, verified platform release; keep older transfer holds."""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess,time
from publish import github_env
ROOT=pathlib.Path(__file__).resolve().parent.parent
SAFE=['.gitignore','.gitattributes','.github','README.md','README.ru.md','INSTALL.md','INSTALL.ru.md','BUILD.md','CROSS-PLATFORM.md','VERIFICATION.md','LICENSE','NOTICE','SECURITY.md','SUPPORT.md','CODE_OF_CONDUCT.md','CONTRIBUTING.md','Start-Website.cmd','Export-to-SSD.cmd','FILEZILLA-MODELS.txt','deploy','app','packaging','site','assets','licenses','docs','connect']

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()

def verify_package_reports(root,v):
 """Reject stale successful reports from an earlier build of the same version."""
 folder=root/'release/platforms'/v
 windows=[root/'release'/('FreedomGPT-Setup-'+v+'.exe'),root/'release'/('FreedomGPT-'+v+'-Windows-x64.zip')]
 ubuntu=[folder/('FreedomGPT-'+v+'-Ubuntu-x64.tar.gz'),folder/('FreedomGPT-Setup-'+v+'-Ubuntu-x64.run'),folder/('FreedomGPT-'+v+'-Ubuntu-amd64.deb')]
 packages=windows+ubuntu+[folder/('FreedomGPT-'+v+'-macOS-AppleSilicon.zip'),root/'release/update.json',folder/'update-ubuntu-x64.json',folder/'update-macos-arm64.json']
 for kind,inputs in [('windows-clean-pc-verification',windows),('ubuntu-clean-pc-verification',ubuntu[:1]),('ubuntu-installers-verification',ubuntu[1:]),('platform-artifacts-verification',packages),('source-alignment-verification',packages)]:
  report=root/'logs'/(kind+'-'+v+'.json')
  if not report.is_file() or not json.loads(report.read_text(encoding='utf8')).get('passed'):raise ValueError('Passed verification required: '+kind)
  if any(not p.is_file() for p in inputs) or report.stat().st_mtime<max(p.stat().st_mtime for p in inputs):raise ValueError('Fresh package verification required: '+kind)

def verify_native_macos(root,v):
 """Bind native execution evidence to the exact archive being published."""
 spec=json.loads((root/'packaging/native-validation.json').read_text(encoding='utf-8'))
 report=json.loads((root/'logs'/('native-macos-verification-'+v+'.json')).read_text(encoding='utf-8'))
 asset=spec['macos'];file=root/'release/platforms'/v/asset['file']
 workflow=report.get('workflow',{})
 if spec['version']!=v or report.get('version')!=v or report.get('platform')!='macos-arm64' or not report.get('passed'):raise ValueError('Native macOS verification required')
 if report.get('asset')!=asset or file.stat().st_size!=asset['bytes'] or sha(file)!=asset['sha256']:raise ValueError('Native macOS report does not match final archive')
 if workflow.get('status')!='completed' or workflow.get('conclusion')!='success' or workflow.get('headSha')!=report.get('source_commit'):raise ValueError('Successful exact-commit native macOS CI required')
 if not report.get('checks') or not all(report['checks'].values()):raise ValueError('Native macOS checks did not all pass')
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-version',required=True);p.add_argument('--phase',choices=['source','upload','publish'],required=True);a=p.parse_args()
 meta=json.loads((ROOT/'app/version.json').read_text());v=meta['version'];repo=meta['repository'];tag='v'+v
 if a.approved_version!=v or not re.fullmatch(r'\d+\.\d+\.\d+',v):raise ValueError('Exact approved version required')
 approval=ROOT/'.private'/('publication-approval-'+v+'.json')
 def permitted():
  value=json.loads(approval.read_text()) if approval.is_file() else {}
  if time.time()<float(value.get('deferred_until',0)):raise RuntimeError('Publication deferred by owner')
  if value.get('version')!=v or value.get('enabled') is not True or (ROOT/'.private'/('release-stop-'+v)).exists():raise RuntimeError('Version-scoped publication approval is disabled. Older holds are preserved.')
  gate=ROOT/'.private'/('publish-after-video-test-'+v+'.json')
  if gate.is_file():
   decision=json.loads(gate.read_text())
   if decision.get('required') and not (decision.get('passed') and decision.get('visual_review_passed')):raise RuntimeError('Real video generation and visual review must pass before publication.')
 permitted()
 verify_native_macos(ROOT,v)
 out=ROOT/'release/platforms'/v;status=ROOT/'logs'/('publication-'+v+'.json');env=github_env();gh=shutil.which('gh')
 if not gh:
  gh=next((pathlib.Path(os.environ['LOCALAPPDATA'])/'Microsoft/WinGet/Packages').glob('GitHub.cli_*/bin/gh.exe'),None)
 if not gh:raise RuntimeError('GitHub CLI unavailable')
 def run(args,timeout=180,check=True):
  for attempt in range(3):
   permitted()
   r=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
   network=any(s in r.stderr.lower() for s in ['error connecting','i/o timeout','tls handshake timeout','connection reset','temporary failure','unexpected eof','could not resolve host'])
   retry_safe=str(args[0])==str(gh) and (args[1:3] in [['release','view'],['release','edit'],['repo','edit']] or args[1:2]==['api'] and '--method' not in args) or args[:2]==['git','push']
   if not r.returncode or not network or not retry_safe or attempt==2:break
   time.sleep(2+attempt*3)
  if check and r.returncode:raise RuntimeError('Command failed: '+str(args[:3])+' '+r.stderr[-900:])
  return r
 def api(path):return json.loads(run([gh,'api',path]).stdout)
 def state(**kw):
  status.write_text(json.dumps({'version':v,'phase':a.phase,'time':time.time(),**kw},indent=2));print(json.dumps(kw),flush=True)
 if a.phase=='source':
  pinned=json.loads(approval.read_text()).get('source_commit')
  if not pinned:raise ValueError('Freeze the reviewed release source before uploading')
  if not re.fullmatch('[0-9a-f]{40}',pinned):raise ValueError('Invalid pinned source commit')
  run(['git','cat-file','-e',pinned+'^{commit}'])
  run(['git','push','origin',pinned+':refs/heads/main'],timeout=300)
  metadata=json.loads(run(['git','show',pinned+':docs/repository-metadata.json']).stdout)
  run([gh,'repo','edit',repo,'--description',metadata['description'],'--homepage','https://aionpc.ru'])
  topic_file=ROOT/'.tmp/release-topics.json';topic_file.write_text(json.dumps({'names':metadata['topics']}))
  run([gh,'api','--method','PUT','repos/'+repo+'/topics','--input',topic_file])
  state(source_pushed=True,commit=pinned);return
 verify_package_reports(ROOT,v)
 manifest=json.loads((out/'release.json').read_text());assets=[out/f['name'] for f in manifest['files']]+[out/'release.json',out/'platforms.json',out/'SHA256SUMS.txt',out/'README-BUILDS.md']
 if len({f.name for f in assets})!=len(assets):raise ValueError('Duplicate release assets')
 expected={f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in assets}
 if expected!=json.loads(approval.read_text()).get('assets'):raise ValueError('Frozen release assets changed; do not publish')
 reviewed_notes=json.loads(approval.read_text()).get('release_notes',{})
 notes=pathlib.Path(reviewed_notes.get('path','')).resolve()
 if not notes.is_relative_to(ROOT) or not notes.is_file() or sha(notes)!=reviewed_notes.get('sha256'):raise ValueError('Frozen reviewed release notes required; notes may not change during publication')
 result=run([gh,'release','view',tag,'--repo',repo,'--json','isDraft,tagName'],check=False)
 if result.returncode:
  if not any(s in result.stderr.lower() for s in ['release not found','not found','http 404']):raise RuntimeError('Cannot inspect the existing release: '+result.stderr[-500:])
  if a.phase!='upload':raise RuntimeError('Create and upload a draft first')
  commit=run(['git','rev-parse','origin/main']).stdout.strip();run([gh,'release','create',tag,'--repo',repo,'--draft','--target',commit,'--title','Freedom GPT '+v+' · Windows / Ubuntu / macOS candidate','--notes-file',notes])
 release_id=json.loads(run([gh,'release','view',tag,'--repo',repo,'--json','databaseId']).stdout)['databaseId']
 release_path='repos/'+repo+'/releases/'+str(release_id)
 release=api(release_path)
 if a.phase=='upload':
  if not release.get('draft'):raise RuntimeError('Refusing to change already-public release assets')
  commit=run(['git','rev-parse','origin/main']).stdout.strip()
  run([gh,'release','edit',tag,'--repo',repo,'--notes-file',notes,'--target',commit])
  for number,file in enumerate(assets):
   release=api(release_path);existing=next((x for x in release['assets'] if x['name']==file.name),None);good=existing and existing.get('state')=='uploaded' and existing['size']==expected[file.name]['bytes'] and existing.get('digest')=='sha256:'+expected[file.name]['sha256']
   if not good:
    if existing:run([gh,'api','--method','DELETE','repos/'+repo+'/releases/assets/'+str(existing['id'])])
    for attempt in range(3):
     state(uploading=file.name,completed=number,total=len(assets),attempt=attempt+1)
     r=run([gh,'release','upload',tag,file,'--repo',repo],timeout=10800,check=False)
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
 commit=json.loads(approval.read_text()).get('source_commit')
 if not commit or not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Pinned source commit is required')
 run([gh,'release','edit',tag,'--repo',repo,'--target',commit,'--notes-file',notes,'--draft=false','--latest']);latest=api('repos/'+repo+'/releases/latest')
 if latest['tag_name']!=tag or latest['draft']:raise RuntimeError('Published latest release differs')
 state(published=True,url=latest['html_url'],verified_assets=len(expected))
if __name__=='__main__':main()
