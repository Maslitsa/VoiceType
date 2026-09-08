# Configuration

Settings live in `config.json` in the project root. It is written on first run
from the defaults in [`voicetype/config.py`](../voicetype/config.py), which
carries a comment explaining every value and why it is what it is. That file
is the real reference.

Open it from **tray → Edit settings**. Most changes need a restart.

`config.json` is deliberately **not** tracked by git: it has an `api_key` field,
and untracked is the safest default for a file that can hold a secret.

---

## The settings worth knowing about

### Hotkey

| Setting | Default | Meaning |
| --- | --- | --- |
| `hotkey.engage_delay` | `0.25` | How long `Ctrl`+`Alt` must be held before recording starts. This is what stops ordinary `Ctrl`+`Alt`+`key` shortcuts from triggering it. Raise it if a shortcut you use still trips it. |
| `hotkey.tap_max` | `0.7` | Release before this and it counts as a tap (hands-free latch) rather than push-to-talk. |
| `hotkey.accept_altgr` | `false` | Whether right-Alt / AltGr counts as Alt. Off, so typing accented characters never starts a recording. |
| `hotkey.cancel_on_other_key` | `true` | Any non-modifier key cancels the recording. |
| `hotkey.health_check_seconds` | `20` | How often to check the keyboard hook is still alive. `0` disables the watchdog. See [troubleshooting](troubleshooting.md#the-hotkey-stopped-working). |
| `hotkey.min_reinstall_seconds` | `60` | Floor on how often the hook may actually be replaced. |

### Recording

| Setting | Default | Meaning |
| --- | --- | --- |
| `recording.latch_silence_timeout` | `2.5` | Silence that ends a hands-free recording. `0` disables auto-stop, so only a second tap finishes it. |
| `recording.max_seconds` | `300` | Hard cap, so a stuck key can never record forever. |
| `recording.min_seconds` | `0.35` | Recordings shorter than this are discarded as accidental taps. |
| `recording.min_speech_run` | `12` | Consecutive 20 ms frames of detected speech required before a transcript is accepted. 12 = 240 ms. Raise it if noise gets through; lower it if short words are dropped. |
| `recording.vad_aggressiveness` | `1` | WebRTC VAD strictness, 0 (permissive) to 3 (strict). **This interacts with your microphone level.** see [accuracy](accuracy.md#microphone-level-matters-more-than-you-would-think). |
| `recording.normalize_for_transcription` | `true` | Boost quiet recordings before transcribing. Applied to the transcription audio only, never to the speech guard. |
| `recording.normalize_target_peak` | `0.9` | Boost quiet audio up to this peak. |
| `recording.normalize_max_gain` | `8.0` | Never amplify by more than this, or near-silence becomes loud noise. |

### Models

| Setting | Default | Meaning |
| --- | --- | --- |
| `model.final` | `"base"` | Model for the real transcript: `tiny` / `base` / `small` / `medium` / `large-v3-turbo`. Bigger is slower and, for language switching, [often worse](accuracy.md#bigger-is-not-better). |
| `model.realtime` | `"tiny"` | Model for the live preview text. Keep it small. |
| `model.language` | `""` | `""` auto-detects per utterance. Set `"en"`, `"ru"`, `"de"` to pin. Only pin when the whole sentence is in that language. |
| `model.language_menu` | en/ru/de | What the tray's Language submenu offers. Whisper knows ~99 languages, so `"French": "fr"` is all it takes to add one. |
| `model.device` | `"cpu"` | Set `"cuda"` if you have an NVIDIA GPU. |
| `model.compute_type` | `"int8"` | `int8` is the fast CPU default. `float32` is marginally better and much slower. |
| `model.initial_prompt` | `null` | Whisper's vocabulary hint, for names and jargon. **Empty on purpose**, see the warning below. |

> [!WARNING]
> `initial_prompt` biases everything you say toward the prompt's language. A
> bilingual Russian/English hint was tried here to coax Whisper into
> code-switching and measurably made things worse: on a German sentence ending
> in English it silently dropped the entire English half, and it turned
> "Donnerstag" into "Dunnestag". Use it only if you dictate in one language and
> want specific vocabulary respected.

### Transcription backend

| Setting | Default | Meaning |
| --- | --- | --- |
| `transcription.backend` | `"local"` | `local` or `cloud`. Same as the tray menu. |
| `transcription.per_segment_language` | `false` | Split at pauses and detect the language of each piece. See [accuracy](accuracy.md#switching-language-mid-sentence). |
| `transcription.segment_min_pause` | `0.35` | How long a gap must be to split on. |
| `transcription.segment_max` | `3` | Cap on segments per recording. Whisper pads every piece to a 30-second window, so each segment is a whole extra pass. |
| `transcription.segment_min_length` | `1.2` | Segments shorter than this are merged into a neighbour. |

### Cloud

| Setting | Default | Meaning |
| --- | --- | --- |
| `transcription.cloud.model` | `"gpt-transcribe"` | The only model measured here that transcribes a sentence which switches language. See [accuracy](accuracy.md#which-cloud-model). |
| `transcription.cloud.languages` | `["en","ru","de"]` | **Load-bearing.** The list is what buys mid-sentence switching. Keep every language you use in it. |
| `transcription.cloud.keywords` | `[]` | Literal terms you expect it to hear: names, jargon, product names. |
| `transcription.cloud.api_key_file` | `%APPDATA%\VoiceType\openai.key` | Read per request, so a new key takes effect immediately. |
| `transcription.cloud.api_key_env` | `OPENAI_API_KEY` | Environment variable fallback. |
| `transcription.cloud.api_key` | `""` | Inline key. **Avoid**, see below. |
| `transcription.cloud.timeout` | `30` | Seconds. |
| `transcription.cloud.fallback_to_local` | `true` | Transcribe locally if the API fails, rather than losing the recording. |

Key lookup order is `api_key`, then the environment variable, then the file.
**Prefer the file.** VoiceType starts from a Startup shortcut and only inherits
environment variables that already existed when it launched, so a newly set
variable stays invisible until your next sign-in. The file has no such problem,
lives outside the project folder, and cannot be committed by accident.

> [!CAUTION]
> Do not put a real key in `transcription.cloud.api_key`. `config.json` is
> gitignored, but a file in the project folder is one `git add -f` or one cloud
> sync away from leaking. Use `.\install.ps1 -SetApiKey`.

### Cleanup

| Setting | Default | Meaning |
| --- | --- | --- |
| `cleanup.enabled` | `false` | Send the transcript through a small chat model to drop filler words and fix punctuation. Adds about a second. |
| `cleanup.model` | `"gpt-4o-mini"` | |
| `cleanup.instructions` | `""` | Extra instructions appended to the prompt. |

It is deliberately conservative: the prompt forbids translating or
paraphrasing, and if the result differs in length by more than about half the
original, the raw transcript is kept instead. A misbehaving cleanup can never
silently rewrite what you said.

### Output

| Setting | Default | Meaning |
| --- | --- | --- |
| `output.copy_to_clipboard` | `true` | Always put the transcript on the clipboard. |
| `output.insert_method` | `"paste"` | `paste` (Ctrl+V), `type` (synthesised keystrokes), or `none` for clipboard only. |
| `output.append_space` | `true` | Trailing space, which helps when dictating several times in a row. |
| `output.modifier_release_timeout` | `5.0` | Wait this long for Ctrl/Alt/Shift/Win to be released before inserting. |

### Overlay

`overlay.*` controls the pill: `width`, `height`, `margin_bottom` (gap above
the taskbar), `corner_radius`, `opacity`, `hide_delay`, `bars` (waveform bar
count), `font_family`, `font_size`, and a `colors` map for each state.

| Setting | Default | Meaning |
| --- | --- | --- |
| `overlay.show_partial_text` | `true` | Show the live preview text while you speak. It comes from `model.realtime`, a much weaker model than the one producing the final text, so it often disagrees. It is drawn greyed out for that reason. Set `false` for waveform only. |

---

## Recipes

**English only, as accurate as possible.** The English-only models beat the
multilingual ones at the same size:

```json
{ "model": { "language": "en", "final": "base.en", "realtime": "tiny.en" } }
```

**You have an NVIDIA GPU.** Local transcription becomes far faster, and a
bigger model becomes practical:

```json
{ "model": { "device": "cuda", "compute_type": "float16", "final": "small" } }
```

**Clipboard only, never type anything.**

```json
{ "output": { "insert_method": "none" } }
```

**Add a language.** Whisper knows about 99:

```json
{ "model": { "language_menu": { "Auto-detect": "", "English": "en", "French": "fr" } },
  "transcription": { "cloud": { "languages": ["en", "fr"] } } }
```
