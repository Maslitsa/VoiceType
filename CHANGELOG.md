# Changelog

Notable changes to VoiceType. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Changed

- One-command install: `irm .../install.ps1 | iex`. The same script installs a
  local copy when run from one, and bootstraps the project first when piped in.
- `transcription.cloud.timeout` lowered from 30 s to 15 s. Measured normal
  range is 1.1–2.6 s and the worst seen in real use was 7.7 s, so past 15 s the
  request is stuck rather than slow. Waiting half a minute before falling
  back to a local model that answers in under two seconds is a bad trade.
- Documented where the wait after you stop talking actually goes, including
  the finding that the cloud backend is not the faster option. Its median is
  comparable to local and its tail is much worse. See
  [docs/accuracy.md](docs/accuracy.md#latency-where-the-wait-actually-goes).

## [1.0.0] - 2026-09-08

First public release.

### Added

- Push-to-talk and hands-free dictation on `Ctrl`+`Alt`, anywhere in Windows.
- Click-through overlay above the taskbar with a live waveform and preview
  text; never takes focus, so the caret stays where it was.
- Local transcription with faster-whisper, or OpenAI `gpt-transcribe`,
  switchable from the tray without a restart.
- Mid-sentence language switching: per-segment language detection locally, and
  a `languages` list for the cloud backend.
- English, Russian and German out of the box; any Whisper language via config.
- Silence guard, so a recording with no speech in it can never produce a
  hallucinated sentence.
- Optional AI cleanup pass, with a length guard that keeps the raw transcript
  if the model rewrites too much.
- Keyboard-hook watchdog, because Windows drops low-level hooks silently after
  sleep and the only symptom is that the hotkey stops working.
- One-command install: `irm .../install.ps1 | iex`. The same script installs a
  local copy when run from one, and downloads the project first when piped in
  with nothing on disk. Re-running it updates in place and keeps `config.json`.
- `INSTALL.bat`, `UNINSTALL.bat` and `CHECKUP.bat`, for anyone who would rather
  not use a terminal at all.
- `tools/doctor.py`, a single check-up that reports what is wrong and what to
  do about it.

### Fixed

- **Orphaned transcription workers.** A force-killed parent runs no cleanup
  code, so RealtimeSTT's child process survived, spun on a broken pipe and
  logged a traceback per iteration. Twelve were found on the development
  machine, the oldest three days old, having written 8.7 GB between them. The
  process now joins a Windows job object marked kill-on-close, so the OS
  terminates children whatever happens to the parent. `logs/stdout.log` is
  also capped at 2 MB per process.
- **Slow fallback when the network is down.** Only a total timeout was set, and
  `getaddrinfo` blocks for as long as Windows wants, measured at 11.6 s before
  the local fallback even started. The connect phase is now bounded at 4 s, and
  a connection failure suppresses cloud attempts for the next 20 s. Measured
  11.6 s to 4.1 s, then 0.00 s.
- **Silent downgrade to the local model.** Falling back is right; doing it
  invisibly is not, since local is much weaker on Russian and German. The
  status line now says `local (offline)` and why.
- **Preview text looked final.** It comes from a much smaller model,
  a different system entirely on the cloud backend, so it regularly disagrees
  with the final text. It is now drawn greyed out, and can be turned off with
  `overlay.show_partial_text`.
- **Quiet microphones failed the silence guard.** WebRTC VAD gets less
  sensitive as input gets quieter; real Russian speech scored 8 against a
  threshold of 12 and was discarded as silence. Default aggressiveness lowered
  to 1, where the same speech scores 23-40 and silence still reaches only 5.
- Clipboard access violation caused by ctypes truncating 64-bit handles.
- Model load failing on a cold boot, when the Startup shortcut fires before
  Wi-Fi is up; it now retries offline against the cached weights.

[1.0.0]: https://github.com/Maslitsa/VoiceType/releases/tag/v1.0.0
