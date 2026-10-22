# Freedom GPT 1.4.2 — понятная установка

[Website](https://aionpc.ru/#download) · [Telegram @AI1rus](https://t.me/AI1rus) · [English](INSTALL.md)

В готовых сборках уже есть Python, Node.js и движки. Веса моделей скачиваются отдельно. Выберите файл для своей ОС; аккаунт GitHub для скачивания не нужен.

## Windows

**[Скачать для Windows](https://github.com/Leongrupp/freedom-gpt/releases/download/v1.4.2/FreedomGPT-Setup-1.4.2.exe)**

1. **Скачайте приложение.** Нажмите «Скачать для Windows» выше. Откройте скачанный EXE-файл.
2. **Выберите папку.** Выберите язык и новую пустую папку на SSD, затем нажмите «Установить».
3. **Начните первый чат.** Откройте FreedomGPT.exe или ярлык. Приложение проверит ПК — выберите и скачайте модель.

### Скачать и установить через терминал

Откройте PowerShell в папке для загрузок и вставьте блок целиком. Файл проверяется по SHA256 релиза. Укажите новую пустую папку на SSD вне папки пользователя. Будет создана переносимая установка.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  $freedomInstallPath = Read-Host 'New empty SSD folder (for example D:\FreedomGPT)'
  if ([string]::IsNullOrWhiteSpace($freedomInstallPath)) { throw 'Choose an empty folder.' }
  $freedomInstallPath = [IO.Path]::GetFullPath($freedomInstallPath)
  $freedomSetupPath = Join-Path (Get-Location) 'FreedomGPT-Setup-1.4.2.exe'
  $freedomHash = 'c7862b0c5e90ebcf454b405fa84047c76c966cd2346e1dae25392574dcd4317a'
  if (!(Test-Path -LiteralPath $freedomSetupPath) -or (Get-FileHash -LiteralPath $freedomSetupPath -Algorithm SHA256).Hash -ne $freedomHash) {
    curl.exe -fL -C - --retry 4 -o $freedomSetupPath 'https://github.com/Leongrupp/freedom-gpt/releases/download/v1.4.2/FreedomGPT-Setup-1.4.2.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Download failed. Run again to resume.' }
  }
  if ((Get-FileHash -LiteralPath $freedomSetupPath -Algorithm SHA256).Hash -ne $freedomHash) { throw 'SHA256 mismatch. Installation stopped.' }
  $freedomProcess = Start-Process -FilePath $freedomSetupPath -ArgumentList ('/extract="' + $freedomInstallPath + '"') -Wait -PassThru
  if ($freedomProcess.ExitCode -ne 0) { throw 'Installation failed. Choose a new empty folder outside your user profile.' }
  Start-Process -FilePath (Join-Path $freedomInstallPath 'FreedomGPT.exe')
}
```

## macOS · Apple Silicon

**[Скачать для Mac](https://github.com/Leongrupp/freedom-gpt/releases/download/v1.4.2/FreedomGPT-1.4.2-macOS-AppleSilicon.zip)**

1. **Проверьте свой Mac.** Тестовая сборка требует Apple Silicon M1+ и macOS 26.2+. Для Intel Mac она не подходит.
2. **Распакуйте ZIP.** Нажмите «Скачать для Mac», распакуйте ZIP и перенесите Freedom GPT.app в «Программы».
3. **Откройте приложение.** Запустите Freedom GPT.app. Для сборки без подписи может потребоваться ручное разрешение macOS; запуск на настоящем Mac ещё не проверен.

Тестовая сборка Mac: запуск и эти команды ещё не проверены на настоящем Mac; может понадобиться ручное разрешение ОС.

### Скачать и установить через терминал

Откройте Terminal в папке для загрузок и вставьте блок целиком. Файл проверяется по SHA256 релиза.

```sh
(
  set -eu
  [ "$(uname -m)" = arm64 ] || { echo 'Apple Silicon is required.'; exit 1; }
  sw_vers -productVersion | awk -F. '{ exit !($1 > 26 || ($1 == 26 && $2 >= 2)) }' || { echo 'macOS26.2+ is required.'; exit 1; }
  freedom_file='FreedomGPT-1.4.2-macOS-AppleSilicon.zip'
  freedom_sha='361c4703cb45f5c44c8b9bd2a4a4cb9a817b1cb9380a16ab9fb52cd75caf1d71'
  freedom_folder='./FreedomGPT-1.4.2-macOS'
  [ ! -e "$freedom_folder" ] || { echo 'The extraction folder already exists. Choose a new folder.'; exit 1; }
  if ! printf '%s  %s\n' "$freedom_sha" "$freedom_file" | shasum -a 256 -c - >/dev/null 2>&1; then
    curl -fL -C - --retry 4 -o "$freedom_file" 'https://github.com/Leongrupp/freedom-gpt/releases/download/v1.4.2/FreedomGPT-1.4.2-macOS-AppleSilicon.zip'
  fi
  printf '%s  %s\n' "$freedom_sha" "$freedom_file" | shasum -a 256 -c -
  ditto -x -k "$freedom_file" "$freedom_folder"
  open "$freedom_folder/Freedom GPT.app"
)
```

## Ubuntu Linux

**[Скачать для Ubuntu](https://github.com/Leongrupp/freedom-gpt/releases/download/v1.4.2/FreedomGPT-Setup-1.4.2-Ubuntu-x64.run)**

1. **Скачайте установщик.** Нажмите «Скачать для Ubuntu». Рекомендуемый файл заканчивается на .run.
2. **Запустите через терминал.** Откройте терминал в папке со скачанным файлом. Скопируйте и выполните короткую команду ниже.
3. **Выберите модель.** Дождитесь открытия приложения. Оно проверит компьютер и предложит подходящие модели.

```sh
sh ./FreedomGPT-Setup-1.4.2-Ubuntu-x64.run
```

### Скачать и установить через терминал

Откройте Terminal в папке для загрузок и вставьте блок целиком. Файл проверяется по SHA256 релиза. Если curl не найден, скачайте файл кнопкой и выполните короткую команду выше.

```sh
(
  set -eu
  freedom_file='FreedomGPT-Setup-1.4.2-Ubuntu-x64.run'
  freedom_sha='c6e4100867c74ee963f32cddbeb2ad3191562f791ee22e2cd64bace82e684910'
  if ! printf '%s  %s\n' "$freedom_sha" "$freedom_file" | sha256sum -c - >/dev/null 2>&1; then
    curl -fL -C - --retry 4 -o "$freedom_file" 'https://github.com/Leongrupp/freedom-gpt/releases/download/v1.4.2/FreedomGPT-Setup-1.4.2-Ubuntu-x64.run'
  fi
  printf '%s  %s\n' "$freedom_sha" "$freedom_file" | sha256sum -c -
  sh "./$freedom_file"
)
```

## Выберите первую модель

Приложение проверит железо и поможет выбрать модель. Скачайте модель, активируйте и создайте чат. Поиск и новые загрузки требуют интернета; скачанные локальные модели могут работать офлайн. Оставьте место на SSD для весов и обновлений.

[Telegram @AI1rus](https://t.me/AI1rus) · [Build from source](BUILD.md)

## Переход с 1.4.x

Остановите приложение, сохраните резервную копию и один раз запустите полный установщик 1.5.0 в прежнюю папку Freedom GPT. Чаты и модели сохраняются. Старый автоматический канал не устанавливает 1.5.0. Начиная с 1.5.0 обновления запускаются только кнопкой «Проверить обновления».
