"""One verified pure-Python QR dependency, shared by all platform packages."""
import hashlib,json,pathlib,shutil,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
NAME='qrcode-8.2-py3-none-any.whl'
SHA='16e64e0716c14960108e85d853062c9e8bba5ca8252c0b4d0231b9df4060ff4f'

def apply(bundle):
    bundle=pathlib.Path(bundle);wheel=ROOT/'.cache/phone-wheels'/NAME
    if not wheel.is_file() or hashlib.sha256(wheel.read_bytes()).hexdigest()!=SHA:
        raise ValueError('Download the pinned QR wheel first: python -m pip download --no-deps --dest .cache/phone-wheels qrcode==8.2')
    win=bundle/'runtime/python/Lib/site-packages'
    site=win if win.is_dir() else bundle/'runtime/python/lib/python3.14/site-packages'
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            path=pathlib.PurePosixPath(item.filename)
            if item.is_dir():continue
            if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe QR wheel member')
            target=site/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(item))
        license_name=next(n for n in archive.namelist() if n.endswith('/LICENSE'))
        target=bundle/'licenses/qrcode-MIT.txt';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(license_name))
    folder=bundle/'runtime/wheels';folder.mkdir(parents=True,exist_ok=True);shutil.copy2(wheel,folder/NAME)
    manifest=folder/'manifest.json'
    if manifest.is_file():
        items=[x for x in json.loads(manifest.read_text()) if x.get('file')!=NAME]
        items.append({'file':NAME,'bytes':wheel.stat().st_size,'sha256':SHA});manifest.write_text(json.dumps(items,indent=2),encoding='utf-8')
    for name in ['requirements.lock']:
        path=folder/name
        if path.exists():
            text=path.read_text(encoding='utf-8')
            if 'qrcode==' not in text:path.write_text(text.rstrip()+'\nqrcode==8.2\n',encoding='utf-8')
