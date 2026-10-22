"""Native execution of the exact macOS release archive, with a loopback model fixture.

Tests installation, private runtimes, engine loading, the actual gateway, a saved
chat and restart. It does not claim a GPU inference or media-generation benchmark.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
import platform
import plistlib
import subprocess
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'.tmp/native-macos'
SPEC = json.loads((ROOT/'packaging/native-validation.json').read_text())
VERSION = SPEC['version']
CHECKS = {}
DETAILS = {'os':platform.platform(), 'architecture':platform.machine(),
           'model_generation_tested':False, 'media_generation_tested':False}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, value):
        raw = json.dumps(value).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_json({'data':[{'id':'freedom-native-qa','object':'model'}], 'status':'ok'})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        if body.get('stream'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Connection', 'close')
            self.end_headers()
            chunks = [
                {'choices':[{'index':0,'delta':{'role':'assistant','content':'Native QA acknowledgement.'},'finish_reason':None}]},
                {'choices':[{'index':0,'delta':{},'finish_reason':'stop'}],
                 'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}},
            ]
            for chunk in chunks:
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
            self.close_connection = True
        else:
            self.send_json({'id':'native-qa','object':'chat.completion',
                'choices':[{'index':0,'message':{'role':'assistant','content':'Native QA acknowledgement.'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}})


def run(args, *, cwd=None, timeout=180):
    p = subprocess.run(list(map(str,args)), cwd=cwd or ROOT, env=ENV,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(str(args[0])+': '+p.stderr[-1600:])
    return p.stdout


def api(path, body=None, token=None):
    req = urllib.request.Request('http://127.0.0.1:19166/api/'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json', **({'X-Freedom-Token':token} if token else {})})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)


def launch():
    run([PY,'-B','-s',TARGET/'launch.py','--no-browser'], cwd=TARGET)
    deadline=time.monotonic()+150
    while time.monotonic()<deadline:
        try:
            if api('health').get('gateway_ready'):
                return
        except OSError:
            pass
        time.sleep(.5)
    raise RuntimeError('Gateway did not become ready.')


ENV = os.environ.copy()
for name in ['PYTHONPATH','HERMES_HOME','HERMES_RUNTIME_DIR','FREEDOM_ROOT','FREEDOM_STACK']:
    ENV.pop(name, None)
ENV.update(TEMP=str(WORK), TMP=str(WORK), TMPDIR=str(WORK), PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
TARGET=WORK/'installed'
PY=TARGET/'runtime/python/bin/python3'
FIXTURE=None
COMPLETED=False
try:
    assert platform.system()=='Darwin' and platform.machine()=='arm64'
    archive=WORK/SPEC['macos']['file']
    digest=hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):
            digest.update(block)
    digest=digest.hexdigest()
    assert digest==SPEC['macos']['sha256']
    CHECKS['exact_release_sha256']=True
    run(['ditto','-x','-k',archive,WORK/'unpacked'])
    bundle=WORK/'unpacked/Freedom GPT.app'
    info=plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
    assert info['CFBundleShortVersionString']==VERSION
    CHECKS['app_bundle_version']=True
    source=bundle/'Contents/Resources/App'
    run([source/'runtime/python/bin/python3','-B','-s',source/'runtime/freedom/portable_install.py',
         '--source',source,'--target',TARGET,'--install-only'])
    CHECKS['native_portable_install']=True
    run([PY,'-B','-s','-c','import psutil,requests,PIL.Image,cryptography,openai,mcp,qrcode; print("private imports OK")'],cwd=TARGET)
    CHECKS['native_python_dependencies']=True
    native=json.loads((TARGET/'runtime/native.json').read_text())
    run([TARGET/'runtime/node/bin/node','--version'])
    CHECKS['native_node']=True
    for family in ['llama','sd']:
        engine=native['engines'][family].get('metal') or native['engines'][family].get('cpu')
        assert engine
        result=run([TARGET/engine,'--help'],cwd=TARGET)
        CHECKS[family+'_native_engine_loads']=bool(result.strip())
    FIXTURE=ThreadingHTTPServer(('127.0.0.1',19179),Fixture)
    threading.Thread(target=FIXTURE.serve_forever,daemon=True).start()
    (TARGET/'data').mkdir(exist_ok=True)
    (TARGET/'data/settings.json').write_text(json.dumps({'onboarded':True,'auto_update':False,
        'ui_port':19166,'model_port':19171,'external_url':'http://127.0.0.1:19179/v1',
        'external_model':'freedom-native-qa','external_context':65536}))
    launch()
    CHECKS['native_ui_and_gateway']=True
    assert api('sessions')['sessions']==[]
    CHECKS['clean_history']=True
    boot=api('bootstrap');assert boot['version']==VERSION
    token=boot['token']
    sid=api('sessions',{'title':'Native macOS release check','access':'manual'},token)['id']
    CHECKS['chat_creation']=bool(sid)
    assert api('phone')['enabled'] is False
    assert not (TARGET/'data/remote-device.key').exists()
    CHECKS['phone_opt_in']=True
    assert api('updates')['manual_only'] is True
    CHECKS['manual_updates']=True
    api('sessions/'+sid+'/messages',{'text':'Return one acknowledgement; no tools.',
        'input_id':'native-macos-release-check','mode':'code','files':[]},token)
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        snapshot=api('sessions/'+sid)
        text=json.dumps(snapshot,ensure_ascii=False)
        if 'Native QA acknowledgement.' in text and not snapshot.get('running'):
            break
        time.sleep(.5)
    else:
        raise RuntimeError('Native gateway fixture reply was not persisted.')
    CHECKS['gateway_turn_and_persistence']=True
    run([PY,'-B','-s',TARGET/'stop.py'],cwd=TARGET)
    launch()
    assert sid in {s['id'] for s in api('sessions')['sessions']}
    CHECKS['restart_preserves_chat']=True
    COMPLETED=True
except Exception as exc:
    DETAILS['error']=str(exc)[-1600:]
    raise
finally:
    if PY.is_file():
        subprocess.run([str(PY),'-B','-s',str(TARGET/'stop.py')],cwd=TARGET,env=ENV,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45)
    if FIXTURE:
        FIXTURE.shutdown()
    report={'version':VERSION,'platform':'macos-arm64','checks':CHECKS,'details':DETAILS,
            'passed':COMPLETED and len(CHECKS)>=12 and all(CHECKS.values())}
    print('FREEDOM_NATIVE_RESULT='+json.dumps(report,ensure_ascii=False),flush=True)
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
            summary.write('## Freedom GPT '+VERSION+' native macOS check\n\n')
            summary.write('Archive SHA256 verified. No personal data or model weights used.\n\n')
            for key,value in CHECKS.items():
                summary.write('- '+('PASS' if value else 'FAIL')+' '+key+'\n')
assert report['passed'], report
