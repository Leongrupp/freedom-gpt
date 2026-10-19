"""Read Mach-O architecture, minimum OS and library names without execution."""
import pathlib,struct
def inspect(path):
 path=pathlib.Path(path)
 with path.open('rb') as source:
  def at(offset):
   source.seek(offset);head=source.read(32)
   if head[:4] in {b'\xca\xfe\xba\xbe',b'\xca\xfe\xba\xbf'}:
    count=struct.unpack_from('>I',head,4)[0];wide=head[:4]==b'\xca\xfe\xba\xbf';source.seek(offset+8);entries=[]
    for _ in range(count):entries.append(source.read(32 if wide else 20))
    result=[]
    for entry in entries:
     child=struct.unpack_from('>Q' if wide else '>I',entry,8)[0];result.extend(at(offset+child))
    return result
   if head[:4]!=b'\xcf\xfa\xed\xfe':return []
   cpu=struct.unpack_from('<I',head,4)[0];count=struct.unpack_from('<I',head,16)[0];cursor=offset+32;minimum=[];dylibs=[];rpaths=[]
   for _ in range(count):
    source.seek(cursor);command,size=struct.unpack('<II',source.read(8));source.seek(cursor);data=source.read(size)
    if command in {0x32,0x24}:
     value=struct.unpack_from('<I',data,12 if command==0x32 else 8)[0];minimum.append([value>>16,(value>>8)&255,value&255])
    if command in {0xc,0x18,0x80000018,0x8000001f,0x80000023,0x8000001c}:
     start=struct.unpack_from('<I',data,8)[0];name=data[start:].split(b'\0',1)[0].decode('utf-8','replace');(rpaths if command==0x8000001c else dylibs).append(name)
    cursor+=size
   return [{'cpu':cpu,'minimum_macos':max(minimum) if minimum else None,'dylibs':dylibs,'rpaths':rpaths}]
  return at(0)
