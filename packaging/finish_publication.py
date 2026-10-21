"""Finish one authorized release, then atomically update static pages without VPN changes."""
import argparse,hashlib,json,os,pathlib,shlex,subprocess,sys,tarfile,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION='1.5.0';STATUS=ROOT/'logs/background-publication-1.5.0.json'
SSH=['C:/Windows/System32/OpenSSH/ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=20','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(ROOT/'.private/vps-known-hosts'),'root@185.125.100.186']
def state(stage,**values):
 data={'version':VERSION,'stage':stage,'time':time.time(),**values};p=STATUS.with_suffix('.new');p.write_text(json.dumps(data,indent=2));p.replace(STATUS);print(json.dumps(data),flush=True)
def permitted():
 a=json.loads((ROOT/'.private/publication-approval-1.5.0.json').read_text())
 if a.get('enabled') is not True or (ROOT/'.private/release-stop-1.5.0').exists():raise RuntimeError('Publication paused by owner')
def run(args,timeout=600):
 permitted();p=subprocess.run(list(map(str,args)),cwd=ROOT,timeout=timeout,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if p.returncode:raise RuntimeError('Step failed: '+str(args[:2])+' '+p.stderr[-1200:])
 return p.stdout
def phase(name):
 permitted();state(name)
 subprocess.run([sys.executable,'-B',str(ROOT/'packaging/publish_platforms.py'),'--approved-version',VERSION,'--phase',name],cwd=ROOT,check=True,timeout=10*3600)
def fetch(url):
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(urllib.request.Request(url,headers={'User-Agent':'FreedomGPT-ReleaseVerification'}),timeout=30) as response:return response.status,response.read(),dict(response.headers)
def deploy():
 state('refreshing_website_metadata');run(SSH+['systemctl start freedom-gpt-release-refresh.service'],90)
 for _ in range(20):
  permitted()
  if json.loads(fetch('https://aionpc.ru/api/platforms')[1]).get('version')==VERSION:break
  time.sleep(15)
 else:raise RuntimeError('Public metadata did not refresh to the new version')
 approved=json.loads((ROOT/'.private/publication-approval-1.5.0.json').read_text())
 package=approved['website_package'];source=pathlib.Path(package['archive']).resolve()
 if not source.is_relative_to(ROOT) or hashlib.sha256(source.read_bytes()).hexdigest()!=package['sha256']:raise ValueError('Website package changed')
 remote='/root/freedom-gpt-deploy/'+source.name;helper='/root/freedom-gpt-deploy/update-design-1.5.0.py'
 scp=['C:/Windows/System32/OpenSSH/scp.exe','-O','-o','BatchMode=yes','-o','ConnectTimeout=20','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(ROOT/'.private/vps-known-hosts')]
 deployer=pathlib.Path(approved['website_deployer']['path']).resolve()
 if not deployer.is_relative_to(ROOT) or hashlib.sha256(deployer.read_bytes()).hexdigest()!=approved['website_deployer']['sha256']:raise ValueError('Frozen website deployer changed')
 run(scp+[source,'root@185.125.100.186:'+remote]);run(scp+[deployer,'root@185.125.100.186:'+helper])
 state('deploying_static_pages')
 result=json.loads(run(SSH+['python3 '+shlex.quote(helper)+' '+shlex.quote(remote)+' '+shlex.quote(package['sha256'])],180))
 if not result.get('protected_state_unchanged') or not result.get('deployed'):raise RuntimeError('Website deployment was not confirmed')
 (ROOT/'logs/website-deployment-1.5.0.json').write_text(json.dumps(result,indent=2))
 state('verifying_public_pages_and_downloads')
 checks={}
 for path,lang in [('/','ru'),('/en/','en'),('/guides/ai-agent/','ru'),('/en/guides/ai-agent/','en')]:
  code,raw,_=fetch('https://aionpc.ru'+path);text=raw.decode('utf-8');checks[path]=code==200 and '1.5.0' in text and 'https://t.me/AI1rus' in text
 code,_,_=fetch('https://aionpc.ru/agent.css');checks['agent_css']=code==200
 with tarfile.open(source,'r:gz') as archive:
  design=json.load(archive.extractfile('design-manifest.json'))
 images=[item for item in design['files'] if item['path'].startswith('public/media/screenshots/')]
 checks['nine_real_interface_images']=len(images)==9
 commit=approved['source_commit']
 for item in images:
  relative=item['path'].removeprefix('public/');name=pathlib.PurePosixPath(relative).name
  code,pixels,headers=fetch('https://aionpc.ru/'+relative)
  checks['site_image:'+name]=code==200 and hashlib.sha256(pixels).hexdigest()==item['sha256'] and 'image/png' in headers.get('Content-Type','')
  code,pixels,_=fetch('https://raw.githubusercontent.com/Leongrupp/freedom-gpt/'+commit+'/assets/screenshots/'+name)
  checks['github_image:'+name]=code==200 and hashlib.sha256(pixels).hexdigest()==item['sha256']
 for readme,lang in [('README.md','en'),('README.ru.md','ru')]:
  code,raw,_=fetch('https://raw.githubusercontent.com/Leongrupp/freedom-gpt/'+commit+'/'+readme)
  checks['github_readme:'+lang]=code==200 and ('assets/screenshots/overview-'+lang+'.png') in raw.decode('utf-8') and 'https://aionpc.ru' in raw.decode('utf-8')
 matrix=json.loads(fetch('https://aionpc.ru/api/platforms')[1]);checks['three_platforms']=matrix.get('version')==VERSION and len(matrix.get('platforms',[]))==3
 downloads=[f for p in matrix['platforms'] for f in p['files']];checks['six_downloads']=len(downloads)==6
 for file in downloads:
  req=urllib.request.Request(file['url'],headers={'Range':'bytes=0-4095','User-Agent':'FreedomGPT-ReleaseVerification'})
  with urllib.request.urlopen(req,timeout=60) as response:checks['download:'+file['name']]=response.status==206 and response.headers.get('Content-Range')=='bytes 0-4095/'+str(file['bytes']) and len(response.read(4096))==4096
 public=json.loads(fetch('https://api.github.com/repos/Leongrupp/freedom-gpt/releases/tags/v1.4.2')[1]);old=json.loads((ROOT/'logs/previous-release-1.4.2.json').read_text())
 checks['previous_release_unchanged']={a['name']:(a['size'],a.get('digest')) for a in public['assets']}=={a['name']:(a['size'],a.get('digest')) for a in old['assets']}
 report={'passed':all(checks.values()),'checks':checks,'version':VERSION,'mac_native_execution_tested':False,'website':'https://aionpc.ru','release':'https://github.com/Leongrupp/freedom-gpt/releases/tag/v1.5.0'}
 (ROOT/'logs/public-release-verification-1.5.0.json').write_text(json.dumps(report,indent=2))
 if not report['passed']:raise RuntimeError('A public endpoint check failed; inspect report')
 return report
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--website-only',action='store_true');args=parser.parse_args();permitted()
 if not args.website_only:
  phase('upload');phase('source');phase('publish')
 report=deploy();state('verifying_public_seo')
 run([sys.executable,'-B',ROOT/'packaging/audit_site_seo.py','--base','https://aionpc.ru','--report','logs/site-seo-public-1.5.0.json'],240)
 state('complete',published=True,downloads_verified=True,website=report['website'],release=report['release'],vpn_configuration_unchanged=True,mac_native_execution_tested=False,public_seo_verified=True)
if __name__=='__main__':
 try:main()
 except Exception as error:state('needs_attention',error=type(error).__name__+': '+str(error)[:700]);raise
