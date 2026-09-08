# FAQ

Questions people ask, with straight answers. If yours is not here, open a
[discussion](https://github.com/Maslitsa/VoiceType/discussions) or an issue.

## Is this just a wrapper around the OpenAI API?

No, but the honest answer has two halves.

VoiceType is a Windows dictation app: a global hotkey, a tray icon, an overlay,
and paste-into-the-focused-window. That part is the same whichever backend you
use, and it is most of the code.

Transcription runs **locally by default** on faster-whisper, and nothing leaves
your machine. The OpenAI backend is opt-in from the tray, and it is better at
one specific thing: a sentence that changes language with no pause in the
middle. See the next question for exactly how much better.

## What does the local backend actually do on a switched sentence?

Measured on `demo/four_languages.wav`, which is in the repo so you can check.
Local is `base` on CPU with int8, the default.

| Clip | Backend | Result |
| --- | --- | --- |
| English then Russian, real pause | local, default | `I already sent the invoice yesterday, but...` |
| English then Russian, real pause | local, `per_segment_language: true` | correct, both halves |
| English then Russian, no pause | local, either setting | English half only |
| Four languages, no pauses | local, any setting | English half only |
| Any of the above | OpenAI | correct |

So: local handles a switch **if you pause at it** and you turn on
`per_segment_language`. It does not handle a switch with no pause, because
there is nothing for the splitter to split on.

## Then why is `per_segment_language` off by default?

Because it is a real trade-off, not a free win. A segment is transcribed
without the surrounding context, so punctuation and rare words get worse
(`bis morgen früh schicken` became `bis morgen frischicken`), and it runs about
1.7x slower. For someone who dictates in one language it is a pure regression.

If you switch languages mid-sentence regularly, turn it on. It is one line in
`config.json`, and this is probably the first thing you should change after
installing.

## Does the `languages` list actually do anything?

This one deserves a careful answer, because it is the claim I am least sure of.

`docs/accuracy.md` records a measurement where sending `["en","ru","de"]`
recovered a half-sentence that sending `["ru","en"]` or nothing at all lost.
That was measured on real speech, on this laptop, some weeks ago.

**It does not reproduce on synthetic speech today.** Running the demo clip
through `gpt-transcribe` with no list at all returns all four languages
correctly, three times out of three, in both directions. So either the model
improved, or clean synthesised audio is simply too easy to show the difference,
or both.

Check it on your own voice rather than believing either of us:

```
tools\try_demo.py my_recording.wav --sweep
```

That runs your clip under every list from none up to your full set. If the
shorter lists lose a language for you, the field is earning its keep. If they
do not, it is not, and I would genuinely like to see that in an issue.

## Why not just use whisperX, or faster-whisper, or RealtimeSTT directly?

They solve different problems, and VoiceType is built on two of them.

- **faster-whisper** is the inference library VoiceType uses. It is a library.
- **RealtimeSTT** does the microphone pipeline, the voice activity detection
  and the live preview. VoiceType is one thing you can build with it. Star it
  too.
- **whisperX** does batch transcription of audio files with word-level
  timestamps and diarization. It has no hotkey, no overlay and no paste, and
  its alignment models are language-specific, so it is single-language per file
  by design.

None of them are a dictation app you can hold a key and talk into.

## What about Parakeet, Canary, or another multilingual model?

Not supported yet, and a fair suggestion. NVIDIA's Canary does language
identification as part of decoding, which is a genuinely different approach
from splitting on pauses and would likely beat the local path here.

The backend interface is small (`available()` and `transcribe()`), so adding
one is not a big change. If you want to try it, open an issue and I will help.

## Linux? macOS?

Windows only, and not by preference. The hotkey, the tray icon, the always-on-
top overlay and the paste into the focused window are all Win32. The
transcription half is portable; the app half is not.

A port is welcome but it is close to a rewrite of the UI layer.

## Where does my audio go? Where is my API key?

Locally, audio never leaves the process. There is no telemetry and no analytics
in this repo, and you can check that with grep.

On the OpenAI backend, the audio for that one utterance goes to OpenAI and
nowhere else.

Your key is stored in `%APPDATA%\VoiceType\openai.key`, outside the project
folder, readable only by your Windows account. It is deliberately not in
`config.json`, so you cannot commit it by accident. `.gitignore` blocks
`*.key`, `.env` and `config.json` as a second line of defence.

## What does the API cost?

About $0.006 per minute of audio for `gpt-transcribe`. Ordinary dictation runs
to a few cents a day. You are billed by OpenAI directly; VoiceType has no
account, no server and no middleman.

## How fast is it?

The demo clip is 11 seconds of audio:

| Backend | Time |
| --- | --- |
| local, `base` on CPU | 1.7s |
| OpenAI | 3.6s |

Local is faster and less accurate. The overlay shows a live preview from a
`tiny` model while you talk, which is why the grey preview text sometimes
differs from the white final text.

## Can I use a bigger model, or my GPU?

Yes. `model.final` in `config.json` takes any faster-whisper model name, and
`model.device` defaults to `auto`, which uses CUDA when it can and falls back
to CPU when the driver or cuDNN is not usable.

`large-v3` on a GPU is a large accuracy improvement. On CPU it is too slow for
dictation.

## Was this written by an AI?

Substantially, yes, and it says so in the Reddit post. The problem is mine, the
testing is mine, and the measurements in `docs/accuracy.md` are real numbers
from this machine rather than plausible-sounding ones.

Judge it as code. It has tests, the trade-offs are written down including the
ones that did not work out, and the one claim I cannot currently reproduce is
flagged as such above rather than quietly left in.

## Can I change the hotkey?

Yes, `hotkey` in `config.json`. Ctrl+Alt is the default because it is a chord
almost nothing else uses and it needs no third key.

## It is not working

Run `CHECKUP.bat`. It checks nine things (Python version, virtual environment,
dependencies, settings, device, microphone, API key, whether the app is
running, log size) and prints a fix line for each failure.

If that does not do it, [docs/troubleshooting.md](troubleshooting.md), then an
issue with the `CHECKUP.bat` output pasted in.

## How do I contribute?

[CONTRIBUTING.md](../CONTRIBUTING.md). Short version: the tests are stdlib
`unittest` plus numpy and run in about two seconds, there is no linter to
fight, and a bug report with a wav attached is worth more than most patches.

The most useful thing anyone can send is a recording where it fails.
