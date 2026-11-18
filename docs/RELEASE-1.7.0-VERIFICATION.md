# Freedom GPT 1.7.0 — verification and scope

This release packages the current Freedom workspace, including project
Neurosphere, specialist agents, conversation personality, goals, memory,
queue/steer controls and the measured Turbo profile recovery fix.

## Checks

- Windows: the final EXE was extracted, verified and launched with its bundled
  Python and a PATH restricted to Windows system directories. Clean startup,
  empty history, gateway readiness, chat/queue/steer, branching, memory,
  specialist create/delete, personality, skills, persistence across restart
  and offline dependency repair passed.
- Ubuntu: the exact portable archive and installers are verified in native
  Ubuntu 24.04 CI, inside a clean container without network or system Python.
  The `.run` and `.deb` installers receive independent installation checks.
- macOS: the exact ZIP is verified on an Apple Silicon macOS runner. Bundled
  Python, native dependencies, installation, gateway/chat, skills, persistence
  and restart are checked. The archive SHA256 is pinned in CI.
- All three packages are compared with the reviewed application sources.
  Signed update envelopes, archive manifests, file hashes and modes are checked.
  Native runtime copying resumes safely after interruption and preserves
  legitimate nested library folders such as `prompt_toolkit/output`.

The release asset `VERIFICATION-1.7.0.json` contains the final check results
and links to the native CI runs. Publication is blocked unless these checks pass.

## Limits

Core chat tests use a loopback model fixture to test the application and
streaming independently of model downloads. They do not benchmark language
model intelligence, GPU inference, every driver or every physical computer.
Ubuntu desktop/GPU, Finder launch, VR headsets, camera devices and personal
voice models are not certified by these checks.

Large model weights and the author's voice recordings/profiles, chats,
credentials and local project databases are not included. Optional voice,
camera, VR and other external integrations require their own components and
hardware. Browser automation requires a supported installed browser and does
not guarantee that websites will never request a CAPTCHA.

Windows installers are not Authenticode-signed. The Mac package requires
Apple Silicon and macOS 26.2+, is unsigned and is not notarized. Intel Mac and
older macOS versions are not supported by these binaries.

Before upgrading an existing installation, stop it and back up its data.
Update checks are manual; old legacy update channels are preserved separately.
