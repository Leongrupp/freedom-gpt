"""Re-sign existing verified feeds; leave package bytes and previous releases untouched."""
import base64,json,pathlib,sys
from sign_update import signing_key,ROOT
sys.path.insert(0,str(ROOT/'app'))
from update_protocol import canonical,sha256,verify
def main():
 key=signing_key();version=json.loads((ROOT/'app/version.json').read_text())['version'];out=ROOT/'release/platforms'/version
 for feed,target in [(ROOT/'release/update.json','windows-x64'),(out/'update-ubuntu-x64.json','ubuntu-x64'),(out/'update-macos-arm64.json','macos-arm64')]:
  value=json.loads(feed.read_text());payload=value['payload'];assert payload['version']==version
  payload['base_version']='1.5.0';value['signature']=base64.b64encode(key.sign(canonical(payload))).decode()
  verify(value,(ROOT/'app/update-key.pub').read_text(),expected_platform=target)
  try:verify(value,(ROOT/'app/update-key.pub').read_text(),'1.4.2',expected_platform=target)
  except ValueError as error:
   if 'full release' not in str(error):raise
  else:raise ValueError('Legacy automatic update is not blocked')
  feed.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
  meta=ROOT/'release/release.json' if target=='windows-x64' else out/(target+'.json')
  data=json.loads(meta.read_text())
  for item in data['files']:
   if item['name']==feed.name:item.update(bytes=feed.stat().st_size,sha256=sha256(feed))
  meta.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Signed feeds block automatic migration from1.4.x; package contents unchanged.')
if __name__=='__main__':main()
