# Architecture

## Layout

```
VoiceType\
├─ run.py                  entry point; launch with pythonw.exe
├─ install.ps1             environment, autostart, key setup, uninstall
├─ requirements.txt
├─ config.json             created on first run, gitignored
├─ logs\                   voicetype.log (rotating), stdout.log (capped)
├─ tools\
│  ├─ check_mic.py         is your microphone good enough?
│  └─ check_cloud.py       what does OpenAI return for known sentences?
├─ docs\
└─ voicetype\
   ├─ app.py               controller and state machine
   ├─ engine.py            RealtimeSTT wrapper: capture, VAD, live preview
   ├─ transcribe.py        local/cloud backends, per-segment language
   ├─ cleanup.py           optional LLM tidy-up pass
   ├─ hotkey.py            Ctrl+Alt detection and the hook watchdog
   ├─ mic.py               PyAudio capture and level metering
   ├─ overlay.py           the pill above the taskbar
   ├─ output.py            clipboard and paste
   ├─ tray.py              tray icon
   ├─ winjob.py            job object that stops orphaned workers
   └─ config.py            defaults and config.json loading
```

## Threads

| Thread | Job |
| --- | --- |
| main | Tk event loop; owns the overlay and drains the UI queue |
| keyboard | the low-level hook; only ever hands work to other threads |
| mic-read | PyAudio reads, feeding the recorder and the level meter |
| engine-* | model load and final transcription |
| tray | the pystray message loop |
| hotkey-watchdog | checks the keyboard hook is still installed |

Everything that touches the overlay goes through `App.post()` so it runs on the
Tk thread.

## Flow

Holding Ctrl+Alt for 0.25s shows the overlay and opens the microphone. Each
chunk of audio goes two places at once: to RealtimeSTT, which produces the live
preview text, and into a buffer the app keeps for itself.

When the recording ends, by release, a second tap, or silence, the app runs a
voice activity check over the raw buffer. If there is no real speech it stops
there and shows "Nothing heard". Otherwise it boosts a quiet recording, sends
it to whichever backend is selected, optionally runs the cleanup pass, then
copies the text and pastes it into the focused window.

RealtimeSTT is driven with `use_microphone=False`, so it only ever sees audio
the app feeds it and can never start listening on its own. It supplies capture,
the voice-activity detection that ends a hands-free recording, and the live
preview. The **final** transcript is produced separately from the app's own copy
of the audio. That separation is what makes the local/cloud switch and
per-segment language detection possible without a second copy of the weights.

---

## Windows-specific decisions

These are the things that were not obvious, and the reasons they are the way
they are. Most cost a bug to learn.

### Ctrl+Alt cannot use RegisterHotKey

It is a modifier-only combo, so it needs a `WH_KEYBOARD_LL` hook and a state
machine over it. The 0.25 s engage delay is what separates dictation from an
ordinary `Ctrl`+`Alt`+`key` shortcut.

### Windows silently removes low-level hooks

No error, no crash. The app keeps running and looks healthy while the hotkey
is dead. There is no API to ask whether a hook is alive, so the watchdog infers
it: Windows tracks when it last saw *any* input (`GetLastInputInfo`), and we
track when our hook last saw one. If the system has had input we have not,
events are going somewhere we are not.

An earlier version injected a key and checked whether the hook observed it.
That worked, but `SendInput` resets the system idle timer, so probing on a
schedule would have quietly stopped the laptop from ever sleeping. The passive
check has no such side effect.

Mouse movement counts as input to Windows but never reaches a keyboard hook, so
the check cannot distinguish a dead hook from mouse-only use. A 60 s floor on
reinstalls turns that ambiguity into a harmless refresh when you come back to
the machine, instead of constant churn while you use the mouse.

### The overlay must not take focus

`WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED`. It
never steals focus, is click-through, and stays out of `Alt`+`Tab`, so the
caret stays exactly where you left it and the paste lands in the right window.
The ex-styles are re-applied after the first map, because the frame window only
reliably exists once the window has been shown.

### ctypes needs explicit argtypes

Handles are 64-bit and ctypes defaults to a 32-bit int, which silently
truncates them. This produced an access violation in the clipboard path that
looked like a random crash. Every Win32 call in this project declares
`argtypes` and `restype`.

### pythonw.exe has no stdout

`sys.stdout` and `sys.stderr` are `None`, so any stray `print()` in a
dependency raises. `run.py` points them at a log file at *import* time, not in
`main()`, because multiprocessing re-imports the entry module in spawned
children and they need it too.

### A killed parent orphans its children

This is the one that did real damage. RealtimeSTT transcribes in a spawned
child process. `TerminateProcess` runs no `atexit` handlers, no `finally`
blocks and no signal handlers. So when VoiceType was force-killed, the child
survived, its parent pipe broke, and RealtimeSTT's poll loop logged a
`BrokenPipeError` traceback and immediately retried. Forever.

Twelve of those were found running on the development machine, the oldest three
days old, having written an **8.7 GB** `stdout.log` between them.

No Python can fix this, because no Python runs. So the cleanup belongs to the
operating system: [`winjob.py`](../voicetype/winjob.py) puts the process in a
job object marked `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Children inherit the
job, and when the last handle to it closes, which Windows does for us when the
process dies by any means, everything left in the job is terminated.

`logs\stdout.log` is also capped at 2 MB per process, as a backstop.

### Normalising audio before a VAD destroys it

Boosting a quiet recording scales the noise floor up with everything else.
Silence at peak 0.044, normalised, measures **300 speech frames out of 300**.
The boost is applied to the transcription copy only; the speech guard always
sees raw audio.

### One instance only

A named mutex (`Global\VoiceType.SingleInstance`), so the Startup shortcut
cannot produce duplicates.

---

## Privacy

The microphone is opened **only while you are recording**, so Windows' "app is
using your microphone" indicator is an honest signal. Nothing is captured
otherwise.

With the default local backend, no audio and no text ever leaves the machine.
With the cloud backend, the recorded audio is uploaded to OpenAI when you
dictate, and only then.

The API key is stored in `%APPDATA%\VoiceType\openai.key`, outside the project
folder, with inheritance broken so only your account can read it. It is
deliberately not in `config.json`: a file inside the project is one `git add -f`
or one cloud-sync away from leaking.
