# Contributing

Small, focused contributions are welcome: reproducible bug reports, interface
translations, model compatibility reports, accessibility and performance fixes.

1. Describe the expected and actual behavior, Windows version, CPU/RAM/GPU,
   model and quantization. Remove private data from screenshots and logs.
2. Keep changes focused. Preserve the local-only API, resumable verified model
   downloads and existing chats, files and settings.
3. Build the frontend using `npm ci --ignore-scripts` and `npm run build` in app/.
   See BUILD.md for packaged development and release preparation.
4. Explain how the change was verified and what remains untested.

Please do not commit weights, generated builds, private keys, cookies or real
customer data. The maintainer publishes signed release packages after review.
