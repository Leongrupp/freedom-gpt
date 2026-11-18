"""Prevent truncated runtimes and accidental filtering of library packages."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from build_current_release import ROOT,clone_native


class NativeClone(unittest.TestCase):
    def test_resumes_existing_directory_and_preserves_nested_resources(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='native-copy-check-') as temp:
            base=pathlib.Path(temp);source=base/'source';dest=base/'dest'
            files={'runtime/python/lib/types.py':'stdlib',
                   'runtime/python/lib/site-packages/prompt_toolkit/output/base.py':'required output package',
                   'runtime/python/lib/site-packages/vendor/data/resource.json':'required data',
                   'data/auth.json':'private','logs/owner.log':'private'}
            for name,text in files.items():
                p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            dest.mkdir()  # An interrupted copy is not a completed runtime.
            clone_native(source,dest)
            clone_native(source,dest)  # Safe to resume a second time.
            for name in files:
                if name.startswith('runtime/'):
                    self.assertEqual((dest/name).read_text(),files[name])
                else:self.assertFalse((dest/name).exists())


if __name__=='__main__':unittest.main()
