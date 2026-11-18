"""Parse a public RSS response as data, outside the visited page's script policy."""
import json,re,sys,xml.etree.ElementTree as ET

def parse(xml,limit=5):
    if len(xml)>3_000_000 or re.search(r'<!DOCTYPE|<!ENTITY',xml,re.I):raise ValueError('Unsupported RSS document')
    root=ET.fromstring(xml)
    if root.tag.rsplit('}',1)[-1].lower()!='rss':return []
    rows=[]
    for item in root.findall('./channel/item'):
        value=lambda tag:(item.findtext(tag) or '').strip()
        url=value('link');title=value('title')
        if not title or not re.match(r'^https?://',url,re.I):continue
        source=item.find('source')
        rows.append({'title':title,'url':url,'description':re.sub(r'<[^>]*>',' ',value('description'))[:1000],
            'published':value('pubDate') or None,'publisher':value('source') or None,'source_url':source.get('url') if source is not None else None,'position':len(rows)+1})
        if len(rows)>=limit:break
    return rows

if __name__=='__main__':
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(parse(sys.stdin.read(3_000_001),max(1,min(10,int(sys.argv[1]) if len(sys.argv)>1 else 5))),ensure_ascii=False))
