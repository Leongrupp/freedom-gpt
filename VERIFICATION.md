# Freedom GPT verification history

Verified on Windows 11 with Ryzen9 7900X, 32 GB RAM and NVIDIA RTX4080 16 GB.
Other physical PCs and an external SSD on another PC were not tested.

## Completed checks

- Python sources parsed successfully and the production React frontend built.
- The Russian and English interfaces switch without restarting the application.
- The first-run screen detects CPU, RAM, NVIDIA VRAM and free disk space.
- Usual interface, website and product documentation use Freedom GPT branding.
  Original third-party legal notices are preserved separately.
- The public bundle scan contains no personal database, credentials or model weights.
- The pinned public key verifies the published update envelope; tampered
  signatures are rejected before files are changed.
- Protected settings/model paths, path traversal, Windows reserved paths and
  alternate data stream paths are rejected by the update allowlist.
- A synthetic transaction installed files while preserving user settings.
  An injected failure rolled back the changed application file.
- An isolated application received a signed synthetic1.2.1 package automatically,
  installed it, restarted and retained its saved session and settings.
  The fixture transport and test key are not in the public application.
- The packaged text engine loaded the standard65K coding model using shared
  cuBLAS, answered a real code request and restored the previous model process.
- The packaged image engine generated a real1024×1024 PNG at8 steps using the
  shared cuBLAS libraries, finishing the native process in23.88 seconds.
- Native PE imports were checked. The image engine includes its five
  application-local Microsoft C++ runtime DLLs, with valid Microsoft signatures
  and recorded SHA256 hashes, so those files do not depend on a separate runtime
  installation. The final installer was extracted and its managed files hashed.
- The author's private upgrade retained all22 existing session IDs. Original
  model/agent configuration hashes matched before and after upgrade. A streamed
  code response identified itself as Freedom GPT and used the local model/API.
  The private toolkit remained available with21 tools in that test session.
- The upgraded private interface generated another1024×1024 image, displayed
  the PNG in its chat and restored the coding model; total image call40.8 seconds.

The complete standard model set is not embedded in the installer. The isolated
tests used already downloaded, verified local model weights, with no paid API.

## Limits

Successful installation, download and update on this PC do not replace testing
across every Windows build, GPU, driver and physical SSD. Other GPUs currently
use CPU. The Windows installer does not have an Authenticode publisher certificate.

Throughput depends on prompt, context and hardware. Earlier code tests ranged
from100.85 to135.36 tokens/s in specific cases; a61K input case gave88.10.
Prompt processing and tools take extra time. Generated code can fail its tests;
fast generation does not mean every answer is correct.

Signing proves possession of the release signing key, not absence of software
defects. Preserve the key and baseline privately, review changes and verify
updates before publishing. Source commits alone do not update installed clients.

## Version 1.3 model discovery and video gates

Live Hugging Face and Ollama searches, GGUF architecture/context inspection,
catalog additions, deduplication, token protection, the free video endpoint and
preservation of 24 personal sessions were checked on the development PC.
An isolated 1.2 client accepted the signed 1.3 update using its original verifier;
the upgraded clean application started with the new search/video modules.

The full video feature validation is gated on a real Wan generation after all three weights
finish downloading: full WebM decode, HTTP Range delivery, restored coding-model
health and a subsequent local model response. An incomplete model download or a
working interface alone does not satisfy that gate. Memory recommendations for
other GPUs remain estimates. No subscription or payment service is connected.


## Version 1.4.2 platform release

Windows: a clean copy runs with PATH restricted to Windows system folders and
its private Python. Startup, empty history, chat creation, restart persistence,
Node.js, bundled components and offline repair of a missing dependency passed.
The actual EXE extraction and managed file hashes were checked.

Ubuntu 24.04: app installation, private Python/Node/pip, gateway, chat creation,
restart persistence and offline dependency repair passed without system Python
or network. The .run and DEB are checked through actual installation. The native
Linux CUDA engine previously loaded the same coding model and produced text and
Python. This does not substitute for physical Linux desktop or AMD GPU tests.

macOS: Apple Silicon, minimum macOS 26.2. Native-file architecture/dependency and
archive integrity checks passed. The build remains an unsigned candidate;
execution on a real Mac, signing and notarization are outstanding.

A real code response through the updated personal Windows UI and copy/paste
were checked. Public support links appear in Settings; the personal installation
suppresses that section. Project chats and personal model routing are preserved.

Video remains experimental on other hardware and operating systems. The Wan
pack and real Windows rendering were verified for 1.4.2 as detailed below.
Other model transfers remain paused. No universal 100+ tokens/s claim is made.
Public packages do not include personal chats, secrets or model weights.

Website domain: aionpc.ru. HTTP domain routing is prepared. DNS is pending the
owner's change. HTTPS and shared VPN-port routing are deferred by owner choice;
the VPN port, configuration and processes are preserved.

## 1.4.2 video and Windows file-sharing fix
Real rendering found WinError 5 when a progress JSON destination was briefly held open on Windows. State writes now use unique temporary files, bounded sharing-violation retries and a writer lock; reads retry short sharing violations too. Video progress only writes when it changes. A real Windows destination-lock test and 400 concurrent writes with a reader passed.
The corrected candidate rendered Wan 2.1 512x288, 33 frames, 16 fps and 20 steps: 30.76 s native engine, 50.24 s including GPU handoff and coder restoration. WebM VP8, 33 decoded frames, HTTP 206 and a subsequent local coder reply passed. Contact sheets were visually reviewed. VAE CUDA decode took 8.73 s; CPU decode had taken about 63 s per tile. Native macOS rendering remains untested.
The final 1.4.2 application repeated the same test in 52.68 s while packaging was running. Its clip was byte-identical to the visually reviewed candidate. A UI code reply and copy/paste after video, application restart and video-history recovery passed too.

## Release 1.5.0

See [1.5.0 checks and remaining limits](docs/RELEASE-1.5.0-VERIFICATION.md). Windows and offline Ubuntu installation/runtime checks passed. Mac native execution remains unverified. Legacy automatic migration from 1.4.x is deliberately blocked; use the full installer once.

