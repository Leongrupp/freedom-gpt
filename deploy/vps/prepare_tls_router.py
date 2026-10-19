"""Prove SNI routing on LOOPBACK ONLY. Never changes the live VPN or firewall."""
import hashlib,json,pathlib,socket,ssl,subprocess,time
WORK=pathlib.Path('/root/freedom-gpt-deploy');QA=WORK/'tls-router-qa'
def run(args,timeout=60):
 r=subprocess.run(args,cwd=QA,capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(str(args[:3])+': '+r.stderr[-1200:])
 return r.stdout
def state():
 files={}
 for name in ['/etc/accel-ppp.conf','/etc/ipsec.conf','/etc/ipsec.secrets','/etc/nginx']:
  p=pathlib.Path(name)
  for f in sorted(p.rglob('*')) if p.is_dir() else [p]:
   if f.is_file():files[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 services=subprocess.check_output(['systemctl','show','nginx','accel-ppp','strongswan-starter','--property=Id,MainPID,ActiveState'],text=True)
 return {'hashes':files,'services':services}
def certificate(port):
 with ssl.create_default_context().wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=10),server_hostname='185-125-100-186.sslip.io') as s:return hashlib.sha256(s.getpeercert(binary_form=True)).hexdigest()
def main():
 QA.mkdir(parents=True,exist_ok=True);before=state();started=False
 version=subprocess.check_output(['dpkg-query','-W','-f=${Version}','nginx'],text=True).strip()
 if not list(QA.glob('libnginx-mod-stream_*.deb')):run(['apt-get','-o','Acquire::Retries=1','-o','Acquire::http::Timeout=15','download','libnginx-mod-stream='+version],90)
 deb=next(QA.glob('libnginx-mod-stream_*.deb'));run(['dpkg-deb','-x',str(deb),str(QA/'module')])
 module=QA/'module/usr/lib/nginx/modules/ngx_stream_module.so';cert=QA/'qa.crt';key=QA/'qa.key';cfg=QA/'nginx.conf'
 if not cert.exists():run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=aionpc.ru','-addext','subjectAltName=DNS:aionpc.ru,DNS:www.aionpc.ru'])
 key.chmod(0o600)
 cfg.write_text(f'''load_module {module};
pid {QA}/nginx.pid;
error_log {QA}/error.log warn;
worker_processes 1;
events {{ worker_connections 128; }}
stream {{
 map $ssl_preread_server_name $freedom_target {{
  aionpc.ru 127.0.0.1:9444;
  www.aionpc.ru 127.0.0.1:9444;
  default 127.0.0.1:443;
 }}
 server {{ listen 127.0.0.1:9443; ssl_preread on; proxy_connect_timeout 5s; proxy_timeout 24h; proxy_pass $freedom_target; }}
}}
http {{ access_log off; server {{
 listen 127.0.0.1:9444 ssl;
 server_name aionpc.ru www.aionpc.ru;
 ssl_certificate {cert}; ssl_certificate_key {key};
 default_type text/plain;
 return 200 "FREEDOM_TLS_QA_OK\\n";
}} }}
''')
 run(['nginx','-t','-c',str(cfg)])
 try:
  run(['nginx','-c',str(cfg)]);started=True;time.sleep(.2)
  response=run(['curl','--silent','--show-error','--fail','--noproxy','*','--cacert',str(cert),'--resolve','aionpc.ru:9443:127.0.0.1','https://aionpc.ru:9443/'])
  checks={'domain_tls_routes_to_web':response.strip()=='FREEDOM_TLS_QA_OK','vpn_tls_passes_through_unchanged':certificate(443)==certificate(9443)}
 finally:
  if started:run(['nginx','-c',str(cfg),'-s','quit'])
 checks['protected_live_services_and_config_unchanged']=before==state()
 report={'checks':checks,'passed':all(checks.values()),'public_routing_enabled':False,'firewall_changed':False,'vpn_restarted':False,'module_deb':str(deb),'module_sha256':hashlib.sha256(deb.read_bytes()).hexdigest()}
 (QA/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
