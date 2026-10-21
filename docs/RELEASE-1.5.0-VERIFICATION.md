# Freedom GPT 1.5.0 verification

Verified on 2026-10-21. This report describes checks performed, not a guarantee that no defects exist.

- Windows: extracted the actual EXE, verified every signed manifest file, then ran the included private Python with global developer tools absent from PATH. Started the UI and agent, checked the component inventory, restarted with preserved chat history, and repaired an intentionally missing dependency from the offline wheelhouse.
- Ubuntu 24.04: official container, networking disabled and no system Python. Installed the actual TAR package, launched the app and agent, restarted with preserved chats, repaired a dependency offline and reinstalled with preserved data. Also installed the real `.run` and DEB packages and checked private Python imports.
- Both running installations: goal draft and current goal engine, three queued tasks, text editing, reordering, cancellation, steering, streamed agent response, usage counters, branches with copied history and an empty queue, project-memory recall, skill listing and optional accounts. Requests used a loopback API fixture, not paid or external providers.
- 60 isolated account, download, model import, reward and HTTP regressions passed against the extracted Windows package. Four configuration/memory regressions passed, including backup creation and preservation of malformed configuration.
- Archive CRC, per-file SHA256, Unix permissions, signed update packages, wrong-OS rejection, signature tampering and rollback checked. Personal histories, credentials and model weights are excluded.
- macOS: 104 native binaries audited for ARM64, dependency availability and minimum macOS 26.2. Archive hashes, modes, launcher and signed update verified. **No native Mac execution or notarization test.**
- Existing local GPU model answered again after the personal app restart. This release does not claim new rendering or generation-speed benchmarks across all supported systems.
- Loop and correction hotfix: thirteen focused regressions and a real local terminal failure passed. An isolated running gateway accepted an urgent correction during a 20-second foreground command in about 0.4 seconds, retained its history, replayed the receipt without duplicating the correction, blocked the third identical failing command, and remained idle without duplicate failure notifications. Browser harness exceptions and read-only status probes are covered by the loop guard.
- Real-model workflow: the local model created an expense-summary module, implemented an urgent correction, ran six passing tests, completed a queued README and finished a goal in two steps. File editing, stale-edit rejection, recoverable removal/restoration and branching with history/files were also checked. Actual UI captures are documented in [SCREENSHOTS.md](SCREENSHOTS.md).
- Quality fixes: calibration-only `imatrix` GGUF files are excluded from model suggestions, including cached results and add requests. Native tool metadata now registers created Markdown and other project files in chat. Each fix has four focused regressions. Active-model steering appends corrections at the current transcript tail, preserving earlier messages and receiving them during text-only turns.

## Updates and migration

1.5.0 checks, downloads and applies updates only following the user's **Check for updates** action. Legacy 1.4.x automatic clients are intentionally blocked by the signed minimum version. Install the full 1.5.0 package once into the existing application folder after stopping it, retaining your backup. Subsequent updates use the manual flow.

## Remaining boundaries

Hardware, GPU drivers, model compatibility and context affect performance. Browser and specialist applications such as Blender are separate installations. Real GitHub/Hugging Face/cloud accounts were not registered or modified by these checks. Encrypted persistent API credential storage is Windows-only; other platforms support session storage. Image/video rendering and macOS execution need real hardware validation beyond these tests.
