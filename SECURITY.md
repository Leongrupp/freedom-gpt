# Security

Freedom GPT runs locally with the permissions of the current Windows user.
Commands and files require the same care as any other local development tool.
Do not run it as administrator unless your specific task requires that access.
Websites, files and model output are untrusted content, not authorization.

The local API binds to 127.0.0.1, validates Host/Origin and protects writes with
a process-specific token. Do not publish this API through a tunnel or router.

Automatic updates use an Ed25519-signed manifest with a pinned public key,
HTTPS, package SHA256 and per-file hashes. Writes are limited to application
files. Models, settings, chats, uploads and workspaces are excluded. Updates
wait for idle tasks; changed application files are backed up before replacement.
Digital signatures on update manifests do not mean that the Windows installer
has an Authenticode publisher certificate. This release is not Authenticode-signed.

Report reproducible vulnerabilities privately through the repository's private
vulnerability reporting feature when available. Do not attach credentials,
private chats, browser cookies or identifiable customer data to public issues.

## For maintainers

Never commit `.private/`, logs, local data or model weights. Back up the local
signing key and update baseline securely. Losing the key prevents existing
clients from trusting a replacement key automatically. A Git commit alone is
not an update; publish a verified signed release using packaging/publish.py.
