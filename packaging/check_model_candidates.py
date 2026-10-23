"""Offline checks that auxiliary GGUF calibration files cannot masquerade as a model."""
import json,os,pathlib,sys,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(os.environ['FREEDOM_QA_ROOT']).resolve();sys.path[:0]=[str(ROOT/'runtime/freedom'),str(ROOT)]
import bootstrap,discovery
class Candidates(unittest.TestCase):
 def test_calibration_names(self):
  for name in ['imatrix.gguf','coder390-imatrix.gguf','folder/coder.imatrix.gguf','imatrix_coder.gguf']:
   with self.subTest(name=name):self.assertTrue(discovery.auxiliary_gguf(name))
 def test_quantized_weight_names(self):
  for name in ['Coder-IQ3_S3.gguf','Coder-imatrix-Q4_K_M.gguf','Coder-Q4_K_M-imatrix.gguf','Coder-Q8_0-MTP.gguf']:
   with self.subTest(name=name):self.assertFalse(discovery.auxiliary_gguf(name))
 def test_huggingface_candidates_exclude_matrix(self):
  meta={'sha':'revision','gguf':{'architecture':'qwen35','context_length':65536},'siblings':[{'rfilename':name,'size':size,'lfs':{'sha256':'a'*64}} for name,size in [('coder390-imatrix.gguf',30*1024**2),('Coder-IQ3_S3.gguf',11*1024**3)]]}
  with patch.object(discovery,'remote',return_value=meta):rows=discovery.hf_candidates('example/coder',{'ram_gb':32,'vram_gb':16,'free_disk_gb':60,'cuda':True})
  self.assertEqual([r['filename'] for r in rows],['Coder-IQ3_S3.gguf'])
 def test_cached_auxiliary_cannot_be_offered_or_added(self):
  lib=types.SimpleNamespace(device={'ram_gb':32,'vram_gb':16,'free_disk_gb':60,'cuda':True})
  search=discovery.Discovery(lib);search.state['results']=[{'key':'matrix','filename':'coder390-imatrix.gguf','bytes':30*1024**2,'can_add':True}]
  self.assertEqual(search.snapshot()['results'],[])
  with self.assertRaises(ValueError):search.add('matrix')
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Candidates));sys.exit(not result.wasSuccessful())
