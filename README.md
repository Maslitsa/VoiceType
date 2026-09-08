<div align="center">

# VoiceType

**Hold Ctrl+Alt, talk, and the text appears in whatever window you were typing in.**

Background dictation for Windows, built on
[RealtimeSTT](https://github.com/KoljaB/RealtimeSTT).
It handles sentences that switch language halfway through.

[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4?logo=windows&logoColor=white)](#requirements)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Built on RealtimeSTT](https://img.shields.io/badge/built%20on-RealtimeSTT-8A2BE2)](https://github.com/KoljaB/RealtimeSTT)
[![Stars](https://img.shields.io/github/stars/Maslitsa/VoiceType?style=social)](https://github.com/Maslitsa/VoiceType/stargazers)

<img src="docs/img/overlay-hero.png" width="720" alt="The VoiceType pill above the taskbar showing a live waveform and a sentence that starts in English and continues in Russian">

</div>

---

## What it does

VoiceType starts with Windows and stays out of the way. There is no console
window, no taskbar button and nothing in Alt+Tab.

Hold Ctrl+Alt and a small pill appears above the taskbar with a live waveform
and the words as they are recognised. Let go and the text is pasted into
whatever window you were already in, and copied to your clipboard.

Transcription runs locally by default, so nothing leaves your machine. You can
switch to the OpenAI API from the tray if you want better results on Russian
and German.

<div align="center">
<img src="docs/img/overlay-listening.png" width="620" alt="Listening state with a red dot, live waveform and grey preview text"><br>
<em>Listening. Preview text is grey because it comes from a small fast model and is only a guess.</em><br><br>
<img src="docs/img/overlay-done.png" width="620" alt="Done state with a green dot and the final transcript in white"><br>
<em>Done. White text is the final transcript, already pasted and on the clipboard.</em>
</div>

## Install

One command in PowerShell:

```powershell
irm https://raw.githubusercontent.com/Maslitsa/VoiceType/main/install.ps1 | iex
```

This downloads the project to `%LOCALAPPDATA%\Programs\VoiceType`, builds a
virtual environment, installs the dependencies, registers VoiceType to start
when you sign in, and launches it. The first run downloads a few hundred MB of
PyTorch and Whisper weights.

Then hold Ctrl+Alt and talk.

Run the same command again to update. Your `config.json` is kept.

Requires Windows 10 or 11 and Python 3.11 or 3.12. Python 3.13 does not work
because RealtimeSTT declares `python_requires >=3.11,<3.13`. The installer
checks the version before doing anything.

<details>
<summary><b>Options, or a different install location</b></summary>

<br>

A piped script cannot take arguments directly, so build it into a script block:

```powershell
$s = [scriptblock]::Create((irm https://raw.githubusercontent.com/Maslitsa/VoiceType/main/install.ps1))
& $s -InstallDir 'D:\Apps\VoiceType'
& $s -NoAutostart
& $s -Python 'C:\Python312\python.exe'
```

</details>

<details>
<summary><b>Without piping a script from the internet</b></summary>

<br>

Read [install.ps1](install.ps1) first, or skip the pipe:

```powershell
git clone https://github.com/Maslitsa/VoiceType.git
cd VoiceType
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

If you would rather not use a terminal at all, download the
[ZIP](https://github.com/Maslitsa/VoiceType/archive/refs/heads/main.zip), unzip
it somewhere permanent and double-click `INSTALL.bat`.

</details>

<details>
<summary><b>Using the OpenAI API instead of the local model</b></summary>

<br>

Local transcription is the default. It is free, offline and private. The cloud
backend is better on Russian and German, and it is the one that handles
seamless mid-sentence switching.

```powershell
.\install.ps1 -SetApiKey
```

The prompt does not echo the key. It is written to
`%APPDATA%\VoiceType\openai.key` and locked to your account, outside the
project folder so it cannot be committed by accident. Then pick *OpenAI* under
**tray → Transcribed by**.

It is your own key on your own OpenAI account. Nothing is proxied. Cost is
about $0.006 per minute of audio, roughly $3.60 a month at 20 minutes of
dictation a day. Check [current pricing](https://openai.com/api/pricing/).

</details>

<details>
<summary><b>Uninstall</b></summary>

<br>

```powershell
.\install.ps1 -Uninstall
```

Or double-click `UNINSTALL.bat`. This stops VoiceType and removes the
shortcuts, then prints where the folder, the environment and the key file are
so you can delete them yourself.

</details>

## How you use it

| Gesture | What happens |
| --- | --- |
| Hold Ctrl+Alt for longer than 0.7s | Records while held. Release to transcribe and insert. |
| Tap Ctrl+Alt and release under 0.7s | Latches on for hands-free dictation. Tap again to finish, or stop talking and it ends after 2.5s of silence. |
| Any other key while recording | Cancels. Nothing is inserted. |
| Tray icon | Status, pin the language, switch backend, pause the hotkey, edit settings, quit. |

Releasing Ctrl+Alt within 0.25s does nothing at all. That delay is what keeps
ordinary Ctrl+Alt+key shortcuts, and AltGr on layouts that report it as
Ctrl+Alt, from starting a recording.

If you say nothing, nothing is pasted. Whisper invents plausible sentences out
of silence, so every recording is checked by a voice activity detector first
and dropped if it holds no real speech.

## The problem it solves

Whisper picks one language per utterance. Anything you said in another language
comes back translated, or it disappears.

Here is Whisper `base` on a sentence that starts in English and ends in
Russian:

```
Spoken:  I already sent the invoice yesterday, but клиент до сих пор
         не ответил на моё письмо.

Got:     I've already sent me an voice yesterday, but today children
         mind your piece more
```

Bigger models make this worse. On the same clip, `small` and `large-v3-turbo`
both dropped the entire English half that `base` had kept, because more
capacity means a stronger single-language prior.

VoiceType handles it two ways, switchable from the tray:

* Locally, by splitting the recording at pauses and detecting the language of
  each piece separately.
* Through OpenAI, by sending a `languages` list instead of a single language,
  so the model expects all of them at once.

The same audio through the cloud backend:

```
I already sent the invoice yesterday, but клиент до сих пор не ответил
на моё письмо.
```

Measurements for all of this are in [docs/accuracy.md](docs/accuracy.md).

## Local or OpenAI

Both measured on the same machine, a Ryzen 7 7730U with no GPU, against the
same audio played through speakers into the microphone.

| | Local (default) | OpenAI |
| --- | --- | --- |
| Model | Whisper `base` on your CPU | `gpt-transcribe` |
| Wait after you stop | 1.5 to 1.9s, consistent | 1.1 to 2.6s typical, 7.7s seen |
| English | good | better |
| German | good | better |
| Russian | the weak one | much better |
| Mid-sentence switching | only across a pause | yes, seamlessly |
| Cost | free | about $0.006/min |
| Privacy | nothing leaves the machine | audio is uploaded when you dictate |
| Offline | yes | no |

The cloud is not the faster option. Its median is close to local and its worst
case is much worse, because it depends on your connection. Switch to it for
Russian, German and mid-sentence switching, not for speed.

Some examples of the accuracy gap:

| Spoken | Local `base` | OpenAI |
| --- | --- | --- |
| Können Sie mir den Bericht bis morgen früh schicken? | "Das Treffen bringt darauf doll das Tag statt" | exact |
| I already sent the invoice yesterday but клиент до сих пор не ответил... | "I've already sent me an voice yesterday, but today children mind your piece more" | exact, both scripts |
| Ich habe die Rechnung gestern geschickt aber the client has not replied... | first half garbled | exact, both languages |

`tools/check_cloud.py` runs these with your installed Windows voices and prints
what comes back, so you can check rather than take my word for it.

## Something wrong?

Double-click `CHECKUP.bat`, or run:

```powershell
.venv\Scripts\python.exe tools\doctor.py
```

It checks the Python version, the dependencies, your settings, the microphone,
the API key, whether VoiceType is running and whether it starts with Windows.

```
[ ok ] Python version             3.12.14
[ ok ] Dependencies               all present
[ ok ] Settings                   backend=cloud  language=auto-detect
[ ok ] Microphone                 7 device(s), using system default
[ ok ] OpenAI key                 found
[ ok ] Running                    yes
[ ok ] Starts with Windows        yes
```

Anything it cannot fix gets a line telling you what to do.
[docs/troubleshooting.md](docs/troubleshooting.md) goes deeper, and
[issues](https://github.com/Maslitsa/VoiceType/issues) are welcome.

## Requirements

* Windows 10 or 11. The hotkey, the overlay and the paste path are all Win32.
* Python 3.11 or 3.12.
* A microphone. If you are not sure yours is good enough, run
  `tools/check_mic.py` while speaking and it will tell you.
* No GPU needed. A CUDA GPU makes local transcription much faster if you have
  one.

## Support VoiceType

If VoiceType is useful to you, a GitHub star helps more than it looks.

Stars are how people find a project like this, and more users means more bug
reports from setups I cannot test: other languages, other microphones, other
keyboard layouts. That is what makes it better.

## Documentation

| | |
| --- | --- |
| [docs/configuration.md](docs/configuration.md) | Every setting in `config.json` and which ones matter |
| [docs/accuracy.md](docs/accuracy.md) | Measurements: model sizes, language switching, latency, microphone level |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Nothing heard, the hotkey going dead, elevated windows |
| [docs/architecture.md](docs/architecture.md) | How the pieces fit together and the Windows traps behind them |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to help, including things that need no code |
| [CHANGELOG.md](CHANGELOG.md) | What changed |

## Contributing

Small changes are easiest to review. Bug reports from setups I cannot test are
worth as much as code, and several of the open issues need no programming at
all. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

VoiceType is built on [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) by
[Kolja Beigel](https://github.com/KoljaB). RealtimeSTT does the microphone
pipeline, the voice activity detection that ends a hands-free recording, and
the live preview transcript. Those are the parts that make dictation feel
immediate, and none of them are mine. If VoiceType is useful to you, star
RealtimeSTT too.

Transcription is [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
running [OpenAI Whisper](https://github.com/openai/whisper), or the OpenAI API.

Full attribution in [NOTICE](NOTICE).

## License

MIT. See [LICENSE](LICENSE).
