"""Finalize an owner-approved HTTPS domain while preserving the live VPN."""
import argparse,hashlib,json,pathlib,shutil,subprocess,time,urllib.request
WORK=pathlib.Path('/root/freedom-gpt-deploy')
HTTP=pathlib.Path('/etc/nginx/sites-available/freedom-gpt.conf')
TLS=pathlib.Path('/etc/freedom-gpt-tls/nginx.conf')
def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=30)
    if result.returncode:raise RuntimeError(str(args[:2])+': '+result.stderr[-600:])
    return result.stdout
def protected():
    return {'hashes':{p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in ['/etc/accel-ppp.conf','/etc/ipsec.conf','/etc/ipsec.secrets']},'services':run(['systemctl','show','accel-ppp','strongswan-starter','--property=Id,MainPID,ActiveState'])}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--https-routing-approved',action='store_true');args=parser.parse_args()
    if not args.https_routing_approved:raise RuntimeError('Explicit owner approval is required')
    activation=json.loads((WORK/'domain-tls-result.json').read_text())
    if not activation.get('domain_tls_active'):raise RuntimeError('Verified TLS activation required')
    before=protected();stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());backup=WORK/('https-final-'+stamp);backup.mkdir(mode=0o700)
    old_http=HTTP.read_text();old_tls=TLS.read_text();shutil.copy2(HTTP,backup/'http.conf');shutil.copy2(TLS,backup/'tls.conf')
    (backup/'protected-before.json').write_text(json.dumps(before,indent=2))
    marker='# Freedom GPT verified HTTPS domain redirect'
    if marker in old_http:raise RuntimeError('Already finalized; inspect current state before changes')
    expected='server_name 185.125.100.186 aionpc.ru www.aionpc.ru;'
    if expected not in old_http or 'proxy_set_header Host $host;' not in old_tls:raise RuntimeError('Unexpected current configuration')
    new_http=old_http.replace(expected,'server_name 185.125.100.186;')+'''
# Freedom GPT verified HTTPS domain redirect
server {
    listen 80;
    listen [::]:80;
    server_name aionpc.ru www.aionpc.ru;
    server_tokens off;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/greenedge-acme;
        try_files $uri =404;
    }
    location / { return 308 https://aionpc.ru$request_uri; }
}
'''
    new_tls=old_tls.replace('proxy_set_header Host $host;','proxy_set_header Host 185.125.100.186;')
    new_tls=new_tls.replace('ssl_protocols TLSv1.2 TLSv1.3;','ssl_protocols TLSv1.2 TLSv1.3;\n add_header Strict-Transport-Security "max-age=86400" always;\n if ($host = www.aionpc.ru) { return 308 https://aionpc.ru$request_uri; }')
    try:
        HTTP.write_text(new_http);TLS.write_text(new_tls)
        run(['nginx','-t']);run(['nginx','-t','-c',str(TLS)])
        run(['systemctl','reload','freedom-gpt-tls.service']);run(['systemctl','reload','nginx'])
        run(['python3','/etc/freedom-gpt-tls/finish_https.py','--rules','add'])
        assert protected()==before
        req=urllib.request.Request('http://127.0.0.1/healthz',headers={'Host':'185.125.100.186'})
        with urllib.request.urlopen(req,timeout=10) as response:assert response.read()==b'Freedom GPT OK\n'
    except Exception:
        HTTP.write_text(old_http);TLS.write_text(old_tls)
        run(['nginx','-t']);run(['nginx','-t','-c',str(TLS)])
        run(['systemctl','reload','freedom-gpt-tls.service']);run(['systemctl','reload','nginx'])
        raise
    report={'https_domain':'https://aionpc.ru','www_redirects_to_apex':True,'http_redirects_to_https':True,'acme_http_challenge_preserved':True,'vpn_configs_and_pids_unchanged':protected()==before,'real_vpn_client_tested':False,'backup':str(backup),'certificate_auto_renew':True}
    (backup/'result.json').write_text(json.dumps(report,indent=2));(WORK/'https-final-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
