"""Build a public allowlisted bundle, excluding every personal data store and model."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,time,zipfile
ROOT=pathlib.Path(__file__).resolve().parent.parent;APP=ROOT/'app';DEST=ROOT/'build'/('FreedomGPT-'+json.loads((APP/'version.json').read_text())['version'])
STACK=pathlib.Path(os.environ.get('FREEDOM_BUILD_STACK',str(ROOT/'vendor/stack')))
HERMES=pathlib.Path(os.environ.get('FREEDOM_BUILD_HERMES',str(ROOT/'vendor/hermes')))
PYBASE=pathlib.Path(os.environ.get('FREEDOM_BUILD_PYTHON',str(ROOT/'vendor/python')))
DEPS=pathlib.Path(os.environ.get('FREEDOM_BUILD_DEPS',str(ROOT/'vendor/site-packages')))
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','*.pdb','__editable__*','_virtualenv*','direct_url.json')
def tree(source,target,exclude=()):shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pdb','__editable__*','_virtualenv*','direct_url.json',*exclude))
def copy(source,target):target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def main():
 global STACK,HERMES,PYBASE,DEPS
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runtime-from',type=pathlib.Path,help='Previously extracted clean Freedom GPT release with its runtime directory');args=parser.parse_args()
 if args.runtime_from:
  donor=args.runtime_from.resolve();STACK=donor/'stack';HERMES=donor/'runtime/hermes';PYBASE=donor/'runtime/python';DEPS=PYBASE/'Lib/site-packages'
 else:donor=None
 DEST.mkdir(parents=True,exist_ok=True)
 for name in ['updater.py','apply_update.py','update_protocol.py','version.json','update-key.pub','README.txt','bootstrap.py','init-project-memory.py','gguf_info.py','launch.py','stop.py','server.py','library.py','engine_supervisor.py','generate-image-request.py','catalog.json','freedom.ico','Start-FreedomGPT.cmd','Stop-FreedomGPT.cmd']:
  copy(APP/name,DEST/name)
 for name in ['discovery.py','video.py','platform_support.py','preflight.py','system_check.py']:copy(APP/name,DEST/'runtime/freedom'/name)
 tree(APP/'dist',DEST/'dist');tree(APP/'public',DEST/'public')
 tree(PYBASE,DEST/'runtime/python')
 # No venv absolute redirector, user .pth, token cache or editable-install path.
 if DEPS.resolve()!=(PYBASE/'Lib/site-packages').resolve():tree(DEPS,DEST/'runtime/python/Lib/site-packages')
 top={'agent','hermes_cli','gateway','tui_gateway','hermes_platform','tools','providers','acp_adapter','cron','skills','plugins','assets','locales','pm'}
 tracked=[p.relative_to(HERMES).as_posix() for p in HERMES.rglob('*') if p.is_file()] if donor else subprocess.check_output(['git','-C',str(HERMES),'ls-files','-z']).decode().split('\0')
 for name in tracked:
  if not name:continue
  p=pathlib.PurePosixPath(name)
  if (len(p.parts)==1 and (p.suffix in {'.py','.md','.yaml','.toml'} or p.name=='LICENSE')) or p.parts[0] in top:
   src=HERMES/name
   if src.is_file() and src.suffix not in {'.pyc','.pdb'} and '__pycache__' not in p.parts:copy(src,DEST/'runtime/hermes'/name)
 # Own local plugins and a minimal coding-memory skill; no personal skill/tool kits.
 for relative in ['plugins/coding-continuity','plugins/image_gen/local-qwen-image','skills/coding-continuity']:
  src=STACK/'hermes-runtime'/relative
  if src.is_dir():tree(src,DEST/'stack/hermes-runtime'/relative)
 for name in ['gpu_lease.py','image-tool.py']:
  src=STACK/'creative-kit'/name;text=src.read_text(encoding='utf8')
  if name=='image-tool.py':
   text=text.replace("'http://127.0.0.1:11435'+path","'http://127.0.0.1:'+str(json.loads((STACK/'server-settings.json').read_text())['port'])+path")
   text=text.replace("pathlib.Path('A:/CodexProjects').resolve()","ROOT.parents[1].resolve()")
   text=text.replace("Output must be under A:/CodexProjects","Output must stay inside Freedom GPT")
   text=text.replace("ROOT/'engine/sd-95b3090-cuda12'","ROOT.parents[1]/'runtime/sd'").replace("ROOT/'engine/sd-95b3090-cuda12/sd-cli.exe'","ROOT.parents[1]/'runtime/sd/sd-cli.exe'")
  target=DEST/'stack/creative-kit'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf8')
 skill=DEST/'stack/hermes-runtime/skills/coding-continuity/SKILL.md'
 text=skill.read_text(encoding='utf8')
 start=text.index('```powershell');end=text.index('```',start+3)+3
 text=text[:start]+'''```powershell
 & "$env:FREEDOM_ROOT\\runtime\\python\\python.exe" "$env:FREEDOM_ROOT\\init-project-memory.py" --project 'ACTUAL_PROJECT_PATH' --session 'ACTUAL_SESSION_ID'
 ```'''+text[end:]
 text=text.replace('All projects and generated artifacts live under `A:\\CodexProjects`.','All projects and generated artifacts live inside the Freedom GPT workspaces folder (`FREEDOM_ROOT/workspaces`).')
 skill.write_text(text,encoding='utf8')
 plugin=DEST/'stack/hermes-runtime/plugins/image_gen/local-qwen-image/__init__.py'
 text=plugin.read_text(encoding='utf8').replace("ROOT=pathlib.Path('A:/CodexProjects/local-llm/huihui-qwen3.8-coder/creative-kit')","import os\nROOT=pathlib.Path(os.environ['FREEDOM_STACK'])/'creative-kit'").replace('Local Qwen Image 2.1 Turbo (RTX 4080)','Local Qwen Image 2.1 Turbo')
 plugin.write_text(text,encoding='utf8')
 plugin=DEST/'stack/hermes-runtime/plugins/coding-continuity/__init__.py'
 text=plugin.read_text(encoding='utf8').replace("Path(r'A:\\CodexProjects').resolve()","Path(os.environ['FREEDOM_ROOT']).resolve()").replace('Project memory must stay under A:\\\\CodexProjects','Project memory must stay inside Freedom GPT')
 plugin.write_text(text,encoding='utf8')
 cuda=donor/'runtime/llama' if donor else STACK/'engine/llama-620d2225c-cuda12'
 shared=donor/'runtime/cuda' if donor and (donor/'runtime/cuda').is_dir() else cuda
 for name in ['cublas64_12.dll','cublasLt64_12.dll']:copy(shared/name,DEST/'runtime/cuda'/name)
 tree(cuda,DEST/'runtime/llama',exclude=('cublas64_12.dll','cublasLt64_12.dll'))
 tree(donor/'runtime/sd' if donor else STACK/'creative-kit/engine/sd-95b3090-cuda12',DEST/'runtime/sd',exclude=('cublas64_12.dll','cublasLt64_12.dll'))
 # Keep the image engine usable on Windows without a separately installed VC runtime.
 # A licensed, unmodified Microsoft redistributable directory can be supplied by builders.
 vc=pathlib.Path(os.environ.get('FREEDOM_BUILD_MSVC',str(pathlib.Path(os.environ.get('SystemRoot','C:/Windows'))/'System32')))
 for name in ['msvcp140.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll','vcomp140.dll']:
  target=DEST/'runtime/sd'/name
  if not target.is_file():
   source=vc/name
   if not source.is_file():raise RuntimeError('Missing Microsoft redistributable '+name+'; set FREEDOM_BUILD_MSVC to its licensed runtime directory')
   copy(source,target)
 for name in ['gpu_lease.py','image-tool.py']:copy(APP/'creative'/name,DEST/'stack/creative-kit'/name)
 # Additional official backends let a clean PC fall back from CUDA to Vulkan/CPU.
 from archive_utils import unpack
 lock=json.loads((ROOT/'packaging/native-lock.json').read_text())
 native={'platform':'windows-x64','engines':{'llama':{'cuda':'runtime/llama/llama-server.exe'},'sd':{'cuda':'runtime/sd/sd-cli.exe'}},'upstream':lock['targets']['windows-x64']}
 for kind,item in native['upstream'].items():
  archive=ROOT/'.cache/platforms/downloads'/item['file'];h=hashlib.sha256()
  with archive.open('rb') as stream:
   for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
  if archive.stat().st_size!=item['bytes'] or h.hexdigest()!=item['sha256']:raise ValueError('Runtime verification failed: '+item['file'])
  folder=ROOT/'.cache/platforms/unpacked/windows-x64'/kind;unpack(archive,folder)
  family,backend=kind.split('-',1);destination=DEST/'runtime'/family/backend;tree(folder,destination)
  executable=next(destination.rglob('llama-server.exe' if family=='llama' else 'sd-cli.exe'))
  native['engines'][family][backend]=executable.relative_to(DEST).as_posix()
 for name in ['msvcp140.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll','vcomp140.dll']:copy(DEST/'runtime/sd'/name,DEST/'runtime/system/lib'/name)
 node=pathlib.Path(os.environ.get('FREEDOM_BUILD_NODE',str(ROOT/'vendor/node')))
 if not (node/'node.exe').is_file():raise ValueError('Set FREEDOM_BUILD_NODE to an official Windows Node.js runtime')
 tree(node,DEST/'runtime/node')
 wheelhouse=ROOT/'.cache/platforms/wheels/windows-x64'
 if not (wheelhouse/'manifest.json').is_file():raise ValueError('Prepare the offline repair wheels: packaging/fetch_wheels.py --target windows-x64')
 for item in json.loads((wheelhouse/'manifest.json').read_text()):
  file=wheelhouse/item['file']
  if file.stat().st_size!=item['bytes'] or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Repair wheel verification failed: '+file.name)
 tree(wheelhouse,DEST/'runtime/wheels');copy(ROOT/'packaging/requirements-portable.lock',DEST/'runtime/wheels/requirements.lock')
 (DEST/'runtime/native.json').write_text(json.dumps(native,indent=2))
 tree(ROOT/'licenses',DEST/'licenses')
 copy(HERMES/'LICENSE',DEST/'licenses/Hermes-MIT.txt');copy(PYBASE/'LICENSE.txt',DEST/'licenses/Python.txt')
 (DEST/'stack/hermes-runtime/SOUL.md').write_text('Ты — Freedom GPT, локальный помощник. Говори честно о доступных инструментах. Не обещай выполненную работу без фактического результата. Храни память проекта в выбранной рабочей папке. Интернет нужен только для внешних ресурсов и загрузок; модель работает локально.\n',encoding='utf8')
 commit=json.loads((donor/'freedom-bundle.json').read_text())['hermes_commit'] if donor else subprocess.check_output(['git','-C',str(HERMES),'rev-parse','HEAD'],text=True).strip()
 marker={'product':'Freedom GPT','version':json.loads((APP/'version.json').read_text())['version'],'platform':'Windows x64','hermes_commit':commit,'personal_data_included':False,'model_weights_included':False}
 (DEST/'freedom-bundle.json').write_text(json.dumps(marker,indent=2),encoding='utf8')
 # Publication is an allowlist operation: no source runtime directory is copied wholesale.
 forbidden=[]
 for p in DEST.rglob('*'):
  if p.is_file() and (p.name in {'auth.json','.env','state.db','interface.sqlite','gateway_state.json','config.yaml','install_id'} or p.suffix.lower() in {'.gguf','.safetensors'} or p.name.startswith('__editable__')):forbidden.append(str(p.relative_to(DEST)))
 if forbidden:raise RuntimeError('Private or model files in public bundle: '+str(forbidden[:20]))
 size=sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())
 (ROOT/'logs/bundle-build.json').write_text(json.dumps({**marker,'bytes':size,'root':str(DEST),'private_files_found':forbidden},indent=2),encoding='utf8');print('BUNDLE_BYTES',size,flush=True)
if __name__=='__main__':main()
