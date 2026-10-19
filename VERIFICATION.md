# Freedom GPT 1.2.0 verification

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
