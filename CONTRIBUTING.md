# Contributing

Thanks for looking. This started as a tool to solve one problem — dictation
that does not fall apart when you switch language mid-sentence — so the most
useful contributions are usually reports from setups I cannot test.

## Especially welcome

- **Other language pairs.** Everything here was tuned against English, Russian
  and German. If your pair behaves differently, that is worth an issue, ideally
  with what you said and what came out.
- **Different microphones.** The voice-activity thresholds are calibrated
  against one quiet laptop microphone. `tools/check_mic.py` prints the numbers
  that matter; if the defaults are wrong for your hardware, say so.
- **GPU results.** Everything measured in [docs/accuracy.md](docs/accuracy.md)
  is CPU-only. Numbers from a CUDA machine would make that document much more
  useful.
- **Windows 11 quirks.** Developed on Windows 10.

## Reporting a bug

Include:

1. What you did and what happened.
2. The relevant part of `logs\voicetype.log`.
3. Windows version, Python version, and whether you are on the local or cloud
   backend.

If it is about recognition quality, `tools\check_mic.py` and
`tools\check_cloud.py` output is worth far more than a description.

**Never paste an API key**, including in a log excerpt. Redact it.

## Development setup

```powershell
git clone https://github.com/Maslitsa/VoiceType.git
cd VoiceType
powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoStart -NoAutostart
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`-NoStart -NoAutostart` builds the environment without registering it to run at
sign-in, which is usually what you want while working on it.

Run it with a console so you can watch it:

```powershell
.venv\Scripts\python.exe run.py
```

Run it as it actually ships — invisible:

```powershell
.venv\Scripts\pythonw.exe run.py
```

## House style

The code is commented for *why*, not *what*. Several defaults in this project
look arbitrary and are not — they are the result of a measurement, and the
comment explaining which one is the reason the next person does not undo it.
`voicetype/config.py` is the clearest example. Please keep that up.

Match the surrounding code: 4 spaces, ~79 columns, standard library first in
imports, docstrings on anything non-obvious.

## Before opening a pull request

```powershell
.venv\Scripts\python.exe -m compileall -q voicetype run.py tools
```

There is no test suite yet — most of this is Win32 behaviour and live audio,
which is awkward to test in CI. If you add something that *can* be tested
without hardware, a test is very welcome.

If you change a default that was chosen by measurement, please include the
measurement.
