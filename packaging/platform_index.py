"""Assemble a local download index only; never publishes or uploads."""
import json,pathlib,shutil
from platform_bundle import ROOT,VERSION,sha

def main():
 out=ROOT/'release/platforms'/VERSION;release=json.loads((ROOT/'release/release.json').read_text(encoding='utf-8'))
 for kind in ['windows-clean-pc-verification','ubuntu-clean-pc-verification','ubuntu-installers-verification','platform-artifacts-verification']:
  name=kind+'-'+VERSION+'.json'
  if not json.loads((ROOT/'logs'/name).read_text()).get('passed'):raise ValueError('Passed verification required: '+name)
 for item in release['files']:
  file=ROOT/'release'/item['name'];target=out/file.name
  if file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:raise ValueError('Windows release integrity: '+file.name)
  shutil.copy2(file,target)
 (out/'windows-x64.json').write_text(json.dumps({'version':VERSION,'platform':'windows-x64','files':release['files'],'published':False,'core_runtime_tested':True},indent=2))
 notes={
  'windows-x64':('Windows 10/11 x64','Проверено на Windows 11. Python, Node.js и движки внутри. Модели отдельно.','Tested on Windows 11. Python, Node.js and engines included; models separate.'),
  'ubuntu-x64':('Ubuntu 24.04 x64','Проверено без Python и сети в чистом контейнере. GPU требует драйвера.','Tested offline in a clean container without system Python. GPU needs a driver.'),
  'macos-arm64':('macOS · Apple Silicon','macOS 26.2+, M1+. Кандидат без подписи; запуск на Mac ещё не проверен.','macOS 26.2+, M1+. Unsigned candidate; native Mac execution not yet tested.')}
 platforms=[];all_files=[]
 for target,(name,ru,en) in notes.items():
  meta=json.loads((out/(target+'.json')).read_text());public=[]
  for item in meta['files']:
   file=out/item['name']
   if file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:raise ValueError('Release changed: '+file.name)
   all_files.append(item)
   if 'update' in file.name.lower() or 'source' in file.name.lower():continue
   fmt='EXE installer' if file.suffix=='.exe' else 'DEB' if file.suffix=='.deb' else '.run installer' if file.suffix=='.run' else 'TAR.GZ portable' if file.name.endswith('.tar.gz') else '.app ZIP' if target.startswith('macos') else 'ZIP portable'
   public.append({**{k:item[k] for k in ['name','bytes','sha256']},'format':fmt,'url':'/downloads/platform/'+file.name})
  platforms.append({'id':target,'name':name,'note_ru':ru,'note_en':en,'files':public,'native_tested':target!='macos-arm64'})
 matrix={'product':'Freedom GPT','version':VERSION,'published':False,'platforms':platforms}
 (out/'platforms.json').write_text(json.dumps(matrix,ensure_ascii=False,indent=2),encoding='utf-8')
 unique={f['name']:f for f in all_files};(out/'SHA256SUMS.txt').write_text(''.join(f['sha256']+'  '+f['name']+'\n' for f in sorted(unique.values(),key=lambda f:f['name'])),encoding='ascii')
 shutil.copy2(ROOT/'CROSS-PLATFORM.md',out/'README-BUILDS.md')
 print('LOCAL DOWNLOAD INDEX READY; publication remains disabled',flush=True)
if __name__=='__main__':main()
