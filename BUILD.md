# Build and publish Freedom GPT

Windows x64, Node.js24+, .NET Framework4.8 csc.exe, Git and Python from a clean
unpacked Freedom GPT runtime are required. Keep temporary files and generated
artifacts on the project drive. Run `npm ci --ignore-scripts` in app/ first.

## Local build

```powershell
$env:TEMP = "$PWD\.tmp"
$env:TMP = $env:TEMP
$env:npm_config_cache = "$PWD\.cache\npm"
$env:FREEDOM_NODE = 'C:\Program Files\nodejs\node.exe'
$python = 'D:\FreedomGPT-runtime\runtime\python\python.exe'
& $python packaging\publish.py --version 1.2.1 --runtime-from D:\FreedomGPT-runtime --prepare-only
```

Version numbers are examples: use a new version for every published release.
The command creates a clean installer, portable ZIP, source archive, SHA256SUMS
and signed update manifest in release/. It does not publish with --prepare-only.
Validate the actual app, model and upgrade before publication.

The binary runtime is copied from an explicit allowlist. Shared CUDA libraries
are included once in runtime/cuda; process-local PATH supplies both local engines.
All third-party licenses stay included. The clean bundle has no personal data.

## Publish new features

From the reviewed Git checkout, run the same command without --prepare-only:

```powershell
& $python packaging\publish.py --version 1.2.1 --runtime-from D:\FreedomGPT-runtime
```

It builds, commits the explicit public source allowlist, pushes main, creates
a draft release, uploads the assets and publishes it. GitHub CLI or Git Credential
Manager must already be signed in. Never embed tokens in URLs, scripts or source.
Do not reuse a published version or overwrite its assets. A commit alone is not
an application update. For first publication, initialize and review the Git repo
and configure its remote first.

## Signing and updates

The first signing run creates `.private/release-signing-key.pem` and the public
`app/update-key.pub`. Back up the private key securely. Never upload, share,
commit or include `.private/` in an archive. Existing public keys are not silently
replaced by a different private key. Losing the key prevents automatic trust in
a replacement key.

`.private/update-baseline.json` records the first public release. Later update
ZIPs contain cumulative changes since this baseline, so clients can skip versions.
Back up the baseline with the key. New installations receive the complete EXE
or portable ZIP. Updates verify Ed25519, HTTPS, SHA256 and each managed file.

Updates wait for idle sessions, image generation, model activation and model
downloads. An independent helper runtime avoids locked application libraries.
Files are staged and replaced with application-file backups; failures roll back.
Chats, models, uploads, workspaces, settings and user prompts are excluded.
The window reconnects and reloads when the application version changes.

Manifest signatures are separate from Authenticode. The Windows installer is
not signed with a publisher certificate. Major incompatible runtime changes
require a tested migration before release.

## Private installation and SSD

Export-to-SSD.cmd creates a separate private copy with optional verified models
and chat export. Do not redistribute that copy. A physical external SSD and a
different PC were not available for testing in this environment.

An optional private `data/private-runtime.json` preserves an existing agent
profile, toolkit and model server behind the interface. It is excluded from
public builds and update paths. The author's personal copy uses this adapter;
the public release creates a clean local profile.
