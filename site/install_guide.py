"""Beginner instructions and reproducible release commands, generated in RU and EN."""
import html,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
SYSTEMS=['windows-x64','macos-arm64','ubuntu-x64']
TITLES={'windows-x64':'Windows','macos-arm64':'macOS · Apple Silicon','ubuntu-x64':'Ubuntu Linux'}
def release_files(version):
    manifest=ROOT/'release/platforms'/version/'release.json'
    if manifest.is_file():files=json.loads(manifest.read_text(encoding='utf-8'))['files']
    else:
        snapshot=json.loads((ROOT/'site/platforms.json').read_text(encoding='utf-8'))
        if snapshot['version']!=version:raise ValueError('Published platform snapshot version mismatch')
        files=[dict(file,url=f'https://github.com/Leongrupp/freedom-gpt/releases/download/v{version}/'+file['name']) for platform in snapshot['platforms'] for file in platform['files']]
    return {f['name']:f for f in files}
def commands(target,version,repo):
    names={'windows-x64':f'FreedomGPT-Setup-{version}.exe','ubuntu-x64':f'FreedomGPT-Setup-{version}-Ubuntu-x64.run','macos-arm64':f'FreedomGPT-{version}-macOS-AppleSilicon.zip'}
    name=names[target];digest=release_files(version)[name]['sha256'];url=repo+'/releases/download/v'+version+'/'+name
    if target=='windows-x64':
        return f'''& {{
  $ErrorActionPreference = 'Stop'
  $freedomInstallPath = Read-Host 'New empty SSD folder (for example D:\\FreedomGPT)'
  if ([string]::IsNullOrWhiteSpace($freedomInstallPath)) {{ throw 'Choose an empty folder.' }}
  $freedomInstallPath = [IO.Path]::GetFullPath($freedomInstallPath)
  $freedomSetupPath = Join-Path (Get-Location) '{name}'
  $freedomHash = '{digest}'
  if (!(Test-Path -LiteralPath $freedomSetupPath) -or (Get-FileHash -LiteralPath $freedomSetupPath -Algorithm SHA256).Hash -ne $freedomHash) {{
    curl.exe -fL -C - --retry 4 -o $freedomSetupPath '{url}'
    if ($LASTEXITCODE -ne 0) {{ throw 'Download failed. Run again to resume.' }}
  }}
  if ((Get-FileHash -LiteralPath $freedomSetupPath -Algorithm SHA256).Hash -ne $freedomHash) {{ throw 'SHA256 mismatch. Installation stopped.' }}
  $freedomProcess = Start-Process -FilePath $freedomSetupPath -ArgumentList ('/extract="' + $freedomInstallPath + '"') -Wait -PassThru
  if ($freedomProcess.ExitCode -ne 0) {{ throw 'Installation failed. Choose a new empty folder outside your user profile.' }}
  Start-Process -FilePath (Join-Path $freedomInstallPath 'FreedomGPT.exe')
}}'''
    if target=='ubuntu-x64':
        return f'''(
  set -eu
  freedom_file='{name}'
  freedom_sha='{digest}'
  if ! printf '%s  %s\\n' "$freedom_sha" "$freedom_file" | sha256sum -c - >/dev/null 2>&1; then
    curl -fL -C - --retry 4 -o "$freedom_file" '{url}'
  fi
  printf '%s  %s\\n' "$freedom_sha" "$freedom_file" | sha256sum -c -
  sh "./$freedom_file"
)'''
    return f'''(
  set -eu
  [ "$(uname -m)" = arm64 ] || {{ echo 'Apple Silicon is required.'; exit 1; }}
  sw_vers -productVersion | awk -F. '{{ exit !($1 > 26 || ($1 == 26 && $2 >= 2)) }}' || {{ echo 'macOS26.2+ is required.'; exit 1; }}
  freedom_file='{name}'
  freedom_sha='{digest}'
  freedom_folder='./FreedomGPT-{version}-macOS'
  [ ! -e "$freedom_folder" ] || {{ echo 'The extraction folder already exists. Choose a new folder.'; exit 1; }}
  if ! printf '%s  %s\\n' "$freedom_sha" "$freedom_file" | shasum -a 256 -c - >/dev/null 2>&1; then
    curl -fL -C - --retry 4 -o "$freedom_file" '{url}'
  fi
  printf '%s  %s\\n' "$freedom_sha" "$freedom_file" | shasum -a 256 -c -
  ditto -x -k "$freedom_file" "$freedom_folder"
  open "$freedom_folder/Freedom GPT.app"
)'''
def steps(target,en):
    if target=='windows-x64':return [
      ('Download the app','Click “Download for Windows” above. Open the downloaded EXE file.') if en else ('Скачайте приложение','Нажмите «Скачать для Windows» выше. Откройте скачанный EXE-файл.'),
      ('Choose a folder','Select your language and a new empty SSD folder, then click Install.') if en else ('Выберите папку','Выберите язык и новую пустую папку на SSD, затем нажмите «Установить».'),
      ('Start your first chat','Open FreedomGPT.exe or the shortcut. The app checks your PC; choose and download a model.') if en else ('Начните первый чат','Откройте FreedomGPT.exe или ярлык. Приложение проверит ПК — выберите и скачайте модель.'),
    ]
    if target=='ubuntu-x64':return [
      ('Download the installer','Click “Download for Ubuntu”. The recommended file ends in .run.') if en else ('Скачайте установщик','Нажмите «Скачать для Ubuntu». Рекомендуемый файл заканчивается на .run.'),
      ('Run it in Terminal','Open Terminal in the folder containing the file. Copy and run the short command below.') if en else ('Запустите через терминал','Откройте терминал в папке со скачанным файлом. Скопируйте и выполните короткую команду ниже.'),
      ('Choose a model','Wait for the app to open. It checks your hardware and lets you choose a suitable model.') if en else ('Выберите модель','Дождитесь открытия приложения. Оно проверит компьютер и предложит подходящие модели.'),
    ]
    return [
      ('Check your Mac','The preview requires Apple Silicon M1+ and macOS26.2+. Intel Mac is not supported.') if en else ('Проверьте свой Mac','Тестовая сборка требует Apple Silicon M1+ и macOS26.2+. Для Intel Mac она не подходит.'),
      ('Unpack the ZIP','Click “Download for Mac”, unpack the ZIP and move Freedom GPT.app into Applications.') if en else ('Распакуйте ZIP','Нажмите «Скачать для Mac», распакуйте ZIP и перенесите Freedom GPT.app в «Программы».'),
      ('Open the application','Open Freedom GPT.app. The unsigned preview may require manual OS approval; native Mac execution is not yet verified.') if en else ('Откройте приложение','Запустите Freedom GPT.app. Для сборки без подписи может потребоваться ручное разрешение macOS; запуск на настоящем Mac ещё не проверен.'),
    ]
