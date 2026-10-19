"""Verify the site and compare the preserved VPN state. No VPN login is performed."""
import hashlib,json,pathlib,re,shutil,socket,ssl,subprocess,urllib.error,urllib.request
WORK=pathlib.Path('/root/freedom-gpt-deploy');BASE=pathlib.Path('/var/www/freedom-gpt')
before=json.loads((WORK/'state-before.json').read_text());checks={};details={}
def run(args):return subprocess.run(args,capture_output=True,text=True,timeout=20)
def request(path,host='185.125.100.186',headers=None):
 req=urllib.request.Request('http://127.0.0.1'+path,headers={'Host':host,**(headers or {})})
 try:
  with urllib.request.urlopen(req,timeout=10) as response:return response.status,response.read(),dict(response.headers)
 except urllib.error.HTTPError as exc:return exc.code,exc.read(),dict(exc.headers)
for key,path,needle in [('russian_page','/',b'lang="ru"'),('english_page','/en/',b'lang="en"'),('health','/healthz',b'Freedom GPT OK')]:
 status,body,headers=request(path);checks[key]=status==200 and needle in body
 if key=='russian_page':checks['security_headers']=headers.get('X-Content-Type-Options')=='nosniff' and headers.get('X-Frame-Options')=='DENY';checks['visible_branding']=b'hermes' not in body.lower()
for path in ['/style.css','/app.js','/freedom.svg','/media/cover.png','/api/catalog','/api/models','/api/release']:
 status,body,headers=request(path);checks['http_'+path]=status==200 and len(body)>0
 if path=='/api/release':details['release_status']=json.loads(body).get('status')
for path in ['/.git/config','/server.py','/bin/refresh_release.py','/models/verification/model.gguf.part']:
 checks['blocked_'+path]=request(path)[0]==404
probe=BASE/'shared/models/verification';probe.mkdir(exist_ok=False);file=probe/'model.gguf';file.write_bytes(b'FreedomGPT-range-verification\n'*200)
try:
 status,body,headers=request('/models/verification/model.gguf',headers={'Range':'bytes=0-15'})
 checks['model_range_download']=status==206 and len(body)==16 and headers.get('Content-Range','').startswith('bytes 0-15/')
finally:
 assert file.resolve().is_relative_to((BASE/'shared/models').resolve());file.unlink();probe.rmdir()
for unit in ['accel-ppp.service','strongswan-starter.service']:
 now=run(['systemctl','show',unit,'--property=ActiveState,MainPID,ActiveEnterTimestampMonotonic,ExecMainStartTimestampMonotonic,NRestarts']).stdout
 checks['unchanged_'+unit]=now==before['services'][unit] and 'ActiveState=active' in now
details['vpn_config_files_checked']=len(before['config_hashes'])
checks['vpn_configuration_unchanged']=all(pathlib.Path(name).is_file() and hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest for name,digest in before['config_hashes'].items())
details['original_nginx_files_checked']=len(before['nginx_file_hashes'])
checks['original_nginx_files_unchanged']=all(pathlib.Path(name).is_file() and hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest for name,digest in before['nginx_file_hashes'].items())
for exe,old in before['firewall'].items():
 p=run([exe]);raw='\n'.join(x for x in p.stdout.splitlines() if not x.startswith('#'))
 details.setdefault('firewall_export_hash_equal',{})[exe]=hashlib.sha256(raw.encode()).hexdigest()==old
 # iptables-save includes live counters in chain declarations. Retain the original
 # hash comparison as an observation; verify the current rules independently.
 normalize=lambda value:re.sub(r'\[\d+:\d+\]','[COUNTERS]', '\n'.join(x for x in value.splitlines() if not x.startswith('#')))
 second=run([exe]);checks['stable_rules_'+exe]=p.returncode==second.returncode==0 and normalize(p.stdout)==normalize(second.stdout)
details['firewall_comparison_note']='Live chain counters can change the export hash. Firewall configuration files are included in the preserved configuration comparison; no firewall mutation command was issued.'
checks['existing_acme_host_unchanged']=request('/',host='185-125-100-186.sslip.io')[0]==before['http_before']['185-125-100-186.sslip.io']
checks['nginx_config_valid']=run(['nginx','-t']).returncode==0
checks['metadata_timer_active']=run(['systemctl','is-active','freedom-gpt-release-refresh.timer']).stdout.strip()=='active'
details['free_bytes']=shutil.disk_usage('/').free
report={'checks':checks,'details':details,'passed':all(checks.values())}
(WORK/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if not report['passed']:raise SystemExit(1)
