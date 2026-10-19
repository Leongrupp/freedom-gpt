"""Structured image-job adapter; the prompt is read as data, never shell code."""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
import bootstrap
CREATIVE=bootstrap.STACK/'creative-kit'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('request',help='JSON job in Freedom GPT/data/image-requests')
args=parser.parse_args()
path=pathlib.Path(args.request).resolve()
if not path.is_relative_to((ROOT/'data/image-requests').resolve()) or not path.is_file():
    raise SystemExit('Invalid local image request')
request=json.loads(path.read_text(encoding='utf-8'))
if not isinstance(request.get('prompt'),str) or not 1<=len(request['prompt'])<=12000:
    raise SystemExit('Invalid image prompt')
sys.path.insert(0,str(CREATIVE))
from importlib.machinery import SourceFileLoader
module=SourceFileLoader('freedom_local_image',str(CREATIVE/'image-tool.py')).load_module()
result=module.generate(request['prompt'],aspect_ratio='square',output=ROOT/'output/images'/path.stem/'image.png')
print(json.dumps(result,ensure_ascii=False))
