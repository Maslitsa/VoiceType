# Contributing

Small changes are easiest to review, and you do not need to write code to help.

## Helping without writing code

These are the most useful things anyone can do, and none of them need a
development setup.

**Tell me how it did with your language.** Everything here was tuned against
English, Russian and German, spoken by one person into one quiet laptop
microphone. That is a narrow sample. If your language or your accent behaves
differently, that is new information. Open a
[language report](https://github.com/Maslitsa/VoiceType/issues/new?template=language_report.yml)
with what you said and what came out. Good results are worth reporting too.

**Run the check-up and paste the output.** If something is broken,
`CHECKUP.bat` prints everything I would otherwise have to ask you for.

**Tell me your microphone is different.** The voice-activity thresholds are
calibrated against one quiet microphone. `tools/check_mic.py` prints the
numbers that matter. If the defaults are wrong for your hardware, say so.

**Numbers from a GPU.** Every measurement in
[docs/accuracy.md](docs/accuracy.md) is CPU-only, which shapes the defaults a
lot. See [issue #5](https://github.com/Maslitsa/VoiceType/issues/5).

Looking for somewhere to start? The
[good first issue](https://github.com/Maslitsa/VoiceType/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
label is where I put things that are self-contained.

## Development setup

```powershell
git clone https://github.com/Maslitsa/VoiceType.git
cd VoiceType
powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoStart -NoAutostart
```

`-NoStart -NoAutostart` builds the environment without registering VoiceType to
run at sign-in, which is usually what you want while working on it.

Run it with a console so you can watch it:

```powershell
.venv\Scripts\python.exe run.py
```

Run it the way it ships, with no window:

```powershell
.venv\Scripts\pythonw.exe run.py
```

Logs are in `logs\voicetype.log`.

## Before opening a pull request

```powershell
.venv\Scripts\python.exe -m compileall -q voicetype run.py tools
```

That is the whole check. CI runs the same thing on Python 3.11 and 3.12, plus
a scan for committed API keys.

There is no test suite. Most of this is Win32 behaviour and live audio, which
is awkward to test in CI. If you add something that can be tested without
hardware, a test is welcome but not required.

## Two house rules

**Comments explain why, not what.** Several defaults here look arbitrary and
are not. They came from a measurement, and the comment saying which one is the
reason nobody undoes it later. `voicetype/config.py` is the clearest example.

**If you change a default that was chosen by measurement, include a
measurement.** Otherwise the next person will change it back.

Match the surrounding code otherwise: 4 spaces, about 79 columns, standard
library imports first.

## Reporting a bug

Include what you did, what happened, the relevant part of
`logs\voicetype.log`, and your Windows and Python versions. The
[bug report template](https://github.com/Maslitsa/VoiceType/issues/new?template=bug_report.yml)
asks for exactly this.

Never paste an API key, including inside a log excerpt.
