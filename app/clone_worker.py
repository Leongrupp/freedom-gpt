"""Offline Qwen3-TTS voice cloning. Runs only in its isolated CPU environment."""
import contextlib,json,os,pathlib,sys,time,wave,faulthandler
faulthandler.enable()
ROOT=pathlib.Path(__file__).resolve().parent
MODEL=ROOT/'runtime/personal-speech/models/Qwen3-TTS-12Hz-0.6B-Base'
loaded=None;prompts={}

def progress(text):print(json.dumps({'progress':text}),flush=True)

def synthesize(request):
    global loaded
    output=pathlib.Path(request['output']).resolve();profile=request['profile'];pid=profile['id']
    import re
    if not re.fullmatch('[a-f0-9]{32}',pid):raise ValueError('Invalid profile')
    if not output.is_relative_to((ROOT/'.cache/speech').resolve()) or output.suffix!='.wav':raise ValueError('Invalid output')
    text=request['text']
    if not isinstance(text,str) or not 1<=len(text)<=700:raise ValueError('Invalid text')
    reference=ROOT/'data/speech-profiles'/pid/'reference.wav'
    started=time.monotonic()
    if loaded is None:
        progress('Загружаю Qwen3-TTS на процессор')
        with contextlib.redirect_stdout(sys.stderr):
            import torch
            from qwen_tts import Qwen3TTSModel
            torch.set_num_threads(6);torch.set_num_interop_threads(1)
            # Avoid large Windows mmap storage copies under commit pressure.
            from functools import partial
            from unittest.mock import patch
            from transformers import modeling_utils
            import safetensors
            with patch.object(modeling_utils,'safe_open',partial(safetensors.safe_open,backend='pread')):
                loaded=Qwen3TTSModel.from_pretrained(str(MODEL),device_map='cpu',dtype=torch.bfloat16,attn_implementation='sdpa')
            # Bound decoder workspace while keeping its original overlap.
            decoder=loaded.model.speech_tokenizer.model.decoder
            decoder.chunked_decode=partial(decoder.chunked_decode,chunk_size=24,left_context_size=25)
    import torch,soundfile
    prompt_key=(pid,profile.get('updated'),profile['text'])
    if prompt_key not in prompts:
        progress('Анализирую тембр и манеру речи из вашей записи')
        with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
            prompts.clear()
            prompts[prompt_key]=loaded.create_voice_clone_prompt(ref_audio=str(reference),ref_text=profile['text'],x_vector_only_mode=bool(profile.get('x_vector_only',False)))
    progress('Создаю речь вашим голосом на процессоре')
    with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
        torch.manual_seed(42)
        wavs,sr=loaded.generate_voice_clone(text=text,language=request['language'],voice_clone_prompt=prompts[prompt_key],
            non_streaming_mode=True,max_new_tokens=min(1800,max(240,len(text)*4)),do_sample=True,temperature=.9)
        partial=output.with_name(output.stem+'.partial.wav')
        soundfile.write(str(partial),wavs[0],sr,subtype='PCM_16')
    with wave.open(str(partial),'rb') as wav:seconds=wav.getnframes()/wav.getframerate()
    if seconds<=.15:raise ValueError('Получился пустой звук. Проверьте запись и текст.')
    partial.replace(output)
    return {'ok':True,'seconds':seconds,'generation_seconds':round(time.monotonic()-started,3),'device':'cpu','engine':'Qwen3-TTS','bytes':output.stat().st_size}

for line in sys.stdin:
    try:result=synthesize(json.loads(line))
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        result={'ok':False,'error':('Недостаточно памяти для синтеза голоса. Закройте тяжёлые приложения или уменьшите контекст модели.' if isinstance(exc,MemoryError) else str(exc)[:350]),'type':type(exc).__name__}
    print(json.dumps(result,ensure_ascii=True),flush=True)
