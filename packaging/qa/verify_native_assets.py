"""Bind native CI execution to the exact locally verified release archives."""
import hashlib
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=json.loads((ROOT/'packaging/native-validation.json').read_text())
target=sys.argv[1]
for item in spec[target]:
    path=ROOT/'release/platforms'/spec['version']/item['file']
    assert path.stat().st_size==item['bytes'],path.name
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):digest.update(block)
    assert digest.hexdigest()==item['sha256'],path.name
print('NATIVE_ASSETS_VERIFIED='+json.dumps({'version':spec['version'],'platform':target,'assets':spec[target]}),flush=True)
