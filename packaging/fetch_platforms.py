"""Resumable downloads of reviewed, pinned upstream runtimes; never model weights."""
import concurrent.futures,hashlib,json,pathlib,time
import requests
ROOT=pathlib.Path(__file__).resolve().parent.parent;CACHE=ROOT/'.cache/platforms/downloads'
def digest(path):
 value=hashlib.sha256()
 with path.open('rb') as source:
  for chunk in iter(lambda:source.read(4*1024**2),b''):value.update(chunk)
 return value.hexdigest()
def fetch(item):
 CACHE.mkdir(parents=True,exist_ok=True);final=CACHE/item['file'];partial=final.with_name(final.name+'.part')
 if final.is_file():
  if final.stat().st_size==item['bytes'] and digest(final)==item['sha256']:return final.name
  raise ValueError('An existing runtime failed verification and was preserved: '+str(final))
 for attempt in range(8):
  start=partial.stat().st_size if partial.exists() else 0
  if start>item['bytes']:raise ValueError('Oversized preserved runtime partial')
  try:
   while start<item['bytes']:
    end=min(start+8*1024**2,item['bytes'])-1
    with requests.get(item['url'],params={'download':'1','offset':start},headers={'User-Agent':'FreedomGPT local build','Range':f'bytes={start}-{end}'},stream=True,timeout=(20,45)) as response:
     response.raise_for_status()
     if response.status_code!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {start}-{end}/'):raise ValueError('Bounded resume rejected; partial preserved')
     with partial.open('ab') as target:
      for chunk in response.iter_content(128*1024):
       if target.tell()+len(chunk)>end+1:raise ValueError('Oversized runtime range')
       target.write(chunk)
    start=partial.stat().st_size
    print('RUNTIME '+item['file']+' '+str(round(start/item['bytes']*100,1))+'%',flush=True)
   if partial.stat().st_size!=item['bytes'] or digest(partial)!=item['sha256']:raise ValueError('Runtime size or SHA256 mismatch; partial preserved')
   partial.replace(final);print('VERIFIED '+final.name,flush=True);return final.name
  except requests.RequestException:
   if attempt==7:raise
   time.sleep(min(15,attempt+2))
 raise RuntimeError('Runtime not downloaded')
def main():
 lock=json.loads((ROOT/'packaging/native-lock.json').read_text());items={i['file']:i for components in lock['targets'].values() for i in components.values()}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:verified=list(pool.map(fetch,items.values()))
 report={'verified':verified,'model_downloads_started':False};(ROOT/'logs/platform-runtime-downloads.json').write_text(json.dumps(report,indent=2));print('ALL RUNTIMES VERIFIED',flush=True)
if __name__=='__main__':main()
