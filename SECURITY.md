# Security

## Reporting a vulnerability

Please report security issues privately using GitHub's
[report a vulnerability](https://github.com/Maslitsa/VoiceType/security/advisories/new)
form, rather than opening a public issue.

This is maintained in spare time, so no response time is promised, but
anything sent that way will be read.

## What VoiceType touches

Worth being explicit about, because the permissions look alarming and deserve
to be understood rather than trusted:

- **A global keyboard hook.** Required for a modifier-only chord like
  `Ctrl`+`Alt`, which `RegisterHotKey` cannot express. The hook classifies keys
  and never stores or transmits them.
- **The microphone**, opened *only* while you are recording. Windows' own "app
  is using your microphone" indicator is therefore an honest signal.
- **The clipboard**, to place the transcript.
- **Synthetic keystrokes**, to paste into the focused window.
- **The network**, only when the cloud backend is enabled, and only to
  `api.openai.com`. The default backend is local and sends nothing anywhere.

## Your API key

The key lives in `%APPDATA%\VoiceType\openai.key`, outside the project folder,
with ACL inheritance broken so only your account can read it.

Keeping it out of the project is deliberate: a key inside a repository is one
`git add -f`, one screenshot, or one cloud-sync client away from leaking.
`config.json` is gitignored and CI fails the build if anything key-shaped is
committed, but the file location is the real protection.

If you think a key has leaked, revoke it at
<https://platform.openai.com/api-keys>. That is always the right first move, and rotating a key costs nothing.
