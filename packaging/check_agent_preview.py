"""Offline/local checks for the agent preview. Does not publish or contact providers."""
import ast,importlib.util,json,pathlib,sys,time,unittest,urllib.request,uuid,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1];APP=ROOT/'app';sys.path.insert(0,str(ROOT/'packaging'))
from feature_payload import apply,MODULES
spec=importlib.util.spec_from_file_location('preview_update_protocol',APP/'update_protocol.py');protocol=importlib.util.module_from_spec(spec);spec.loader.exec_module(protocol)
from html.parser import HTMLParser
class Doc(HTMLParser):
 def __init__(self):super().__init__();self.tags=[];self.script=False;self.jsonld=[];self.text=''
 def handle_starttag(self,tag,attrs):
  a=dict(attrs);self.tags.append((tag,a))
  if tag=='script' and a.get('type')=='application/ld+json':self.script=True;self.text=''
 def handle_data(self,text):
  if self.script:self.text+=text
 def handle_endtag(self,tag):
  if tag=='script' and self.script:self.jsonld.append(json.loads(self.text));self.script=False
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:17900'+path,timeout=8) as response:return response.status,response.read()
class Checks(unittest.TestCase):
 def test_bilingual_agent_home_and_metadata(self):
  for prefix,keyword in [('', 'ИИ-агент'),('/en','AI agent')]:
   status,raw=get(prefix+'/');text=raw.decode();doc=Doc();doc.feed(text)
   self.assertEqual(status,200);self.assertEqual(sum(t=='h1' for t,a in doc.tags),1);self.assertIn(keyword,text)
   self.assertEqual(text.count('class="agent-index"'),6);self.assertIn('1.5.0',text);self.assertTrue(doc.jsonld)
   self.assertTrue(any(t=='link' and a.get('rel')=='canonical' and a['href']=='https://aionpc.ru'+prefix+'/' for t,a in doc.tags))
   self.assertTrue(any(t=='link' and a.get('href','').startswith('/agent.css') for t,a in doc.tags))
  self.assertEqual(get('/agent.css')[0],200)
 def test_new_agent_guides_and_sitemap(self):
  for prefix,keyword in [('', 'Blender'),('/en','Blender')]:
   status,raw=get(prefix+'/guides/ai-agent/');self.assertEqual(status,200);self.assertIn(keyword,raw.decode());self.assertIn('1.5.0',raw.decode())
  text=get('/sitemap.xml')[1].decode();ET.fromstring(text);self.assertIn('/en/guides/ai-agent/',text);self.assertIn('/guides/ai-agent/',get('/llms.txt')[1].decode())
 def test_source_and_publication_phase(self):
  for name in ('README.md','README.ru.md'):
   text=(ROOT/name).read_text(encoding='utf-8');self.assertIn('assets/agent-cover.svg',text);self.assertIn('1.5.0',text);self.assertIn('/v1.5.0/',text)
  ET.parse(ROOT/'assets/agent-cover.svg');self.assertEqual(json.loads((APP/'version.json').read_text())['channel'],'stable')
  self.assertEqual(json.loads((ROOT/'site/project.json').read_text())['version'],'1.5.0');self.assertTrue((ROOT/'.private/publication-hold.json').is_file())
 def test_python_sources_parse(self):
  paths=list(APP.glob('*.py'))+list((APP/'native_overrides').rglob('*.py'))+list((ROOT/'site').glob('*.py'))+list((ROOT/'packaging').glob('*.py'))
  for path in paths:ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
 def test_platform_feature_payloads_exclude_personal_data(self):
  parent=ROOT/'build'/('qa-agent-'+uuid.uuid4().hex[:8]);parent.mkdir(parents=True)
  forbidden={'auth.json','.env','state.db','interface.sqlite','config.yaml','runtime.json','accounts-control.json','github-connection.json'}
  for target in ('windows-x64','ubuntu-x64','macos-arm64'):
   folder=parent/target;report=apply(folder);self.assertEqual(report['modules'],16);self.assertEqual(report['native_overrides'],7)
   for name in MODULES:self.assertTrue((folder/'runtime/freedom'/name).is_file())
   self.assertTrue((folder/'runtime/freedom/agent_plugins/freedom-preview/plugin.yaml').is_file())
   self.assertTrue((folder/'runtime/freedom/node_modules/playwright/package.json').is_file())
   for file in folder.rglob('*'):
    if file.is_file():
     self.assertTrue(protocol.managed(file.relative_to(folder).as_posix()));self.assertNotIn(file.name,forbidden);self.assertNotIn(file.suffix,{'.gguf','.safetensors','.dpapi'})
 def test_playwright_dependency_and_portable_browser_fallback(self):
  package=json.loads((APP/'package.json').read_text());lock=json.loads((APP/'package-lock.json').read_text())
  self.assertEqual(package['dependencies']['playwright'],'1.64.1');self.assertEqual(lock['packages']['node_modules/playwright']['version'],'1.64.1')
  self.assertIn("process.platform==='win32'",(APP/'scripts/preview-browser.mjs').read_text());self.assertNotIn('Path("A:/CodexProjects")',(APP/'native_overrides/tools/browser_use_cli.py').read_text())
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks));out=ROOT/'output/agent-preview-20261021';out.mkdir(parents=True,exist_ok=True)
 report={'tests':result.testsRun,'passed':result.wasSuccessful(),'failures':[n.id() for n,_ in result.failures],'errors':[n.id() for n,_ in result.errors],'external_network_used':False,'clean_full_installers_built':False,'mac_native_tested':False,'public_upload_started':False}
 (out/'candidate-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');sys.exit(not result.wasSuccessful())
