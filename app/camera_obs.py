"""Reuse installed OBS resources with an isolated portable profile on A:."""
import os,pathlib,shutil,subprocess,threading
import psutil
from bootstrap import ROOT,read,write

BASE=ROOT/'camera-studio';PORTABLE=BASE/'obs';LOCK=threading.Lock()
NAME='Freedom Avatar';SCENE='FreedomAvatar'

def installed():
    candidate=pathlib.Path(os.environ.get('ProgramFiles','C:/Program Files'))/'obs-studio'
    return candidate if (candidate/'bin/64bit/obs64.exe').is_file() else None

def prepare(scene):
    with LOCK:
        source=installed()
        if not source:raise ValueError('OBS не найден. Установите OBS Studio, либо импортируйте сцену в свою версию OBS.')
        executable=PORTABLE/'bin/64bit/obs64.exe'
        # Windows portable mode derives its config directory from the executable.
        # Only the small binary folder is copied; existing bundled resources are
        # read through junctions, without modifying the installed OBS profile.
        marker=PORTABLE/'source-version.json'
        identity={'path':str(source),'size':(source/'bin/64bit/obs64.exe').stat().st_size,'mtime':(source/'bin/64bit/obs64.exe').stat().st_mtime}
        if read(marker,{})!=identity or not executable.is_file():
            if any(p.info['exe'] and pathlib.Path(p.info['exe'])==executable for p in psutil.process_iter(['exe'])):
                raise ValueError('Закройте отдельное окно Freedom OBS перед обновлением его компонентов.')
            shutil.copytree(source/'bin/64bit',PORTABLE/'bin/64bit',dirs_exist_ok=True)
            write(marker,identity)
        for name in ['data','obs-plugins']:
            destination=PORTABLE/name
            if not destination.exists():
                script=ROOT/'.tmp/camera-obs-junction.ps1'
                script.write_text('param([string]$Link,[string]$Target)\n$ErrorActionPreference="Stop"\nNew-Item -ItemType Junction -Path $Link -Target $Target | Out-Null\n',encoding='ascii')
                command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-Link',str(destination),'-Target',str(source/name)]
                result=subprocess.run(command,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode or not destination.exists():
                    raise ValueError('Не удалось подключить установленные ресурсы OBS.')
        config=PORTABLE/'config/obs-studio'
        profiles=config/'basic/profiles'/SCENE;scenes=config/'basic/scenes'
        profiles.mkdir(parents=True,exist_ok=True);scenes.mkdir(parents=True,exist_ok=True)
        if not (config/'global.ini').exists():
            (config/'global.ini').write_text('[General]\nLastVersion=537001986\n\n[Video]\nRenderer=Direct3D 11\n',encoding='utf8')
        if not (config/'user.ini').exists():
            (config/'user.ini').write_text('[General]\nFirstRun=true\n\n[Basic]\nProfile=Freedom Avatar\nProfileDir=FreedomAvatar\nSceneCollection=Freedom Avatar\nSceneCollectionFile=FreedomAvatar.json\n\n[BasicWindow]\nPreviewEnabled=true\nStudioMode=false\n',encoding='utf8')
        if not (profiles/'basic.ini').exists():
            (profiles/'basic.ini').write_text('[General]\nName=Freedom Avatar\n\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSType=0\nFPSCommon=30\n\n[SimpleOutput]\nFilePath='+str(BASE/'exports')+'\n\n[Output]\nMode=Simple\n\n[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n',encoding='utf8')
        # Never replace a running OBS collection. The browser source URL is stable.
        if not (scenes/(SCENE+'.json')).exists():shutil.copy2(scene,scenes/(SCENE+'.json'))
        return executable

def launch(scene):
    executable=prepare(scene)
    for process in psutil.process_iter(['exe']):
        if process.info['exe'] and pathlib.Path(process.info['exe'])==executable:
            return {'ok':True,'running':True,'pid':process.pid,'profile':NAME}
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    env={**os.environ,'TEMP':str(ROOT/'.tmp'),'TMP':str(ROOT/'.tmp')}
    process=subprocess.Popen([str(executable),'--portable','--collection',NAME,'--profile',NAME,'--scene',NAME,'--multi','--disable-updater','--minimize-to-tray','--only-bundled-plugins'],cwd=executable.parent,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,startupinfo=startup)
    write(BASE/'data/obs-process.json',{'pid':process.pid,'created':psutil.Process(process.pid).create_time(),'path':str(executable)})
    return {'ok':True,'running':True,'pid':process.pid,'profile':NAME}
