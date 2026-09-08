r"""Checks a VoiceType installation and says what to fix.

Run this first whenever something is wrong. It is the front door; the deeper
tools (check_mic.py, check_cloud.py) are for when it points you at one.

    .venv\Scripts\python.exe tools\doctor.py

Or just double-click CHECKUP.bat.
"""

import ctypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows consoles are often not UTF-8 (cp1251 here), and a UnicodeEncodeError
# while reporting a problem is a poor way to report a problem.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OK, WARN, FAIL = "[ ok ]", "[warn]", "[FAIL]"

problems = []
warnings = []


def say(mark, label, detail="", fix=""):
    print("{} {:<26} {}".format(mark, label, detail))
    if fix:
        print("       -> {}".format(fix))
    if mark == FAIL:
        problems.append(label)
    elif mark == WARN:
        warnings.append(label)


def check_python():
    major, minor = sys.version_info[:2]
    version = "{}.{}.{}".format(major, minor, sys.version_info[2])
    if (major, minor) in ((3, 11), (3, 12)):
        say(OK, "Python version", version)
    else:
        say(FAIL, "Python version", version + " (need 3.11 or 3.12)",
            "RealtimeSTT does not support this version. Reinstall with "
            "INSTALL.bat, which picks a supported one.")


def check_venv():
    inside = Path(sys.executable).resolve()
    expected = (ROOT / ".venv").resolve()
    if expected in inside.parents:
        say(OK, "Environment", "using .venv")
    else:
        say(WARN, "Environment", "running from {}".format(inside.parent),
            "Not the project's .venv. Fine if deliberate.")


def check_imports():
    missing = []
    for name, package in [
        ("RealtimeSTT", "RealtimeSTT"), ("numpy", "numpy"),
        ("pyaudio", "PyAudio"), ("webrtcvad", "webrtcvad-wheels"),
        ("keyboard", "keyboard"), ("pystray", "pystray"),
        ("PIL", "pillow"), ("httpx", "httpx"),
    ]:
        try:
            __import__(name)
        except Exception:
            missing.append(package)
    if missing:
        say(FAIL, "Dependencies", "missing: " + ", ".join(missing),
            "Run INSTALL.bat again to repair the environment.")
    else:
        say(OK, "Dependencies", "all present")


def check_config():
    try:
        from voicetype import config as config_module
        cfg = config_module.load()
    except Exception as exc:
        say(FAIL, "config.json", str(exc)[:60],
            "Delete config.json; it is rewritten from defaults on next start.")
        return None
    backend = cfg["transcription"]["backend"]
    pinned = cfg["model"]["language"] or "auto-detect"
    say(OK, "Settings", "backend={}  language={}".format(backend, pinned))

    # Worth surfacing: a GPU makes local transcription several times faster,
    # and "auto" silently landing on cpu is the difference between a bigger
    # model being usable and being unusable.
    try:
        from voicetype.hardware import resolve_hardware
        device, compute = resolve_hardware(
            cfg["model"]["device"], cfg["model"]["compute_type"])
        detail = "{} / {} (model {})".format(
            device, compute, cfg["model"]["final"])
        if device == "cpu":
            say(OK, "Local model runs on", detail,
                "No CUDA GPU found. That is fine, just slower.")
        else:
            say(OK, "Local model runs on", detail)
    except Exception as exc:
        say(WARN, "Local model runs on", "could not tell: {}".format(
            str(exc)[:40]))
    return cfg


def check_microphone(cfg):
    try:
        from voicetype.mic import list_input_devices
        devices = list(list_input_devices())
    except Exception as exc:
        say(FAIL, "Microphone", "cannot list devices: {}".format(
            str(exc)[:50]))
        return
    if not devices:
        say(FAIL, "Microphone", "no input devices found",
            "Check Settings > System > Sound > Input.")
        return
    chosen = cfg["audio"]["input_device_index"] if cfg else None
    label = "system default" if chosen is None else "device {}".format(chosen)
    say(OK, "Microphone", "{} device(s), using {}".format(
        len(devices), label),
        "Run tools/check_mic.py while speaking to test the level.")


def check_api_key(cfg):
    if cfg is None:
        return
    try:
        from voicetype.transcribe import CloudBackend
        backend = CloudBackend(cfg)
        has_key = backend.available()
    except Exception as exc:
        say(WARN, "OpenAI key", "could not check: {}".format(str(exc)[:50]))
        return
    wants_cloud = cfg["transcription"]["backend"] == "cloud"
    if has_key:
        say(OK, "OpenAI key", "found")
    elif wants_cloud:
        say(FAIL, "OpenAI key", "missing, but backend is set to cloud",
            "Run INSTALL.bat -SetApiKey, or switch to local in the tray.")
    else:
        say(OK, "OpenAI key", "not set (local backend, so not needed)")


def check_running():
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenMutexW.restype = ctypes.c_void_p
        handle = kernel32.OpenMutexW(
            0x00100000, False, "Global\\VoiceType.SingleInstance")
    except Exception:
        say(WARN, "Running", "could not tell")
        return
    if handle:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        say(OK, "Running", "yes")
    else:
        # The instance mutex is claimed a moment after launch, so running this
        # immediately after starting VoiceType can catch the gap.
        say(WARN, "Running", "not running (or still starting)",
            "If you just started it, wait a few seconds and run this again. "
            "Otherwise start it from the Start Menu.")


def check_autostart():
    startup = Path(os.environ.get("APPDATA", "")) / (
        r"Microsoft\Windows\Start Menu\Programs\Startup\VoiceType.lnk")
    if startup.exists():
        say(OK, "Starts with Windows", "yes")
    else:
        say(WARN, "Starts with Windows", "no shortcut",
            "Run INSTALL.bat to add it.")


def check_logs():
    stdout_log = ROOT / "logs" / "stdout.log"
    if stdout_log.exists():
        size = stdout_log.stat().st_size
        if size > 5_000_000:
            say(WARN, "Logs", "stdout.log is {:.0f} MB".format(size / 1e6),
                "Unexpected. Please open an issue with the last lines.")
            return
    say(OK, "Logs", "normal size")


def main():
    print()
    print("VoiceType check-up")
    print("=" * 62)
    check_python()
    check_venv()
    check_imports()
    cfg = check_config()
    check_microphone(cfg)
    check_api_key(cfg)
    check_running()
    check_autostart()
    check_logs()
    print("=" * 62)

    if problems:
        print("\n{} problem(s) to fix: {}".format(
            len(problems), ", ".join(problems)))
        print("Each one has a '->' line above telling you what to do.")
        return 1
    if warnings:
        print("\nEverything essential works. {} note(s): {}".format(
            len(warnings), ", ".join(warnings)))
        return 0
    print("\nAll good. Hold Ctrl+Alt and talk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
