"""Notify IndexNow once for changed, verified public pages; never promise indexing."""
import hashlib,json,pathlib,time,urllib.error,urllib.request,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent.parent
def main():
 config=json.loads((ROOT/'.private/seo-indexnow.json').read_text(encoding='utf-8'))
 audit=json.loads((ROOT/'logs/seo-live-20261020.json').read_text(encoding='utf-8'))
 if not audit.get('passed') or audit.get('base')!='https://aionpc.ru':raise RuntimeError('Verified live SEO audit required')
 host=config['host'];key=config['key'];base='https://'+host
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(base+'/'+key+'.txt',timeout=20) as r:
  if r.read().decode().strip()!=key:raise RuntimeError('Public verification file mismatch')
 with opener.open(base+'/sitemap.xml',timeout=20) as r:data=r.read()
 sitemap=ET.fromstring(data);urls=[n.text for n in sitemap.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
 if len(urls)!=12 or any(not url.startswith(base+'/') for url in urls):raise ValueError('Unexpected sitemap')
 fingerprint=hashlib.sha256(data).hexdigest();record=ROOT/'logs/indexnow-submission.json'
 if record.is_file():
  previous=json.loads(record.read_text())
  if previous.get('sitemap_sha256')==fingerprint and previous.get('received'):
   print(json.dumps({'skipped_unchanged':True,'previous_status':previous['http_status']}));return
 payload={'host':host,'key':key,'keyLocation':base+'/'+key+'.txt','urlList':urls}
 request=urllib.request.Request('https://api.indexnow.org/indexnow',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json; charset=utf-8','User-Agent':'FreedomGPT-SitePublisher'},method='POST')
 try:
  with opener.open(request,timeout=35) as r:status=r.status;response=r.read(500).decode('utf-8',errors='replace')
 except urllib.error.HTTPError as exc:status=exc.code;response=exc.read(500).decode('utf-8',errors='replace')
 report={'time':time.time(),'endpoint':'https://api.indexnow.org/indexnow','url_count':len(urls),'http_status':status,'received':status in [200,202],'key_validation_pending':status==202,'sitemap_sha256':fingerprint,'indexing_guaranteed':False,'response':response.replace(key,'[redacted]')}
 record.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
 raise SystemExit(0 if report['received'] else 1)
if __name__=='__main__':main()
