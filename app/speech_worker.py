"""Private CPU speech worker. JSON in/out; no agent or network connections."""
import contextlib,json,os,pathlib,sys,time,wave,subprocess,shutil,importlib.util

ROOT=pathlib.Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('freedom_speech_numbers',ROOT/'speech_numbers.py')
_numbers=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_numbers)
FOLDER=ROOT/'runtime/personal-speech'
MODELS=FOLDER/'models'
CACHE=ROOT/'.cache/speech'
CACHE.mkdir(parents=True,exist_ok=True)
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['OMP_NUM_THREADS']='4'
os.environ['MKL_NUM_THREADS']='4'
loaded={}

def synthesize(request):
    text=request['text'];voice=request['voice'];output=pathlib.Path(request['output']).resolve()
    if not output.is_relative_to(CACHE.resolve()) or output.suffix!='.wav':raise ValueError('Invalid audio path')
    if not isinstance(text,str) or not 1<=len(text)<=700:raise ValueError('Invalid text length')
    target=output;output=output.with_name(output.stem+'.partial.wav')
    started=time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        if voice.startswith('ru-'):
            text=_numbers.russian_numbers(text)
            import torch
            import soundfile
            torch.set_num_threads(4)
            torch.hub.set_dir(str(ROOT/'.cache/torch'))
            speaker=voice.removeprefix('ru-')
            if speaker=='tars':speaker='eugene'
            if speaker not in {'xenia','kseniya','eugene','aidar','baya'}:raise ValueError('Unknown voice')
            if 'ru' not in loaded:
                model=torch.package.PackageImporter(str(MODELS/'silero-v5_6_ru.pt')).load_pickle('tts_models','model')
                model.to(torch.device('cpu'));loaded['ru']=model
            audio=loaded['ru'].apply_tts(text=text,speaker=speaker,sample_rate=24000,put_accent=True,put_yo=True)
            soundfile.write(str(output),audio.detach().cpu().numpy(),24000,subtype='PCM_16')
        elif voice=='en-amy':
            from piper import PiperVoice
            if 'en' not in loaded:
                import onnxruntime
                from piper.config import PiperConfig
                options=onnxruntime.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
                config=json.loads((MODELS/'en_US-amy-medium.onnx.json').read_text(encoding='utf-8'))
                loaded['en']=PiperVoice(config=PiperConfig.from_dict(config),
                    session=onnxruntime.InferenceSession(str(MODELS/'en_US-amy-medium.onnx'),sess_options=options,providers=['CPUExecutionProvider']),
                    download_dir=ROOT/'.cache/piper')
            with wave.open(str(output),'wb') as wav:loaded['en'].synthesize_wav(text,wav)
        else:raise ValueError('Unknown voice')
        if voice=='ru-tars':
            config=json.loads((ROOT/'data/personal-voice.json').read_text(encoding='utf-8-sig'))
            ffmpeg=config.get('ffmpeg') or shutil.which('ffmpeg')
            if not ffmpeg or not pathlib.Path(ffmpeg).is_file():raise ValueError('Обработчик голоса ТАРС не найден.')
            processed=output.with_name(output.stem+'.tars.wav')
            try:
                subprocess.run([str(ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-y','-i',str(output),
                    '-af','asetrate=22080,aresample=24000,atempo=1.04,highpass=f=65,lowpass=f=7800,equalizer=f=180:t=q:w=0.8:g=2,acompressor=threshold=0.16:ratio=2:attack=8:release=80,alimiter=limit=0.95',
                    '-ac','1','-c:a','pcm_s16le',str(processed)],check=True,capture_output=True,timeout=30,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                processed.replace(output)
            finally:processed.unlink(missing_ok=True)
    with wave.open(str(output),'rb') as wav:
        seconds=wav.getnframes()/wav.getframerate()
        if seconds<=0 or wav.getnchannels()!=1:raise ValueError('Invalid generated audio')
    output.replace(target)
    return {'ok':True,'seconds':seconds,'generation_seconds':round(time.monotonic()-started,3),'bytes':target.stat().st_size,'device':'cpu'}

for line in sys.stdin:
    try:
        request=json.loads(line)
        result=synthesize(request)
    except Exception as exc:
        result={'ok':False,'error':str(exc)[:350],'type':type(exc).__name__}
    print(json.dumps(result,ensure_ascii=True),flush=True)
