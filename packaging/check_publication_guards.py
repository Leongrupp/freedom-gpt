"""Publication freshness regressions; local fixtures only, no uploads."""
import json,os,pathlib,tempfile,unittest
from publish_platforms import ROOT,verify_package_reports

class PublicationGuards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='publication-guards-',dir=ROOT/'build');self.root=pathlib.Path(self.tmp.name);self.version='1.5.0'
  self.artifacts=['release/FreedomGPT-Setup-1.5.0.exe','release/FreedomGPT-1.5.0-Windows-x64.zip','release/update.json']
  self.artifacts+=['release/platforms/1.5.0/'+name for name in ['FreedomGPT-1.5.0-Ubuntu-x64.tar.gz','FreedomGPT-Setup-1.5.0-Ubuntu-x64.run','FreedomGPT-1.5.0-Ubuntu-amd64.deb','FreedomGPT-1.5.0-macOS-AppleSilicon.zip','update-ubuntu-x64.json','update-macos-arm64.json']]
  for name in self.artifacts:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture');os.utime(p,(1000,1000))
  self.reports=[]
  for name in ['windows-clean-pc-verification','ubuntu-clean-pc-verification','ubuntu-installers-verification','platform-artifacts-verification']:
   p=self.root/'logs'/(name+'-1.5.0.json');p.parent.mkdir(exist_ok=True);p.write_text('{"passed": true}');os.utime(p,(2000,2000));self.reports.append(p)
 def tearDown(self):self.tmp.cleanup()
 def test_fresh_reports_pass(self):verify_package_reports(self.root,self.version)
 def test_each_stale_report_rejected(self):
  for report in self.reports:
   with self.subTest(report=report.name):
    os.utime(report,(500,500))
    with self.assertRaisesRegex(ValueError,'Fresh package verification required'):verify_package_reports(self.root,self.version)
    os.utime(report,(2000,2000))
 def test_failed_report_rejected(self):
  self.reports[0].write_text('{"passed": false}')
  with self.assertRaisesRegex(ValueError,'Passed verification required'):verify_package_reports(self.root,self.version)
 def test_missing_package_rejected(self):
  (self.root/self.artifacts[0]).unlink()
  with self.assertRaisesRegex(ValueError,'Fresh package verification required'):verify_package_reports(self.root,self.version)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicationGuards))
 (ROOT/'logs/publication-guard-regressions-1.5.0.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun},indent=2))
 raise SystemExit(not result.wasSuccessful())