def command_block(code,key,label,en):
    return f'<div class="install-command"><div class="command-toolbar"><span>{label}</span><button type="button" data-copy-command="{key}" aria-label="{("Copy commands: " if en else "Скопировать команды: ")+label}">{"Copy commands" if en else "Копировать команды"}</button><button type="button" data-select-command="{key}" aria-label="{("Select commands: " if en else "Выделить команды: ")+label}">{"Select" if en else "Выделить"}</button></div><pre><code id="{key}" tabindex="0">{html.escape(code)}</code></pre><div class="command-copy-status" role="status" aria-live="polite"></div><p class="command-hint">{"If one-click copy is unavailable: Select → Ctrl+C (Cmd+C on Mac)." if en else "Если копирование по кнопке недоступно: «Выделить» → Ctrl+C (Cmd+C на Mac)."}</p></div>'
def guides(lang,version,repo):
    en=lang=='en';blocks=[]
    for index,target in enumerate(SYSTEMS):
        title=TITLES[target];mark={'windows-x64':'windows','macos-arm64':'apple','ubuntu-x64':'ubuntu'}[target]
        from download_ui import brand
        items=''.join(f'<li><span>{i+1:02}</span><div><strong>{html.escape(heading)}</strong><p>{html.escape(text.replace("macOS26.2","macOS 26.2"))}</p></div></li>' for i,(heading,text) in enumerate(steps(target,en)))
        short=''
        if target=='ubuntu-x64':short=command_block(f'sh ./FreedomGPT-Setup-{version}-Ubuntu-x64.run','launch-ubuntu','Ubuntu · '+('already downloaded file' if en else 'уже скачанный файл'),en)
        terminal_label={'windows-x64':'PowerShell','macos-arm64':'macOS Terminal','ubuntu-x64':'Ubuntu Terminal'}[target]
        terminal_intro=('Open '+terminal_label+' in a download folder. Paste the entire block. It downloads this release from GitHub, checks SHA256 and starts it.' if en else 'Откройте '+terminal_label+' в папке для загрузок. Вставьте блок целиком: он скачает сборку из GitHub, проверит SHA256 и запустит её.')
        if target=='windows-x64':terminal_intro+=(' Enter a new empty SSD folder when asked. This creates a portable installation; no separate Python is needed.' if en else ' Когда появится запрос, укажите новую пустую папку на SSD вне папки пользователя. Это переносимая установка; отдельный Python не нужен.')
        if target=='macos-arm64':terminal_intro+=(' These commands have not been executed on a physical Mac. OS approval may still be required.' if en else ' Эти команды ещё не выполнялись на настоящем Mac. Может потребоваться ручное разрешение macOS.')
        if target=='ubuntu-x64':terminal_intro+=(' If curl is missing, use the download button and the short command above.' if en else ' Если curl не найден, скачайте файл кнопкой и выполните короткую команду выше.')
        formats={
          'windows-x64':('EXE is the recommended installer. ZIP is portable: extract it completely into a new folder and run FreedomGPT.exe.' if en else 'EXE — рекомендуемый установщик. ZIP — переносимая версия: полностью распакуйте в новую папку и откройте FreedomGPT.exe.'),
          'ubuntu-x64':('.run is the recommended installer. DEB is for your package manager; TAR.GZ is an archive for manual installation.' if en else '.run — рекомендуемый установщик. DEB — пакет для менеджера пакетов; TAR.GZ — архив для ручной установки.'),
          'macos-arm64':('The ZIP contains a complete application. This preview requires M1+ and macOS26.2+, and is unsigned/not notarized.' if en else 'В ZIP лежит готовое приложение. Эта тестовая сборка требует M1+ и macOS26.2+; она без подписи и нотарификации.'),
        }[target].replace('macOS26.2','macOS 26.2')
        blocks.append(f'<details class="installation-system" id="install-{target}" {"open" if index==0 else ""}><summary>{brand(mark)}<span>{title}<small>{"Step-by-step installation and terminal commands" if en else "Установка по шагам и команды для терминала"}</small></span><span class="guide-chevron">+</span></summary><div class="installation-body"><p class="install-format-note">{formats}</p><ol class="install-steps">{items}</ol>{short}<details class="terminal-guide"><summary>{"Advanced: download and install through Terminal" if en else "Для опытных: скачать и установить через терминал"}<span>⌘</span></summary><p>{terminal_intro}</p>{command_block(commands(target,version,repo),"install-command-"+target,terminal_label,en)}</details></div></details>')
    title='First time installing? Start here.' if en else 'Устанавливаете впервые? Начните здесь.'
    intro='Download directly from the project’s official GitHub releases, without an account. Python and engines are included. Choose your OS below.' if en else 'Файлы скачиваются из официальных релизов проекта в GitHub, без регистрации. Python и движки уже включены. Выберите свою систему ниже.'
    after='After launch: let the app check your PC, select a model and download it. Models need extra disk space. Local chats work offline after the models are downloaded.' if en else 'После запуска: дождитесь проверки ПК, выберите модель и скачайте её. Для весов моделей нужно дополнительное место на диске. После загрузки моделей локальные чаты работают без интернета.'
    return f'<section class="installation-guide" id="installation"><div class="installation-heading"><span>{"INSTALLATION GUIDE" if en else "ПОНЯТНАЯ УСТАНОВКА"}</span><h3>{title}</h3><p>{intro}</p></div>'+''.join(blocks)+f'<div class="after-install"><strong>{"Next: your first model" if en else "Дальше — первая модель"}</strong><p>{after}</p><div><a href="{repo}/blob/main/{"INSTALL.md" if en else "INSTALL.ru.md"}">{"Full guide on GitHub ↗" if en else "Полная инструкция в GitHub ↗"}</a><a href="{repo}/blob/main/BUILD.md">{"Build from source ↗" if en else "Разработчикам: сборка из исходников ↗"}</a><a href="https://t.me/AI1rus">{"Need help? @AI1rus ↗" if en else "Нужна помощь? @AI1rus ↗"}</a></div></div></section>'
