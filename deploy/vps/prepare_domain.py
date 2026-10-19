"""Prepare HTTP domain/ACME and platform metadata. Never touches VPN routing."""
import hashlib,json,pathlib,shutil,subprocess,time,urllib.request
WORK=pathlib.Path('/root/freedom-gpt-deploy')
CONF=pathlib.Path('/etc/nginx/sites-available/freedom-gpt.conf')
PROTECTED=['/etc/accel-ppp.conf','/etc/ipsec.conf','/etc/ipsec.secrets']

def run(args):
 r=subprocess.run(args,text=True,capture_output=True,timeout=60)
 if r.returncode:raise RuntimeError(r.stderr[-1200:])
 return r.stdout

def vpn_state():
 return {'hashes':{n:hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest() for n in PROTECTED},'services':run(['systemctl','show','accel-ppp','strongswan-starter','--property=Id,MainPID,ActiveState'])}

def main():
 before=vpn_state();old=CONF.read_text();stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());backup=WORK/('domain-backup-'+stamp);backup.mkdir(mode=0o700)
 shutil.copy2(CONF,backup/CONF.name)
 text=old.replace('server_name 185.125.100.186;', 'server_name 185.125.100.186 aionpc.ru www.aionpc.ru;')
 if 'location = /api/platforms' not in text:
  text=text.replace('    location = /api/catalog {','    location = /api/platforms {\n        alias /var/www/freedom-gpt/shared/metadata/platforms.json;\n        default_type application/json;\n        expires -1;\n    }\n    location = /api/catalog {')
 if 'aionpc.ru' not in text or 'location = /api/platforms' not in text:raise ValueError('Unexpected Freedom GPT vhost')
 # ACME uses the existing HTTP/80 webroot. No certificate request before DNS.
 if '/var/www/greenedge-acme' not in text:raise ValueError('Expected ACME webroot missing')
 refresh=pathlib.Path('/var/www/freedom-gpt/current/bin/refresh_release.py')
 if refresh.exists():shutil.copy2(refresh,backup/'refresh_release.py')
 try:
  CONF.write_text(text);run(['nginx','-t']);run(['systemctl','reload','nginx'])
  shutil.copy2(WORK/'refresh_release.py',refresh);run(['python3',str(refresh)])
  req=urllib.request.Request('http://127.0.0.1/api/platforms',headers={'Host':'aionpc.ru'})
  with urllib.request.urlopen(req,timeout=10) as response:platforms=json.load(response)
  assert platforms.get('platforms') and vpn_state()==before
 except Exception:
  CONF.write_text(old);run(['nginx','-t']);run(['systemctl','reload','nginx'])
  if (backup/'refresh_release.py').exists():shutil.copy2(backup/'refresh_release.py',refresh)
  raise
 report={'http_domain_prepared':True,'vpn_unchanged':vpn_state()==before,'https_certificate_issued':False,'public_443_routing_changed':False,'backup':str(backup),'platform_version':platforms.get('version')}
 (WORK/'domain-preparation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
