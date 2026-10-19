"""Build and publish a signed Freedom GPT release from reviewed public sources."""
import argparse,ast,json,os,pathlib,re,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parent.parent
SAFE=['.gitignore','.gitattributes','.github','README.md','README.ru.md','BUILD.md','VERIFICATION.md','LICENSE','NOTICE','SECURITY.md','CONTRIBUTING.md','Start-Website.cmd','Export-to-SSD.cmd','FILEZILLA-MODELS.txt','deploy','app','packaging','site','assets','licenses']
def run(args,**kw):
 kw.setdefault('cwd',ROOT);subprocess.run([str(a) for a in args],check=True,**kw)
def github_env():
 env=os.environ.copy()
 if not env.get('GH_TOKEN'):
  env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
  r=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,env=env,timeout=20)
  values=dict(s.split('=',1) for s in r.stdout.splitlines() if '=' in s)
  if not values.get('password'):raise RuntimeError('Sign in to GitHub CLI or Git Credential Manager first')
  env['GH_TOKEN']=values['password']
 env['GH_PROMPT_DISABLED']='1';return env
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',required=True);parser.add_argument('--runtime-from',required=True,type=pathlib.Path);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
 if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise ValueError('Use a numeric version, for example1.2.1')
 env=github_env() if not args.prepare_only else os.environ.copy()
 meta=json.loads((ROOT/'app/version.json').read_text());meta['version']=args.version
 (ROOT/'app/version.json').write_text(json.dumps(meta,separators=(',',':'))+'\n')
 for name in ['package.json','package-lock.json']:
  path=ROOT/'app'/name;data=json.loads(path.read_text());data['version']=args.version
  if 'packages' in data:data['packages']['']['version']=args.version
  path.write_text(json.dumps(data,indent=2)+'\n')
 for name in ['Launcher.cs','Installer.cs']:
  path=ROOT/'packaging'/name;text=path.read_text(encoding='utf8');text=re.sub(r'AssemblyVersion\("[\d.]+"\)',f'AssemblyVersion("{args.version}.0")',text);path.write_text(text,encoding='utf8')
 for path in (ROOT/'app').glob('*.py'):ast.parse(path.read_text(encoding='utf8'),filename=str(path))
 node=os.environ.get('FREEDOM_NODE') or shutil.which('node')
 if not node:raise RuntimeError('Install Node.js to build the frontend')
 if not (ROOT/'app/node_modules').exists():raise RuntimeError('Run npm ci --ignore-scripts in app/ first')
 run([node,ROOT/'app/node_modules/vite/bin/vite.js','build'],cwd=ROOT/'app')
 if args.runtime_from.resolve()==(ROOT/'build'/('FreedomGPT-'+args.version)).resolve():raise RuntimeError('Use a previous clean runtime, not the current output folder')
 run([sys.executable,ROOT/'packaging/sign_update.py'])
 run([sys.executable,ROOT/'packaging/bundle.py','--runtime-from',args.runtime_from])
 run([sys.executable,ROOT/'packaging/release.py'])
 manifest=json.loads((ROOT/'release/release.json').read_text());manifest['public']=True
 manifest['files']=[{**f,'url':f'https://github.com/{meta["repository"]}/releases/download/v{args.version}/{f["name"]}'} for f in manifest['files'] if f['name'].endswith('.exe') or 'Windows-x64.zip' in f['name']]
 (ROOT/'site/release.json').write_text(json.dumps(manifest,indent=2))
 for name in ['README.md','README.ru.md']:
  path=ROOT/name;text=path.read_text(encoding='utf8');text=re.sub(r'FreedomGPT-Setup-\d+\.\d+\.\d+\.exe','FreedomGPT-Setup-'+args.version+'.exe',text);path.write_text(text,encoding='utf8')
 run([sys.executable,ROOT/'packaging/source_archive.py'])
 if args.prepare_only:return
 if not (ROOT/'.git').exists():raise RuntimeError('Initialize and review the source repository first')
 run(['git','add','--',*SAFE]);run(['git','commit','-m','Release Freedom GPT '+args.version]);run(['git','push','origin','main'],env=env)
 manifest=json.loads((ROOT/'release/release.json').read_text());repo=meta['repository'];tag='v'+args.version
 notes=ROOT/'release'/('notes-'+tag+'.md');notes.write_text(f'Freedom GPT {args.version}\n\nWindows x64 · English / Русский\n\nDownload the EXE installer or extract the portable ZIP. Models download separately. Automatic updates are signed and preserve user data. See the README for requirements and installation.\n\nУстановщик RU/EN и переносимый ZIP. Модели загружаются отдельно. Подписанные обновления сохраняют чаты и модели.\n',encoding='utf8')
 run(['gh','release','create',tag,'--repo',repo,'--draft','--target','main','--title','Freedom GPT '+args.version,'--notes-file',notes],env=env)
 assets=[ROOT/'release'/f['name'] for f in manifest['files']]+[ROOT/'release/SHA256SUMS.txt']
 run(['gh','release','upload',tag,*assets,'--repo',repo],env=env)
 run(['gh','release','edit',tag,'--repo',repo,'--draft=false','--latest'],env=env)
 print('Published https://github.com/'+repo+'/releases/tag/'+tag)
if __name__=='__main__':main()
