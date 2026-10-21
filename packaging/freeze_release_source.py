"""Freeze an explicitly approved source commit locally, without pushing or uploading."""
import hashlib,json,pathlib,shutil,subprocess
from publish_platforms import ROOT,SAFE,sha,verify_package_reports
def run(args,check=True):return subprocess.run(args,cwd=ROOT,check=check,capture_output=True,text=True,encoding='utf-8',errors='replace')
def main():
 v=json.loads((ROOT/'app/version.json').read_text())['version'];path=ROOT/'.private'/('publication-approval-'+v+'.json');approval=json.loads(path.read_text())
 if approval.get('enabled') is not True or approval.get('version')!=v:raise ValueError('Explicit version approval required')
 if approval.get('source_commit'):raise ValueError('This release source is already frozen; do not replace its approved commit')
 verify_package_reports(ROOT,v)
 if run(['git','diff','--cached','--name-only']).stdout.strip():raise ValueError('Review the existing staged changes before freezing')
 run(['git','add','--',*[name for name in SAFE if name!='deploy'],'deploy/vps/update_design.py'])
 forbidden={'.private','.tmp','.cache','node_modules','vendor','runtime','data','logs','output'}
 for name in run(['git','diff','--cached','--name-only']).stdout.splitlines():
  p=pathlib.PurePosixPath(name)
  if forbidden.intersection(p.parts) or p.name in {'auth.json','.env','state.db','interface.sqlite','private-runtime.json'} or p.suffix in {'.pem','.gguf','.safetensors','.pyc'} or name.startswith('deploy/') and name!='deploy/vps/update_design.py':raise ValueError('Unreviewed/private staged path: '+name)
 run(['git','commit','-m','Release Freedom GPT '+v+' agent features and portable installers'])
 approval['source_commit']=run(['git','rev-parse','HEAD']).stdout.strip()
 folder=ROOT/'release/platforms'/v;manifest=json.loads((folder/'release.json').read_text())
 files=[folder/f['name'] for f in manifest['files']]+[folder/n for n in ['release.json','platforms.json','SHA256SUMS.txt','README-BUILDS.md']]
 approval['assets']={f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in files}
 approval['website_package']=json.loads((ROOT/'.tmp/site-design-package.json').read_text())
 helper=ROOT/'.tmp'/('website-deployer-'+v+'.py');shutil.copy2(ROOT/'deploy/vps/update_design.py',helper)
 approval['website_deployer']={'path':str(helper),'sha256':sha(helper)}
 notes=ROOT/'release'/('notes-v'+v+'.md')
 if not notes.is_file():raise ValueError('Reviewed bilingual release notes required')
 frozen_notes=ROOT/'.tmp'/('release-notes-'+v+'-frozen.md')
 body=notes.read_text(encoding='utf-8').replace('/freedom-gpt/blob/main/','/freedom-gpt/blob/'+approval['source_commit']+'/').replace('/freedom-gpt/main/','/freedom-gpt/'+approval['source_commit']+'/')
 frozen_notes.write_text(body,encoding='utf-8')
 approval['release_notes']={'path':str(frozen_notes),'sha256':sha(frozen_notes)}
 path.write_text(json.dumps(approval,indent=2))
 print(json.dumps({'version':v,'source_commit':approval['source_commit'],'pushed':False}))
if __name__=='__main__':main()
