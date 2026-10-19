<p align="center"><img src="assets/cover.png" alt="Freedom GPT — Your AI. Your computer." width="100%"></p>

<h1 align="center">Freedom GPT</h1>
<p align="center">A free local AI workspace for Windows. Chat, build software and create images on your own computer.</p>
<p align="center"><a href="https://github.com/Leongrupp/freedom-gpt/releases/latest"><strong>Download for Windows</strong></a> · <a href="README.ru.md">Русский</a> · <a href="#getting-started">Installation</a> · <a href="#support-development">Support development</a></p>
<p align="center"><img alt="Windows x64" src="https://img.shields.io/badge/Windows-10%20%2F%2011-8f9dea"><img alt="Languages: RU and EN" src="https://img.shields.io/badge/Languages-RU%20%2F%20EN-b8a5e8"><img alt="Application source license MIT" src="https://img.shields.io/badge/Source-MIT-a1c9b4"></p>

## Your computer. Your models. Your choice.

Freedom GPT brings local AI into a practical desktop workspace: saved chats,
project folders, files, code, model downloads and a live performance panel.
You choose what runs on your hardware. No cloud API subscription is required.

- **Chat and code:** streaming answers, copyable code, saved conversations and project memory.
- **Three modes:** Fast code, Think and Image. Image generation hands the GPU back to the coding model when finished.
- **Your files:** attach documents and images. Photo analysis needs a compatible vision model.
- **Model library:** inspect hardware, download verified models, resume interrupted downloads, import compatible GGUF files or connect an existing local API.
- **RU / EN:** choose your language in the installer and switch it in the application.
- **Automatic updates:** signed published versions download automatically and install between tasks, preserving chats, settings, models and workspaces. You can turn this off in Settings.
- **Portable folder:** keep the application and its data together on an internal or external SSD.

## Getting started

1. Open [Releases](https://github.com/Leongrupp/freedom-gpt/releases/latest) and download **FreedomGPT-Setup-1.2.0.exe**.
2. Run the installer, choose **English** or **Русский**, and select a new empty folder on an SSD. Allow several GB for the application and additional space for models.
3. Start **FreedomGPT.exe** or the desktop shortcut. The first-run screen checks CPU, RAM, NVIDIA VRAM and free disk space.
4. Choose a model, click **Download model**, wait for SHA256 verification, then **Use model**.
5. Open a chat. To generate images, download the separate image model set and select **Image**.

The portable ZIP is also available in Releases. Extract the **whole archive**,
then run FreedomGPT.exe. Python and the local engines are included. A current
NVIDIA driver is required for NVIDIA acceleration; other GPUs use CPU in this
version. The installer is **not Authenticode-signed**. Do not disable Windows
security protections to install software.

### Models and hardware

| Profile | Model | Approximate starting point |
|---|---|---|
| Standard coding | Huihui Qwen3.8 Coder 27B · IQ3_S3, with vision projector | 32 GB RAM, NVIDIA 16 GB VRAM |
| Image generation | Qwen Image 2.1 Turbo · Q5_K_M, encoder and VAE | NVIDIA 12–16 GB VRAM; shares GPU with the coding model |
| Lighter coding | Qwen3.5 4B · Q4_K_M | 12–16 GB RAM; less capable than the standard model |
| Smallest option | Qwen3.5 0.8B · Q4_K_M | 8 GB RAM; limited coding and tool use |

These are memory estimates, not a speed guarantee. The default model set is
downloaded separately and totals approximately **24.3 GB**. Plan for **35 GB or
more of free SSD space** for a standard installation, temporary downloads and
updates. Long contexts and CPU offloading can be considerably slower.

Model weights are **not** inside the installer. Sources and model licenses are
shown in the library. Import currently supports single-file GGUF models with
native context of at least 64K and an architecture supported by the bundled
engine. Arbitrary training packages and image generators are not installed automatically.

## Offline and private by default

After downloading the models, local inference, chat history and files work
without internet. Downloads, update checks, websites and online search need a
connection. The API listens on **127.0.0.1** only. The clean release contains no
personal chats, credentials, browser profiles or model weights from the author.

Use **Stop-FreedomGPT.cmd** before disconnecting an SSD or making a complete
folder backup. Do not use one installation database from two PCs at the same time.
The target PC still needs its own compatible GPU driver.

## Performance

On the development PC (RTX 4080 16 GB, Ryzen 9 7900X, 32 GB RAM), the standard
model produced a 2016-token code answer at **100.85 tokens/s**, with a following
code answer at **102.34 tokens/s**. A separate direct-engine case reached
135.36 tokens/s. At roughly 61K input tokens, one case measured 88.10 tokens/s.
These are case-specific measurements, excluding prompt processing and tools.
They do not predict every PC, task or generated answer's correctness.

Fast mode can make mistakes. Run tests, review changes and use **Think** for
complex logic. Project memory and compression help continue work, but are not
perfect recall or a substitute for Git and backups.

## Updates and development

Updates are checked on startup and periodically while running. Releases use
an Ed25519-signed manifest, package hashes and a managed file allowlist.
Installation waits for idle tasks and keeps an application-file backup.
Models, chats and user settings are outside that allowlist. Offline checks retry
later; local inference continues. See [SECURITY.md](SECURITY.md).

New features reach installed clients after a verified signed release is
published. A source commit by itself is not a client update. For local builds
and the maintainer release command, see [BUILD.md](BUILD.md).

The repository also includes a bilingual download website. Run
**Start-Website.cmd** for a local preview. Server hosting is configured separately.

## Support development

Freedom GPT is free. If it helps your work and you would like to support future
development, optional Bitcoin donations are welcome:

**BTC · Bitcoin mainnet**

```text
bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6
```

Donations do not unlock features. You can also help by reporting reproducible
bugs, improving translations or contributing focused fixes.

## Contributing and licenses

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and
[verification notes](VERIFICATION.md). Application source is MIT. Third-party
components retain their original notices in [licenses/](licenses/); model
licenses are separate. See [NOTICE](NOTICE).
