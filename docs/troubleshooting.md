# Troubleshooting

Logs are in `logs\voicetype.log` (rotating). Anything a dependency printed
rather than logged lands in `logs\stdout.log`.

---

## It records, but always says "Nothing heard"

The recording was captured and then thrown away by the silence guard. Run:

```powershell
.venv\Scripts\python.exe tools\check_mic.py
```

It records you for six seconds and reports the level, whether the speech
detector fires, and what the transcript comes back as. **Speak during those six
seconds** — it cannot tell a silent room from a broken microphone otherwise.

Read the `quiet vs loud` number first:

| Reading | Meaning | Fix |
| --- | --- | --- |
| **below ~2** | The microphone is not picking up your voice at all. The signal never changes. | Nothing in this app will help. Check **Settings → System → Sound → Input**: right device selected, bar moves when you speak. Check the mute key and any privacy shutter. Check **Settings → Privacy → Microphone** allows desktop apps. |
| **above 2, but `longest run` below the threshold** | Your voice is there but too quiet for the detector. | Raise the level: **Sound → Input → your mic → Properties**, Volume to 100 and enable Microphone Boost. Speak closer. Or lower `recording.min_speech_run`. |
| **above 2, run above threshold** | The microphone is fine; the problem is elsewhere. | Check the log. |

### Why a real sentence can be discarded

Whisper invents plausible sentences out of silence, so every recording is
checked for real speech first. That check is WebRTC VAD, and **it gets less
sensitive the quieter the input is**. On a very quiet microphone, genuinely
spoken Russian once scored a run of 8 against a threshold of 12 and was thrown
away — while silence scored 4.

`recording.vad_aggressiveness` defaults to `1` for this reason. If you still
get false rejections, lower `recording.min_speech_run` (12 = 240 ms of
continuous speech). Raise it instead if room noise is getting through.

