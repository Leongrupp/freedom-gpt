"""Pin publisher metadata; never download model weights while building the installer."""
import concurrent.futures,json,pathlib,urllib.request,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent.parent
SPECS=[
 ('huihui-qwen38-coder','huihui-ai/Huihui-Qwen3.8-27B-Coder390-EfficientThink-abliterated-GGUF','IQ3_S3.gguf','Qwen 3.8 Coder · Huihui','27B · IQ3_S3',65536,16,32),
 ('qwen35-4b','unsloth/Qwen3.5-4B-GGUF','Q4_K_M.gguf','Qwen 3.5 · 4B','4B · Q4_K_M',65536,6,12),
 ('qwen35-08b','unsloth/Qwen3.5-0.8B-GGUF','Q4_K_M.gguf','Qwen 3.5 · 0.8B','0.8B · Q4_K_M',65536,2,8),
]
def metadata(repo):
 url='https://huggingface.co/api/models/'+repo+'?blobs=true'
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FreedomGPT/1.1 catalog builder'}),timeout=45) as response:return json.load(response)
def file_record(repo,meta,item,target=None):
 lfs=item.get('lfs') or {};sha=lfs.get('sha256');size=item.get('size') or lfs.get('size')
 if not sha or not size:raise ValueError('Missing publisher SHA256 '+item['rfilename'])
 return {'name':target or pathlib.PurePosixPath(item['rfilename']).name,'bytes':size,'sha256':sha,
         'url':'https://huggingface.co/'+repo+'/resolve/'+meta['sha']+'/'+urllib.parse.quote(item['rfilename']),
         'publisher_file':item['rfilename']}
def chat(spec):
 ident,repo,suffix,name,quant,context,vram,ram=spec;meta=metadata(repo)
 selected=next(i for i in meta['siblings'] if i['rfilename'].lower().endswith(suffix.lower()) and 'mmproj' not in i['rfilename'].lower())
 files=[file_record(repo,meta,selected,'model.gguf')]
 projector=next((i for i in meta['siblings'] if 'mmproj' in i['rfilename'].lower() and i['rfilename'].endswith('.gguf')),None)
 if ident.startswith('huihui') and projector:files.append(file_record(repo,meta,projector,'mmproj.gguf'))
 return dict(id=ident,name=name,kind='chat',quantization=quant,context=context,recommended_vram_gb=vram,recommended_ram_gb=ram,
             default=ident.startswith('huihui'),source='https://huggingface.co/'+repo,revision=meta['sha'],license=meta.get('cardData',{}).get('license','see model card'),files=files,mtp=ident.startswith('huihui'))
def image():
 parts=[('unsloth/Qwen-Image-2.1-Turbo-GGUF','qwen-image-2.1-turbo-Q5_K_M.gguf'),
        ('unsloth/Qwen3-VL-8B-Instruct-GGUF','Qwen3-VL-8B-Instruct-UD-Q4_K_XL.gguf'),
        ('unsloth/Qwen-Image-2.1-FP8','vae/qwen_image_2.1_vae_bf16.safetensors')]
 files=[];revisions={}
 for repo,name in parts:
  meta=metadata(repo);item=next(i for i in meta['siblings'] if i['rfilename']==name)
  files.append(file_record(repo,meta,item));revisions[repo]=meta['sha']
 return dict(id='qwen-image21',name='Qwen Image 2.1 Turbo',kind='image',quantization='Q5_K_M · 8 шагов',default=True,
             recommended_vram_gb=12,recommended_ram_gb=32,source='https://huggingface.co/unsloth/Qwen-Image-2.1-Turbo-GGUF',license='see component model cards',revisions=revisions,files=files)

def video():
 parts=[('Comfy-Org/Wan_2.1_ComfyUI_repackaged','split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors'),
        ('city96/umt5-xxl-encoder-gguf','umt5-xxl-encoder-Q4_K_M.gguf'),
        ('Comfy-Org/Wan_2.1_ComfyUI_repackaged','split_files/vae/wan_2.1_vae.safetensors')]
 files=[]
 for repo,name in parts:
  meta=metadata(repo);item=next(i for i in meta['siblings'] if i['rfilename']==name)
  files.append(file_record(repo,meta,item))
 return dict(id='wan21-t2v-13b',name='Wan 2.1 · Text to Video 1.3B',kind='video',quantization='FP16 · T5 Q4_K_M',default=False,
             recommended_vram_gb=8,recommended_ram_gb=24,source='https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B',
             license='apache-2.0; see component model cards',files=files,adapter='wan21-t2v',free=True,resolution='480p',supports_image_input=False)
if __name__=='__main__':
 items=[];failures=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  work=[pool.submit(chat,s) for s in SPECS]+[pool.submit(image),pool.submit(video)]
  for future in work:
   try:items.append(future.result())
   except Exception as exc:failures.append(str(exc))
 (ROOT/'logs/catalog-fetch.json').write_text(json.dumps({'items':items,'errors':failures},ensure_ascii=False,indent=2),encoding='utf8')
 if failures:raise SystemExit('; '.join(failures))
 (ROOT/'app/catalog.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps([{'id':m['id'],'bytes':sum(f['bytes'] for f in m['files']),'files':len(m['files'])} for m in items]))
