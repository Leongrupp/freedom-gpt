"""Gated domain TLS activation. Requires DNS and explicit permission for VPN routing."""
import argparse,hashlib,json,pathlib,shutil,socket,ssl,subprocess,time,urllib.request
WORK=pathlib.Path('/root/freedom-gpt-deploy');LIVE=pathlib.Path('/etc/freedom-gpt-tls')
UNIT='freedom-gpt-tls.service';IP='185.125.100.186';NAMES=['aionpc.ru','www.aionpc.ru']

def run(args,timeout=60):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(str(args[:2])+': '+r.stderr[-1000:])
 return r.stdout

def cert(port,name):
 with ssl.create_default_context().wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=10),server_hostname=name) as s:return hashlib.sha256(s.getpeercert(binary_form=True)).hexdigest()

def rules(action):
 interface=run(['ip','route','show','default']).split(' dev ',1)[1].split()[0]
 if not interface.replace('-','').replace('_','').isalnum():raise ValueError('Invalid interface')
 owned=[([], 'INPUT',['-i',interface,'-p','tcp','--dport','9443','-m','conntrack','--ctorigdstport','443','-m','comment','--comment','freedom-gpt-domain-tls','-j','ACCEPT']),
        (['-t','nat'],'PREROUTING',['-i',interface,'-p','tcp','--dport','443','-m','comment','--comment','freedom-gpt-domain-tls','-j','REDIRECT','--to-ports','9443'])]
 if action=='remove':owned.reverse()
 for table,chain,rule in owned:
  base=['iptables','-w','5',*table]
  present=subprocess.run([*base,'-C',chain,*rule],capture_output=True).returncode==0
  if action=='add' and not present:run([*base,'-I',chain,'1',*rule])
  if action=='remove' and present:run([*base,'-D',chain,*rule])

def route_test():
 req=urllib.request.Request('https://aionpc.ru:9443/healthz')
 # Use a TLS socket directly to loopback while validating the public domain certificate.
 with ssl.create_default_context().wrap_socket(socket.create_connection(('127.0.0.1',9443),timeout=10),server_hostname='aionpc.ru') as s:
  s.sendall(b'GET /healthz HTTP/1.1\r\nHost: aionpc.ru\r\nConnection: close\r\n\r\n');body=b''
  while True:
   block=s.recv(65536)
   if not block:break
   body+=block
  if b'200 OK' not in body.split(b'\r\n',1)[0] or b'Freedom GPT OK' not in body:raise RuntimeError('Website TLS check failed')
 if cert(443,'185-125-100-186.sslip.io')!=cert(9443,'185-125-100-186.sslip.io'):raise RuntimeError('VPN TLS passthrough differs')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--activate-with-vpn-routing-approved',action='store_true');p.add_argument('--rules',choices=['add','remove']);args=p.parse_args()
 if args.rules:
  try:
   if args.rules=='add':route_test()
   rules(args.rules)
  except Exception:
   rules('remove');raise
  return
 dns={name:sorted({x[4][0] for x in socket.getaddrinfo(name,80,socket.AF_INET)}) for name in NAMES}
 report={'dns':dns,'dns_ready':all(v==[IP] for v in dns.values()),'activation_requires_explicit_vpn_routing_approval':True,'vpn_config_or_process_restart':False}
 print(json.dumps(report),flush=True)
 if not args.activate_with_vpn_routing_approved:return
 if not report['dns_ready']:raise RuntimeError('DNS is not ready; no certificate request or routing change made')
 if not json.loads((WORK/'tls-router-qa/report.json').read_text())['passed']:raise RuntimeError('Loopback routing QA required')
 if pathlib.Path('/etc/systemd/system/'+UNIT).exists():raise RuntimeError('Existing TLS service needs a reviewed update')
 protected=[pathlib.Path(n) for n in ['/etc/accel-ppp.conf','/etc/ipsec.conf','/etc/ipsec.secrets']]
 before={str(n):hashlib.sha256(n.read_bytes()).hexdigest() for n in protected}
 services=run(['systemctl','show','accel-ppp','strongswan-starter','--property=Id,MainPID,ActiveState'])
 run(['certbot','certonly','--webroot','-w','/var/www/greenedge-acme','--cert-name','aionpc.ru','-d',NAMES[0],'-d',NAMES[1],'--non-interactive','--keep-until-expiring'],240)
 LIVE.mkdir(mode=0o700,exist_ok=False)
 module=WORK/'tls-router-qa/module/usr/lib/nginx/modules/ngx_stream_module.so';shutil.copy2(module,LIVE/'ngx_stream_module.so')
 shutil.copy2(__file__,LIVE/'finish_https.py')
 config=f'''load_module {LIVE}/ngx_stream_module.so;
user www-data;
pid /run/freedom-gpt-tls.pid;
error_log /var/log/nginx/freedom-gpt-tls-error.log warn;
worker_processes 1;
events {{ worker_connections 2048; }}
stream {{
 map $ssl_preread_server_name $target {{ aionpc.ru 127.0.0.1:9444; www.aionpc.ru 127.0.0.1:9444; default 127.0.0.1:443; }}
 server {{ listen 0.0.0.0:9443; ssl_preread on; proxy_connect_timeout 5s; proxy_timeout 24h; proxy_pass $target; }}
}}
http {{
 server {{ listen 127.0.0.1:9444 ssl; server_name aionpc.ru www.aionpc.ru;
 ssl_certificate /etc/letsencrypt/live/aionpc.ru/fullchain.pem;
 ssl_certificate_key /etc/letsencrypt/live/aionpc.ru/privkey.pem;
 ssl_protocols TLSv1.2 TLSv1.3;
 location / {{ proxy_pass http://127.0.0.1:80; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }}
 }}
}}
'''
 (LIVE/'nginx.conf').write_text(config);run(['nginx','-t','-c',str(LIVE/'nginx.conf')])
 unit=f'''[Unit]
Description=Freedom GPT domain TLS and SSTP passthrough
After=network-online.target nginx.service accel-ppp.service
BindsTo=nginx.service
[Service]
Type=simple
ExecStart=/usr/sbin/nginx -c {LIVE}/nginx.conf -g "daemon off;"
ExecStartPost=/usr/bin/python3 {LIVE}/finish_https.py --rules add
ExecStopPost=/usr/bin/python3 {LIVE}/finish_https.py --rules remove
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
TimeoutStartSec=45
TimeoutStopSec=30
[Install]
WantedBy=multi-user.target
'''
 unit_path=pathlib.Path('/etc/systemd/system')/UNIT;unit_path.write_text(unit)
 try:
  run(['systemctl','daemon-reload']);run(['systemctl','enable','--now',UNIT]);route_test()
  assert before=={str(n):hashlib.sha256(n.read_bytes()).hexdigest() for n in protected}
  assert services==run(['systemctl','show','accel-ppp','strongswan-starter','--property=Id,MainPID,ActiveState'])
 except Exception:
  subprocess.run(['systemctl','disable','--now',UNIT],capture_output=True);rules('remove');raise
 hook=pathlib.Path('/etc/letsencrypt/renewal-hooks/deploy/freedom-gpt-tls')
 hook.write_text('#!/bin/sh\ncase "$RENEWED_LINEAGE" in /etc/letsencrypt/live/aionpc.ru) systemctl reload freedom-gpt-tls.service ;; esac\n');hook.chmod(0o755)
 report.update(certificate_issued=True,domain_tls_active=True,vpn_configs_and_pids_unchanged=True,real_vpn_client_tested=False,rollback='systemctl disable --now '+UNIT)
 (WORK/'domain-tls-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
