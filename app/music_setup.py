"""Explicit, deferred ACE-Step installation. Never runs when the studio is opened."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,time,urllib.request

COMMIT='ca1e85fe9430179831e6bc6be790c332190a3866'
REPO='ACE-Step/Ace-Step1.5'

def environment(root,online=False):
    env=os.environ.copy()
    for name in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','UV_PROJECT_ENVIRONMENT','UV_OFFLINE','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE'):
        env.pop(name,None)
    base=pathlib.Path(root)
    env.update(TEMP=str(base/'.tmp/music'),TMP=str(base/'.tmp/music'),TMPDIR=str(base/'.tmp/music'),
        UV_CACHE_DIR=str(base/'.cache/music/uv'),UV_PYTHON_INSTALL_DIR=str(base/'runtime/music/python'),
        HF_HOME=str(base/'.cache/music/huggingface'),XDG_CACHE_HOME=str(base/'.cache/music'),
        TORCH_HOME=str(base/'.cache/music/torch'),PIP_CACHE_DIR=str(base/'.cache/music/pip'),
        CUDA_CACHE_PATH=str(base/'.cache/music/cuda'),TRITON_CACHE_DIR=str(base/'.cache/music/triton'),
        MPLCONFIGDIR=str(base/'.cache/music/matplotlib'),NUMBA_CACHE_DIR=str(base/'.cache/music/numba'),
        PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',TOKENIZERS_PARALLELISM='false',
        HF_HUB_ETAG_TIMEOUT='90',HF_HUB_DOWNLOAD_TIMEOUT='120')
    if not online:env.update(UV_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    for folder in (base/'.tmp/music',base/'.cache/music',base/'runtime/music'):folder.mkdir(parents=True,exist_ok=True)
    return env

def setup(root):
    root=pathlib.Path(root).resolve();folder=root/'runtime/music/ACE-Step-1.5';env=environment(root,True)
    uv=shutil.which('uv')
    if not uv:raise RuntimeError('Не найден uv. Установите официальный менеджер uv и повторите установку.')
    def run(args,cwd=root):
        subprocess.run([str(x) for x in args],cwd=cwd,env=env,check=True)
    if not (folder/'.git').is_dir():
        folder.mkdir(parents=True,exist_ok=True)
        run(['git','init',folder]);run(['git','remote','add','origin','https://github.com/ace-step/ACE-Step-1.5.git'],folder)
    run(['git','fetch','--depth','1','origin',COMMIT],folder)
    run(['git','checkout','--detach',COMMIT],folder)
    run([uv,'sync','--frozen','--python','3.11'],folder)
    # Download only after the explicit installation click. Pin and hash-check the Hub snapshot.
    worker=root/'music_setup.py'
    run([uv,'run','--no-sync','python',worker,'--weights',root],folder)

def weights(root):
    from huggingface_hub import HfApi,snapshot_download
    root=pathlib.Path(root).resolve();folder=root/'runtime/music/ACE-Step-1.5'
    info=HfApi().model_info(REPO,files_metadata=True)
    target=folder/'checkpoints'
    patterns=['vae/*','Qwen3-Embedding-0.6B/*','acestep-v15-turbo/*','acestep-5Hz-lm-1.7B/*','LICENSE*']
    snapshot_download(REPO,revision=info.sha,local_dir=str(target),allow_patterns=patterns,max_workers=2)
    checked=[]
    for item in info.siblings:
        path=target/item.rfilename
        if not path.is_file() or not item.lfs:continue
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=item.lfs.sha256:raise RuntimeError('Ошибка контрольной суммы: '+item.rfilename)
        checked.append({'name':item.rfilename,'bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns,'sha256':actual})
    for part in ('vae/','Qwen3-Embedding-0.6B/','acestep-v15-turbo/','acestep-5Hz-lm-1.7B/'):
        if not any(row['name'].startswith(part) for row in checked):raise RuntimeError('Неполный комплект модели: '+part)
    data={'commit':COMMIT,'model_revision':info.sha,'installed_at':time.time(),'files':checked}
    marker=root/'data/music-installed.json';temp=marker.with_suffix('.new');temp.write_text(json.dumps(data,indent=2),encoding='utf8');os.replace(temp,marker)
    print('FREEDOM_MUSIC_READY',flush=True)

if __name__=='__main__':
    if sys.argv[1]=='--weights':weights(sys.argv[2])
    else:setup(sys.argv[1])
