"""Extract portable runtimes without creating host symlinks or unsafe paths."""
import hashlib,json,pathlib,posixpath,stat,tarfile,zipfile

def safe_name(name):
 value=pathlib.PurePosixPath(name)
 if value.is_absolute() or '..' in value.parts or '\\' in name or ':' in name:raise ValueError('Unsafe archive path: '+name)
 return value.as_posix().removeprefix('./')

def unpack(archive,folder):
 archive=pathlib.Path(archive);folder=pathlib.Path(folder);done=folder/'.extracted.json'
 if done.is_file():return json.loads(done.read_text())
 folder.mkdir(parents=True,exist_ok=True);modes={}
 if zipfile.is_zipfile(archive):
  with zipfile.ZipFile(archive) as source:
   members={safe_name(m.filename):m for m in source.infolist() if not m.is_dir()}
   def content(name,depth=0):
    if depth>12:raise ValueError('Archive link cycle')
    member=members[name]
    if stat.S_ISLNK(member.external_attr>>16):
     target=source.read(member).decode();return content(safe_name(posixpath.normpath(posixpath.join(posixpath.dirname(name),target))),depth+1)
    return source.read(member)
   for name,member in members.items():
    target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content(name));modes[name]=(member.external_attr>>16)&0o777 or 0o644
 else:
  with tarfile.open(archive,'r:*') as source:
   members={safe_name(m.name):m for m in source.getmembers() if not m.isdir()}
   def content(name,depth=0):
    if depth>12:raise ValueError('Archive link cycle')
    member=members[name]
    if member.issym() or member.islnk():
     target=posixpath.join(posixpath.dirname(name),member.linkname) if member.issym() else member.linkname
     return content(safe_name(posixpath.normpath(target)),depth+1)
    if not member.isfile():raise ValueError('Special file in runtime archive')
    return source.extractfile(member).read()
   for name,member in members.items():
    target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content(name));modes[name]=member.mode&0o777
 done.write_text(json.dumps(modes,indent=2),encoding='utf-8');return modes
