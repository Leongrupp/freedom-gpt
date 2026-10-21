"""CLI fallback for existing chats whose tool list was pinned before preview was added."""
import argparse,json,os,pathlib,sys,urllib.request

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')

root=pathlib.Path(os.environ.get('FREEDOM_ROOT') or pathlib.Path(__file__).resolve().parent.parent)
parser=argparse.ArgumentParser(description='Freedom GPT shared browser preview')
parser.add_argument('--session',required=True)
parser.add_argument('--action',required=True,choices=['open','look','inspect','screenshot','click','fill','press','scroll','viewport','reload','back','forward','status','close'])
for field in ['url','question','ref','text','key']:parser.add_argument('--'+field)
for field in ['x','y','dy','width','height']:parser.add_argument('--'+field,type=int)
args=vars(parser.parse_args());sid=args.pop('session');data={k:v for k,v in args.items() if v is not None}
route=json.loads((root/'data/preview-control.json').read_text(encoding='utf-8'))
request=urllib.request.Request(route['url']+'/'+sid,data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+route['key'],'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request,timeout=50) as response:result=json.load(response)
print(json.dumps(result,ensure_ascii=False))