The measurements behind those defaults are in
[accuracy.md](accuracy.md#the-vad-gets-less-sensitive-as-the-input-gets-quieter).

---

## The live preview says something different from the final text

This is expected, and the preview is now drawn in grey to make that obvious.

They are two different models. The preview comes from `model.realtime` (`tiny`
by default) running locally so it can keep up with you in real time. The final
transcript comes from `model.final` — or, on the cloud backend, from OpenAI,
which is a different system entirely. A tiny model asked to guess halfway
through a sentence will regularly disagree with a good model that has heard all
of it.

A real example from this machine, saying a German street name:

<img src="img/preview-dimmed.png" width="560" alt="Grey provisional preview text reading 'Tyurkenshtrasse tri'">

<img src="img/preview-final.png" width="560" alt="White final text reading 'Türkenstraße 3.'">

**Grey text is a guess. White text is the answer.** Only the white text is ever
pasted.

To make the preview closer to the final text, raise `model.realtime` from
`tiny` to `base` — it costs more CPU while you speak. To stop showing it at
all and keep just the waveform:

```json
{ "overlay": { "show_partial_text": false } }
```

---

## It got slower, or the label says "local (offline)"

The status line after a dictation tells you which backend produced the text:

| Label | Meaning |
| --- | --- |
| `· cloud` | OpenAI, as configured |
| `· local (offline)` | The network was unreachable, so it fell back |
| `· local (no API key)` | No key configured |
| `· local (cloud error)` | The API returned an error |

**`local (offline)` is the one to care about**, because local is markedly
weaker on Russian and German — a sentence that was perfect yesterday can come
back mangled purely because the wifi dropped.

A failed connection also costs time. VoiceType bounds the connect phase at 4
seconds and then, having seen the network fail, skips the cloud for the next 20
seconds rather than stalling on every recording. Before that bound, a DNS
failure took **11.6 s** before the fallback even started.

If dictation is slow but still says `· cloud`, that is request latency, not
VoiceType. Measured here, the same setup ranged from 1.6 s to 7.7 s across one
evening.

---

## The hotkey stopped working

Almost certainly a lost keyboard hook. Windows removes a low-level hook
**silently** — after a sleep, or if a callback ever overruns its timeout — with
no error and no crash. The app keeps running and looks perfectly healthy while
`Ctrl`+`Alt` does nothing.

A watchdog handles this. Every `hotkey.health_check_seconds` (20) it compares
when Windows last saw *any* input against when our hook last saw one. If the
system has had input we did not, the hook is refreshed — at most once per
`hotkey.min_reinstall_seconds` (60).

Nothing is injected to test it. An earlier version did inject a key, which
worked, but `SendInput` resets the system idle timer and would have quietly
stopped the laptop from ever sleeping. The passive check leaves a genuinely
idle machine reporting both as stale, so it stays quiet and the machine sleeps
normally.

Look for this in the log:

```
Keyboard hook saw nothing for 31s while Windows saw input 29s ago;
refreshing the hook (#210)
```

If it is stuck anyway, quit from the tray and start VoiceType again.

### It does nothing in one particular window

Windows does not deliver key events from an elevated (administrator) window to
a normal-privilege app. The hotkey will not work while such a window has focus.
Running VoiceType as administrator fixes it, but is not set up by default —
that is a real privilege increase for a background app that reads your
keyboard, and it should be your decision.

---

## Ctrl+Alt+key shortcuts are triggering recordings

Raise `hotkey.engage_delay` (default 0.25 s). Recording only starts once the
combo has been held that long, so a quick shortcut never reaches it.

If your keyboard layout reports right-Alt as AltGr and accented characters are
starting recordings, make sure `hotkey.accept_altgr` is `false` (the default).

---

## It pastes into the wrong place, or not at all

VoiceType waits for you to release Ctrl/Alt/Shift/Win before inserting
(`output.modifier_release_timeout`, 5 s), because a paste sent while Ctrl is
still down becomes a different shortcut.

If an app refuses pasted input, switch to synthesised keystrokes:

```json
{ "output": { "insert_method": "type" } }
```

Or take the text from the clipboard yourself with
`{ "output": { "insert_method": "none" } }`.

---

## Startup and processes

### It did not start when I signed in

The Startup shortcut fires before Wi-Fi is up. faster-whisper contacts Hugging
Face to check the model revision even when the weights are already cached,
which used to fail the whole load with "Server disconnected". VoiceType now
retries with `HF_HUB_OFFLINE=1` and uses what is on disk.

Check the log for `Models ready in …`. If the shortcut is missing entirely,
re-run `install.ps1`.

### Leftover pythonw.exe processes

Should be impossible now. RealtimeSTT transcribes in a spawned child process,
and if VoiceType is killed without running its shutdown path — Task Manager, a
forced sign-out, a crash — that child used to be orphaned. An orphan spins on a
broken pipe, logging a traceback per iteration, and writes without limit: twelve
of them were once found on the development machine, the oldest three days old,
which had between them produced an **8.7 GB** `stdout.log`.

Two things now prevent it:

- The process joins a Windows **job object** marked kill-on-close
  ([`voicetype/winjob.py`](../voicetype/winjob.py)). Children inherit it, and
  when we die — however we die — Windows terminates everything left in it. No
  Python runs, so nothing can be skipped.
- `logs\stdout.log` is capped at 2 MB per process, so even a runaway loop
  cannot fill a disk.

`install.ps1` also clears out any orphans left by an older version.

### Only one instance runs

Enforced with a named mutex, so the Startup shortcut cannot produce duplicates.

---

## Model loading fails

### `EOFError` during startup, app never becomes ready

Do not set `silero_use_onnx` in the recorder options. Passing it **either way**
selects RealtimeSTT's legacy VAD backend, which calls `torch.hub.load()` and
asks on stdin whether you trust the repository. With no console that raises
`EOFError` and the app never finishes loading. Leaving it unset uses the
packaged ONNX model.

### Wrong Python version

RealtimeSTT declares `python_requires >=3.11,<3.13`. Python 3.13 will not
install it. `install.ps1` checks the version before building the environment
and will tell you; if your 3.11/3.12 is somewhere unusual, point at it:

```powershell
.\install.ps1 -Python "C:\Path\To\python.exe"
```

---

## Cloud transcription

### It keeps transcribing locally

`transcription.cloud.fallback_to_local` is `true`, so an unreachable API or a
missing key falls back silently rather than losing your recording. Check the
log for the reason, then confirm the key is found:

```powershell
.venv\Scripts\python.exe tools\check_cloud.py
```

Key lookup order is `api_key` in the config, then `OPENAI_API_KEY`, then
`%APPDATA%\VoiceType\openai.key`.

**An environment variable set after VoiceType started is invisible to it.** The
app launches from a Startup shortcut and only inherits variables that existed at
sign-in. The key file is read per request and has no such problem — use
`.\install.ps1 -SetApiKey`.

### "not supported for this model"

`gpt-4o-transcribe` rejects `languages` and `keywords`. Use `gpt-transcribe`,
which is the default and the only model measured here that handles a sentence
that switches language.
