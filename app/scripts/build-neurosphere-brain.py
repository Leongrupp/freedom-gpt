"""Convert the attributed FreeSurfer fsaverage5 cortical surfaces to a small local GLB."""
import array,base64,gzip,hashlib,json,pathlib,struct,sys,urllib.request,xml.etree.ElementTree as ET,zlib
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import bootstrap
SOURCE=ROOT/'.cache/neurosphere-source';OUT=ROOT/'public/neurosphere';OUT.mkdir(parents=True,exist_ok=True)
op=urllib.request.build_opener(urllib.request.ProxyHandler({}));meshes=[];sources=[]
for side in ['left','right']:
 file=SOURCE/('pial_'+side+'.gii.gz');doc=ET.fromstring(gzip.decompress(file.read_bytes()));data=[]
 for element in doc.findall('DataArray'):
  raw=zlib.decompress(base64.b64decode(element.findtext('Data')));values=array.array('f' if element.attrib['Intent']=='NIFTI_INTENT_POINTSET' else 'i');values.frombytes(raw)
  if sys.byteorder!='little':values.byteswap()
  data.append(values)
 meshes.append(data);sources.append({'name':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'source':'https://github.com/nilearn/nilearn/tree/0.10.4/nilearn/datasets/data/fsaverage5'})
coords=[m[0] for m in meshes];center=[(min(min(v[i::3]) for v in coords)+max(max(v[i::3]) for v in coords))/2 for i in range(3)]
binary=bytearray();views=[];accessors=[];gltfmesh=[]
def attribute(raw,component,count,kind,minimum=None,maximum=None,target=34962):
 while len(binary)%4:binary.append(0)
 index=len(views);views.append({'buffer':0,'byteOffset':len(binary),'byteLength':len(raw),'target':target});binary.extend(raw)
 acc={'bufferView':index,'componentType':component,'count':count,'type':kind}
 if minimum is not None:acc.update(min=minimum,max=maximum)
 accessors.append(acc);return len(accessors)-1
for number,(vertices,faces) in enumerate(meshes):
 positions=array.array('f')
 for i in range(0,len(vertices),3):positions.extend(((vertices[i]-center[0])/50,(vertices[i+2]-center[2])/50,-(vertices[i+1]-center[1])/50))
 indices=array.array('H',faces)
 # Real cortical folds remain in the geometry; smooth normals are calculated by the viewer.
 p=attribute(positions.tobytes(),5126,len(positions)//3,'VEC3',[min(positions[i::3]) for i in range(3)],[max(positions[i::3]) for i in range(3)])
 f=attribute(indices.tobytes(),5123,len(indices),'SCALAR',target=34963)
 gltfmesh.append({'name':['left-cortex','right-cortex'][number],'primitives':[{'attributes':{'POSITION':p},'indices':f,'material':0}]})
document={'asset':{'version':'2.0','generator':'Freedom Neurosphere · modified fsaverage5 display mesh','copyright':'FreeSurfer / The General Hospital Corporation; fsaverage5 distributed by Nilearn; see LICENSE.txt'},'scene':0,'scenes':[{'nodes':[0,1]}],'nodes':[{'mesh':0},{'mesh':1}],'meshes':gltfmesh,'materials':[{'name':'cortex','pbrMetallicRoughness':{'baseColorFactor':[.42,.29,.17,1],'metallicFactor':.28,'roughnessFactor':.5}}],'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors}
js=json.dumps(document,separators=(',',':')).encode();js+=b' '*((-len(js))%4);binary.extend(b'\0'*((-len(binary))%4));glb=struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary
(OUT/'cortex.glb').write_bytes(glb)
with op.open('https://raw.githubusercontent.com/freesurfer/freesurfer/dev/LICENSE.txt',timeout=20) as response:text=response.read().decode()
start=0;end=len(text)
notice='All or portions of this licensed product (such portions are the "Software") have been obtained under license from The General Hospital Corporation and are subject to the following terms and conditions:\n\n'
(OUT/'LICENSE.txt').write_text(notice+text[start:end],encoding='utf-8')
(OUT/'SOURCE.txt').write_text('Cortical surface: FreeSurfer fsaverage5 via Nilearn 0.10.4.\nModified for display: coordinate centering, RAS-to-Y-up transform, scale, GLB serialization and display material. Not a medical tool or a representation of model activations.\nFischl, Sereno, Tootell, Dale (1999), Human Brain Mapping 8(4):272–284.\nhttps://nilearn.github.io/dev/modules/description/fsaverage5.html\nhttps://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSoftwareLicense\n'+json.dumps(sources,indent=2),encoding='utf-8')
print(json.dumps({'file':str(OUT/'cortex.glb'),'bytes':len(glb),'vertices':sum(len(v)//3 for v,f in meshes),'triangles':sum(len(f)//3 for v,f in meshes)}))