def markdown(lang,version,repo):
    en=lang=='en';lines=[f'# Freedom GPT {version} — '+('installation guide' if en else 'понятная установка'),'','[Website](https://aionpc.ru/#download) · [Telegram @AI1rus](https://t.me/AI1rus) · '+('[Русский](INSTALL.ru.md)' if en else '[English](INSTALL.md)'),'',('The ready-made packages include Python, Node.js and engines. Model weights download separately. Pick the download for your OS; a GitHub account is not required.' if en else 'В готовых сборках уже есть Python, Node.js и движки. Веса моделей скачиваются отдельно. Выберите файл для своей ОС; аккаунт GitHub для скачивания не нужен.'),'']
    patterns={'windows-x64':f'FreedomGPT-Setup-{version}.exe','ubuntu-x64':f'FreedomGPT-Setup-{version}-Ubuntu-x64.run','macos-arm64':f'FreedomGPT-{version}-macOS-AppleSilicon.zip'}
    for target in SYSTEMS:
        download_label=('Download for ' if en else 'Скачать для ')+{'windows-x64':'Windows','macos-arm64':'Mac','ubuntu-x64':'Ubuntu'}[target]
        lines+=['## '+TITLES[target],'',f'**[{download_label}]({repo}/releases/download/v{version}/{patterns[target]})**','']
        lines += [f'{i+1}. **{heading}.** {text.replace("macOS26.2","macOS 26.2")}' for i,(heading,text) in enumerate(steps(target,en))]
        if target=='ubuntu-x64':lines+=['','```sh',f'sh ./FreedomGPT-Setup-{version}-Ubuntu-x64.run','```']
        if target=='macos-arm64':lines+=['',('Mac preview: native execution and these commands remain unverified; manual OS approval may be required.' if en else 'Тестовая сборка Mac: запуск и эти команды ещё не проверены на настоящем Mac; может понадобиться ручное разрешение ОС.')]
        terminal={'windows-x64':'PowerShell','macos-arm64':'Terminal','ubuntu-x64':'Terminal'}[target]
        terminal_note=('Open '+terminal+' in a folder for downloads and paste the full block. The file is verified against the release SHA256.' if en else 'Откройте '+terminal+' в папке для загрузок и вставьте блок целиком. Файл проверяется по SHA256 релиза.')
        if target=='windows-x64':terminal_note+=(' Enter a new empty SSD folder when prompted. This creates a portable installation.' if en else ' Укажите новую пустую папку на SSD вне папки пользователя. Будет создана переносимая установка.')
        if target=='ubuntu-x64':terminal_note+=(' If curl is missing, use the download button and the short command above.' if en else ' Если curl не найден, скачайте файл кнопкой и выполните короткую команду выше.')
        lines+=['','### '+('Terminal download and installation' if en else 'Скачать и установить через терминал'),'',terminal_note,'','```'+('powershell' if target=='windows-x64' else 'sh'),commands(target,version,repo),'```','']
    lines+=['## '+('Choose your first model' if en else 'Выберите первую модель'),'',('The application checks hardware and helps you select a model. Download the model, activate it, then start a chat. Search and new downloads need internet; installed local models can run offline. Keep free SSD space for weights and updates.' if en else 'Приложение проверит железо и поможет выбрать модель. Скачайте модель, активируйте и создайте чат. Поиск и новые загрузки требуют интернета; скачанные локальные модели могут работать офлайн. Оставьте место на SSD для весов и обновлений.'),'','[Telegram @AI1rus](https://t.me/AI1rus) · [Build from source](BUILD.md)']
    lines+=['','## '+('Upgrading from 1.4.x' if en else 'Переход с 1.4.x'),'',('Stop the app, keep your backup and run the full 1.5.0 installer once in your existing Freedom GPT folder. Chats and models are preserved. The legacy automatic update channel does not install 1.5.0. From 1.5.0, updates start only after you click Check for updates.' if en else 'Остановите приложение, сохраните резервную копию и один раз запустите полный установщик 1.5.0 в прежнюю папку Freedom GPT. Чаты и модели сохраняются. Старый автоматический канал не устанавливает 1.5.0. Начиная с 1.5.0 обновления запускаются только кнопкой «Проверить обновления».')]
    return '\n'.join(lines)+'\n'
