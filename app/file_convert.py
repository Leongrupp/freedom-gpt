"""Agent CLI for the same offline converter. Originals remain intact; outputs stay on A:."""
import argparse,json,os,pathlib,shutil,subprocess,sys,uuid
from file_converter import formats
ROOT=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Offline Freedom GPT file conversion')
parser.add_argument('files',nargs='+');parser.add_argument('--to',required=True,dest='target');parser.add_argument('--ocr',action='store_true');parser.add_argument('--merge',action='store_true')
parser.add_argument('--quality',choices=['small','balanced','high'],default='balanced');parser.add_argument('--video-size',type=int,choices=[0,720,1080],default=0)
args=parser.parse_args();jid=uuid.uuid4().hex;folder=ROOT/'uploads/converter'/jid;folder.mkdir(parents=True)
if len(args.files)>12:parser.error('At most 12 files per batch')
files=[]
for value in args.files:
    source=pathlib.Path(value).resolve();ext=source.suffix.lower()[1:]
    if not source.is_file() or args.target not in formats(ext):parser.error('Unsupported input/target: '+value+' -> '+args.target)
    target=folder/(str(len(files))+'.'+ext);shutil.copy2(source,target)
    files.append({'name':source.name,'path':str(target.relative_to(ROOT)),'bytes':target.stat().st_size})
spec={'id':jid,'target':args.target,'files':files,'options':{'ocr':args.ocr,'merge':args.merge,'quality':args.quality,'video_size':args.video_size}}
env=os.environ.copy();env.update(TEMP=str(ROOT/'.tmp'),TMP=str(ROOT/'.tmp'),TMPDIR=str(ROOT/'.tmp'),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
process=subprocess.run([str(ROOT/'runtime/converter/python/Scripts/python.exe'),'-I','-B',str(ROOT/'convert_worker.py')],input=json.dumps(spec),text=True,encoding='utf-8',capture_output=True,cwd=ROOT,env=env)
result=None
for line in process.stdout.splitlines():
    try:
        value=json.loads(line)
        if 'ok' in value:result=value
    except ValueError:pass
if not result or not result.get('ok'):
    print(json.dumps(result or {'ok':False,'error':process.stderr[-500:]},ensure_ascii=True));sys.exit(1)
for item in result['files']:item['path']=str(ROOT/item['path'])
print(json.dumps(result,ensure_ascii=True))
