"""Isolated regression tests for portable config and project recall, no model/API calls."""
import ast,importlib.util,json,os,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build/FreedomGPT-1.4.2/runtime/hermes'))
import hermes_yaml as yaml

class Features(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='feature-regression-');self.root=pathlib.Path(self.tmp.name);self.home=self.root/'home';self.home.mkdir()
  source=ast.parse((ROOT/'app/bootstrap.py').read_text(encoding='utf-8'))
  node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='write_hermes')
  self.scope={'PRIVATE':{},'ROOT':self.root,'HOME':self.home,'config':lambda:{},'model_url':lambda:'http://127.0.0.1:19135/v1','model_id':lambda:'test-model','context_size':lambda:65536}
  import uuid
  self.scope.update(uuid=uuid,os=os)
  exec(compile(ast.Module(body=[node],type_ignores=[]),'write_hermes','exec'),self.scope)
 def tearDown(self):self.tmp.cleanup()
 def write(self):self.scope['write_hermes']()
 def test_new_configuration(self):
  self.write();value=yaml.safe_load((self.home/'config.yaml').read_text());self.assertEqual(value['model']['default'],'test-model');self.assertIn('freedom-preview',value['plugins']['enabled']);self.assertTrue(value['tool_loop_guardrails']['hard_stop_enabled'])
 def test_existing_settings_and_backup(self):
  path=self.home/'config.yaml';path.write_text(yaml.safe_dump({'custom_setting':42,'terminal':{'cwd':'myproject'},'plugins':{'enabled':['my-plugin']},'model_aliases':{'personal':{'model':'other'}},'custom_providers':[{'name':'personal'}]}))
  old=path.read_bytes();self.write();value=yaml.safe_load(path.read_text())
  self.assertEqual(value['custom_setting'],42);self.assertEqual(value['terminal']['cwd'],'myproject');self.assertIn('my-plugin',value['plugins']['enabled']);self.assertIn('personal',value['model_aliases']);self.assertIn({'name':'personal'},value['custom_providers'])
  self.assertTrue(any(p.read_bytes()==old for p in (self.root/'archive/agent-config').glob('*.yaml')))
  stamp=path.stat().st_mtime_ns;self.write();self.assertEqual(path.stat().st_mtime_ns,stamp)
 def test_invalid_config_preserved(self):
  path=self.home/'config.yaml';path.write_text('model: [broken');old=path.read_bytes()
  with self.assertRaises(Exception):self.write()
  self.assertEqual(path.read_bytes(),old)
 def test_portable_project_recall(self):
  os.environ['FREEDOM_ROOT']=str(self.root)
  source=ROOT/'app/builtin_plugins/coding-continuity/project_store.py';spec=importlib.util.spec_from_file_location('qa_project_store',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  project=self.root/'workspaces/test-project';project.mkdir(parents=True)
  store=module.ProjectStore(project);store.remember('Remember the amber lighthouse architecture','decision','test','local regression')
  self.assertTrue(store.search('amber lighthouse',8))
  second=module.ProjectStore(project);self.assertTrue(second.search('amber lighthouse',8))
  with self.assertRaises(ValueError):module.ProjectStore(self.root.parent)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Features))
 (ROOT/'logs/release-feature-regressions-1.5.0.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun},indent=2))
 sys.exit(not result.wasSuccessful())
