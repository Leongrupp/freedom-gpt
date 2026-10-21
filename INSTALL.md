# Freedom GPT 1.5.0 — installation guide

[Website](https://aionpc.ru/#download) · [Telegram @AI1rus](https://t.me/AI1rus) · [Русский](INSTALL.ru.md)

The ready-made packages include Python, Node.js and engines. Model weights download separately. Pick the download for your OS; a GitHub account is not required.

## Windows

**[Download for Windows](https://github.com/Leongrupp/freedom-gpt/releases/download/v1.5.0/FreedomGPT-Setup-1.5.0.exe)**

1. **Download the app.** Click “Download for Windows” above. Open the downloaded EXE file.
2. **Choose a folder.** Select your language and a new empty SSD folder, then click Install.
3. **Start your first chat.** Open FreedomGPT.exe or the shortcut. The app checks your PC; choose and download a model.

### Terminal download and installation

Open PowerShell in a folder for downloads and paste the full block. The file is verified against the release SHA256. Enter a new empty SSD folder when prompted. This creates a portable installation.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  $freedomInstallPath = Read-Host 'New empty SSD folder (for example D:\FreedomGPT)'
  if ([string]::IsNullOrWhiteSpace($freedomInstallPath)) { throw 'Choose an empty folder.' }
  $freedomInstallPath = [IO.Path]::GetFullPath($freedomInstallPath)
  $freedomSetupPath = Join-Path (Get-Location) 'FreedomGPT-Setup-1.5.0.exe'
  $freedomHash = '4fe922d80486aceb7a340f67c285001d88d33f375d10957b12642f6d492fd49f'
  if (!(Test-Path -LiteralPath $freedomSetupPath) -or (Get-FileHash -LiteralPath $freedomSetupPath -Algorithm SHA256).Hash -ne $freedomHash) {
    curl.exe -fL -C - --retry 4 -o $freedomSetupPath 'https://github.com/Leongrupp/freedom-gpt/releases/download/v1.5.0/FreedomGPT-Setup-1.5.0.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Download failed. Run again to resume.' }
  }
  if ((Get-FileHash -LiteralPath $freedomSetupPath -Algorithm SHA256).Hash -ne $freedomHash) { throw 'SHA256 mismatch. Installation stopped.' }
  $freedomProcess = Start-Process -FilePath $freedomSetupPath -ArgumentList ('/extract="' + $freedomInstallPath + '"') -Wait -PassThru
  if ($freedomProcess.ExitCode -ne 0) { throw 'Installation failed. Choose a new empty folder outside your user profile.' }
  Start-Process -FilePath (Join-Path $freedomInstallPath 'FreedomGPT.exe')
}
```

## macOS · Apple Silicon

**[Download for Mac](https://github.com/Leongrupp/freedom-gpt/releases/download/v1.5.0/FreedomGPT-1.5.0-macOS-AppleSilicon.zip)**

1. **Check your Mac.** The preview requires Apple Silicon M1+ and macOS 26.2+. Intel Mac is not supported.
2. **Unpack the ZIP.** Click “Download for Mac”, unpack the ZIP and move Freedom GPT.app into Applications.
3. **Open the application.** Open Freedom GPT.app. The unsigned preview may require manual OS approval; native Mac execution is not yet verified.

Mac preview: native execution and these commands remain unverified; manual OS approval may be required.

### Terminal download and installation

Open Terminal in a folder for downloads and paste the full block. The file is verified against the release SHA256.

```sh
(
  set -eu
  [ "$(uname -m)" = arm64 ] || { echo 'Apple Silicon is required.'; exit 1; }
  sw_vers -productVersion | awk -F. '{ exit !($1 > 26 || ($1 == 26 && $2 >= 2)) }' || { echo 'macOS26.2+ is required.'; exit 1; }
  freedom_file='FreedomGPT-1.5.0-macOS-AppleSilicon.zip'
  freedom_sha='6a25cec10e906659c6f0106273ee63e3f3e0dc8bd11998e36cf129094d70908b'
  freedom_folder='./FreedomGPT-1.5.0-macOS'
  [ ! -e "$freedom_folder" ] || { echo 'The extraction folder already exists. Choose a new folder.'; exit 1; }
  if ! printf '%s  %s\n' "$freedom_sha" "$freedom_file" | shasum -a 256 -c - >/dev/null 2>&1; then
    curl -fL -C - --retry 4 -o "$freedom_file" 'https://github.com/Leongrupp/freedom-gpt/releases/download/v1.5.0/FreedomGPT-1.5.0-macOS-AppleSilicon.zip'
  fi
  printf '%s  %s\n' "$freedom_sha" "$freedom_file" | shasum -a 256 -c -
  ditto -x -k "$freedom_file" "$freedom_folder"
  open "$freedom_folder/Freedom GPT.app"
)
```

## Ubuntu Linux

**[Download for Ubuntu](https://github.com/Leongrupp/freedom-gpt/releases/download/v1.5.0/FreedomGPT-Setup-1.5.0-Ubuntu-x64.run)**

1. **Download the installer.** Click “Download for Ubuntu”. The recommended file ends in .run.
2. **Run it in Terminal.** Open Terminal in the folder containing the file. Copy and run the short command below.
3. **Choose a model.** Wait for the app to open. It checks your hardware and lets you choose a suitable model.

```sh
sh ./FreedomGPT-Setup-1.5.0-Ubuntu-x64.run
```

### Terminal download and installation

Open Terminal in a folder for downloads and paste the full block. The file is verified against the release SHA256. If curl is missing, use the download button and the short command above.

```sh
(
  set -eu
  freedom_file='FreedomGPT-Setup-1.5.0-Ubuntu-x64.run'
  freedom_sha='4bcd48dac9d19735f9fd433b76b6e13e8ce6e535f6fbf2120b9aed5585e6855d'
  if ! printf '%s  %s\n' "$freedom_sha" "$freedom_file" | sha256sum -c - >/dev/null 2>&1; then
    curl -fL -C - --retry 4 -o "$freedom_file" 'https://github.com/Leongrupp/freedom-gpt/releases/download/v1.5.0/FreedomGPT-Setup-1.5.0-Ubuntu-x64.run'
  fi
  printf '%s  %s\n' "$freedom_sha" "$freedom_file" | sha256sum -c -
  sh "./$freedom_file"
)
```

## Choose your first model

The application checks hardware and helps you select a model. Download the model, activate it, then start a chat. Search and new downloads need internet; installed local models can run offline. Keep free SSD space for weights and updates.

[Telegram @AI1rus](https://t.me/AI1rus) · [Build from source](BUILD.md)

## Upgrading from 1.4.x

Stop the app, keep your backup and run the full 1.5.0 installer once in your existing Freedom GPT folder. Chats and models are preserved. The legacy automatic update channel does not install 1.5.0. From 1.5.0, updates start only after you click Check for updates.
