"""Short-lived offline ACE-Step REST adapter, launched inside its isolated Python."""
import json,os,pathlib,secrets,socket,subprocess,sys,time,urllib.parse,urllib.request

def run(root,job_path):
    root=pathlib.Path(root).resolve();job=json.loads(pathlib.Path(job_path).read_text(encoding='utf8'))
    folder=root/'runtime/music/ACE-Step-1.5'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    token=secrets.token_urlsafe(32);origin='http://127.0.0.1:'+str(port)
    env=os.environ.copy();env.update(ACESTEP_API_KEY=token,ACESTEP_CONFIG_PATH='acestep-v15-turbo',
        ACESTEP_CHECKPOINTS_DIR=str(folder/'checkpoints'),ACESTEP_LM_MODEL_PATH='acestep-5Hz-lm-1.7B',
        ACESTEP_LM_BACKEND='pt',ACESTEP_DEVICE='cuda',ACESTEP_INIT_LLM='true',
        ACESTEP_INIT_SERVICE='true',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    process=subprocess.Popen([sys.executable,'-m','acestep.api_server','--host','127.0.0.1','--port',str(port)],cwd=folder,env=env)
    def call(path,value=None):
        req=urllib.request.Request(origin+path,data=None if value is None else json.dumps(value).encode(),
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
    try:
        deadline=time.monotonic()+600
        while True:
            if process.poll() is not None:raise RuntimeError('Музыкальный движок завершился при загрузке.')
            try:
                call('/health');break
            except OSError:
                if time.monotonic()>deadline:raise TimeoutError('Музыкальный движок не загрузился за 10 минут.')
                time.sleep(2)
        payload={'prompt':job['prompt'],'lyrics':'[Instrumental]' if job['instrumental'] else job['lyrics'],
            'thinking':True,'vocal_language':job['language'],'audio_duration':job['duration'],
            'audio_format':'wav','batch_size':1,'inference_steps':8,'seed':job['seed']}
        if job.get('bpm'):payload['bpm']=job['bpm']
        task=call('/release_task',payload)
        ident=(task.get('data') or {}).get('task_id')
        if not ident:raise RuntimeError('Движок не подтвердил приём музыкального задания.')
        print('FREEDOM_MUSIC_GENERATING',flush=True);deadline=time.monotonic()+1800
        while time.monotonic()<deadline:
            rows=call('/query_result',{'task_id_list':[ident]}).get('data') or []
            if rows and rows[0].get('status')==2:raise RuntimeError('ACE-Step не смог создать трек. Журнал сохранён.')
            if rows and rows[0].get('status')==1:
                result=rows[0].get('result');result=json.loads(result) if isinstance(result,str) else result
                path=result[0]['file'];url=urllib.parse.urljoin(origin,path)
                if urllib.parse.urlsplit(url).netloc!=urllib.parse.urlsplit(origin).netloc:raise RuntimeError('Неожиданный адрес аудиофайла.')
                request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(request,timeout=45) as response,open(job['output'],'wb') as output:
                    while chunk:=response.read(1024*1024):output.write(chunk)
                return
            time.sleep(2)
        raise TimeoutError('Генерация музыки превысила 30 минут.')
    finally:
        process.terminate()
        try:process.wait(timeout=12)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=8)

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
