"""Exercise the actual artifact extractor without starting an app or changing a user's database."""
import ast,contextlib,json,os,pathlib,re,sys,unittest
ROOT=pathlib.Path(os.environ['FREEDOM_QA_ROOT']).resolve()
tree=ast.parse((ROOT/'server.py').read_text(encoding='utf-8'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='find_artifacts')
scope={'pathlib':pathlib,'contextlib':contextlib,'json':json,'re':re};collected=[]
def register(sid,path):collected.append(path);return {'id':path,'name':pathlib.Path(path).name}
scope['register_artifact']=register;exec(compile(ast.Module(body=[node],type_ignores=[]),'find_artifacts','exec'),scope)
class Extractor(unittest.TestCase):
 def setUp(self):collected.clear()
 def test_native_resolved_markdown_path(self):
  path=str(ROOT/'workspaces/Example/README.md');scope['find_artifacts']('qa',json.dumps({'resolved_path':path,'bytes_written':20}));self.assertIn(path,collected)
 def test_native_modified_file_list(self):
  paths=[str(ROOT/'workspaces/Example/app.tsx'),str(ROOT/'workspaces/Example/project.toml')];scope['find_artifacts']('qa',{'files_modified':paths});self.assertTrue(set(paths).issubset(collected))
 def test_relative_metadata_is_not_registered(self):
  scope['find_artifacts']('qa',{'resolved_path':'README.md','files_modified':['relative.tsx',None,1]});self.assertEqual(collected,[])
 def test_nested_created_file_metadata(self):
  path=str(ROOT/'workspaces/Example/settings.json');scope['find_artifacts']('qa',{'result':{'files_created':[path]}});self.assertIn(path,collected)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Extractor));sys.exit(not result.wasSuccessful())
