"""Read-only audit of the declared public pages, metadata and crawler policy."""
import argparse,concurrent.futures,gzip,json,pathlib,sys,time,urllib.error,urllib.parse,urllib.request,urllib.robotparser,xml.etree.ElementTree as ET
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'site'))
from seo import PAGES,SITE,url
class Document(HTMLParser):
 def __init__(self):
  super().__init__();self.tags=[];self.title='';self.h1=0;self.jsonld=[];self.capture=None;self.buffer='';self.ids=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs);self.tags.append((tag,attrs))
  if attrs.get('id'):self.ids.append(attrs['id'])
  if tag=='h1':self.h1+=1
  if tag=='title' or (tag=='script' and attrs.get('type')=='application/ld+json'):self.capture=tag;self.buffer=''
 def handle_data(self,data):
  if self.capture:self.buffer+=data
 def handle_endtag(self,tag):
  if tag==self.capture:
   if tag=='title':self.title=self.buffer
   if tag=='script':self.jsonld.append(json.loads(self.buffer))
   self.capture=None
 def metas(self,key,value):return [a.get('content','') for t,a in self.tags if t=='meta' and a.get(key)==value]
 def links(self,rel):return [a for t,a in self.tags if t=='link' and a.get('rel')==rel]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--base',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
 base=args.base.rstrip('/')
 if base not in [SITE,'http://127.0.0.1:17908','http://127.0.0.1:17900']:raise ValueError('Only the known public site or owned preview is allowed')
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def fetch(path,agent='FreedomGPT-SiteAudit'):
  start=time.perf_counter();request=urllib.request.Request(base+path,headers={'User-Agent':agent,'Accept-Encoding':'gzip'})
  with opener.open(request,timeout=25) as response:
   ttfb=time.perf_counter()-start;data=response.read();headers=dict(response.headers);status=response.status
  if headers.get('Content-Encoding')=='gzip':data=gzip.decompress(data)
  return status,data,headers,round(ttfb*1000,1)
 checks={};documents={};details=[];resources=set();internal=set()
 def audit(item):
  lang,path=item;route='/'+('en/' if lang=='en' else '')+path;status,data,headers,ttfb=fetch(route)
  text=data.decode('utf-8');doc=Document();doc.feed(text);expected=url(lang,path)
  expected_alts={k:url(k,path) for k in ['ru','en']};expected_alts['x-default']=url('en',path)
  parsed_alts={a.get('hreflang'):a.get('href') for a in doc.links('alternate')}
  canonical=doc.links('canonical')
  graph=[node for block in doc.jsonld for node in block.get('@graph',[])]
  good={
   'http200':status==200,'html_mime':'text/html' in headers.get('Content-Type',''),
   'unique_h1':doc.h1==1,'title':bool(doc.title) and len(doc.title)<100,
   'description':len(doc.metas('name','description'))==1 and 50<=len(doc.metas('name','description')[0])<=230,
   'canonical':len(canonical)==1 and canonical[0].get('href')==expected,
   'hreflang':parsed_alts==expected_alts,
   'indexable':'noindex' not in text.lower() and 'noindex' not in headers.get('X-Robots-Tag','').lower(),
   'social':doc.metas('property','og:url')==[expected] and len(doc.metas('property','og:image'))==1,
   'structured_data':bool(graph) and any(n.get('@type')=='WebPage' and n.get('url')==expected for n in graph),
   'no_fabricated_ratings':not any('aggregateRating' in n or 'review' in n for n in graph),
   'unique_ids':len(doc.ids)==len(set(doc.ids)),
   'utf8': '\ufffd' not in text,
  }
  if not path:
   apps=[n for n in graph if n.get('@type')=='SoftwareApplication']
   good['free_app_schema']=len(apps)==1 and apps[0].get('isAccessibleForFree') is True and apps[0].get('offers',{}).get('price')=='0'
  else:good['breadcrumb_schema']=any(n.get('@type')=='BreadcrumbList' for n in graph)
  return route,doc,good,{'path':route,'bytes':len(data),'ttfb_ms_from_this_pc':ttfb}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for route,doc,good,detail in pool.map(audit,[(lang,path) for lang in ['ru','en'] for path in ['',*PAGES]]):
   documents[route]=doc;details.append(detail)
   checks.update({route+':'+key:value for key,value in good.items()})
   for tag,attrs in doc.tags:
    if tag in ['img','script'] and attrs.get('src','').startswith('/'):resources.add(attrs['src'].split('?')[0])
    if tag=='link' and attrs.get('rel') in ['stylesheet','icon'] and attrs.get('href','').startswith('/'):resources.add(attrs['href'].split('?')[0])
    if tag=='a':
     link=urllib.parse.urlsplit(attrs.get('href',''))
     if link.netloc in ['', 'aionpc.ru'] and link.path.startswith('/') and not link.path.startswith(('/api/','/downloads/','/models/')):internal.add(link.path)
 titles=[doc.title for doc in documents.values()];descs=[doc.metas('name','description')[0] for doc in documents.values()]
 checks['all_titles_unique']=len(set(titles))==len(titles);checks['all_descriptions_unique']=len(set(descs))==len(descs)
 for path in sorted(resources):checks['asset:'+path]=fetch(path)[0]==200
 # Full-size screenshot links are valid assets, with HTTP checked above.
 # Keep rejecting undeclared HTML routes and unverified file links.
 unresolved_internal=sorted(internal-(set(documents)|resources))
 checks['internal_links_resolve']=not unresolved_internal
 status,data,headers,_=fetch('/sitemap.xml');sitemap=ET.fromstring(data);ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9','x':'http://www.w3.org/1999/xhtml'}
 entries=sitemap.findall('s:url',ns);locs=[entry.findtext('s:loc',namespaces=ns) for entry in entries]
 checks['sitemap_all_canonical_pages']=status==200 and len(locs)==len(documents) and set(locs)=={SITE+path for path in documents}
 checks['sitemap_language_alternates']=all(len(entry.findall('x:link',ns))==3 for entry in entries)
 status,robots,_,_=fetch('/robots.txt');policy=urllib.robotparser.RobotFileParser();policy.parse(robots.decode().splitlines())
 checks['robots_sitemap']=SITE+'/sitemap.xml' in robots.decode()
 bots=['Googlebot','Yandex','Bingbot','OAI-SearchBot','ChatGPT-User','PerplexityBot','Google-Extended']
 for bot in bots:
  checks['robots_all_public_pages:'+bot]=all(policy.can_fetch(bot,SITE+path) for path in documents)
  checks['api_disallowed:'+bot]=not policy.can_fetch(bot,SITE+'/api/release')
  checks['bot_http_access:'+bot]=fetch('/guides/local-ai/',bot)[0]==200
 checks['llms_optional_reference']=fetch('/llms.txt')[0]==200
 try:fetch('/this-page-does-not-exist-seo-check/');checks['real_404']=False
 except urllib.error.HTTPError as exc:checks['real_404']=exc.code==404
 report={'passed':all(checks.values()),'checked_at':time.time(),'base':base,'pages':len(documents),'checks':checks,'unresolved_internal_links':unresolved_internal,'page_transfers':details,'core_web_vitals_field_data_measured':False,'indexing_or_ranking_verified':False,'schema_rich_result_eligibility_claimed':False}
 destination=ROOT/args.report
 if not destination.resolve().is_relative_to(ROOT):raise ValueError('Report must stay inside project')
 destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'pages':len(documents),'checks':len(checks),'failed':[k for k,v in checks.items() if not v],'report':str(destination)}))
 raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
