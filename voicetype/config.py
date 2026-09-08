"""Configuration loading for VoiceType.

Settings live in config.json next to the project root so they survive
reinstalls of the environment.
"""

import copy
import json
import logging
from pathlib import Path

logger = logging.getLogger("voicetype.config")

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"
LOG_DIR = ROOT_DIR / "logs"

DEFAULTS = {
    "model": {
        # Multilingual models: handle English and Russian, auto-detected.
        "final": "base",
        "realtime": "tiny",
        # "" means auto-detect per utterance. Set "en", "ru" or "de" to pin it.
        "language": "",
        # What the tray's Language submenu offers. Whisper knows ~99
        # languages, so add any you need: "French": "fr", "Spanish": "es".
        "language_menu": {
            "Auto-detect": "",
            "English": "en",
            "Russian": "ru",
            "German": "de",
            "Kazakh": "kk",
        },
        # "auto" picks cuda when an NVIDIA card is actually usable and cpu
        # otherwise. This used to be hardcoded to cpu, which silently wasted a
        # GPU on the machines that have one, and Whisper on a GPU is several
        # times faster. Detecting a card is not the same as being able to use
        # it (old driver, missing cuDNN), so a cuda load that fails falls back
        # to cpu instead of refusing to start. Force it with "cpu" or "cuda".
        "device": "auto",
        # "auto" means float16 on a GPU and int8 on a CPU. int8 is what makes
        # CPU transcription bearable; float16 is the standard GPU choice.
        "compute_type": "auto",
        # 5 is faster-whisper's default and worth keeping. Greedy decoding
        # (beam_size 1) was measured here at 1.50-1.54s against 1.61-1.73s,
        # so it buys about a tenth of a second, and produced identical text on
        # clean clips, which means the only place it can differ is the hard
        # audio where the beam search is actually earning its keep.
        "beam_size": 5,
        "beam_size_realtime": 3,
        # Where faster-whisper caches the model weights. null = default HF cache.
        "download_root": None,
        # Whisper's equivalent of a vocabulary hint: put your own names and
        # jargon here and the decoder is likelier to spell them right. Read
        # once at startup, so a change needs a restart.
        #
        # Empty on purpose. A bilingual Russian/English hint was tried here to
        # coax Whisper into code-switching, and it measurably made things
        # worse: on a German sentence ending in English it silently dropped
        # the entire English half, and it turned "Donnerstag" into
        # "Dunnestag". A prompt in one language biases everything you say
        # toward that language, so leave it empty unless you dictate in a
        # single language and want specific vocabulary respected.
        "initial_prompt": None,
    },
    "transcription": {
        # "local" runs on your CPU. "cloud" uses OpenAI's speech-to-text,
        # the same family ChatGPT's voice input uses.
        "backend": "local",
        # Local only: split the recording at pauses and detect the language of
        # each piece, so a sentence that switches language is not forced into
        # one.
        #
        # Off by default. It genuinely fixes English->Russian, which is the
        # one direction the single-pass decode gets wrong. But a segment is
        # transcribed without the surrounding context, and that costs accuracy
        # everywhere else: "bis morgen früh schicken" came back as "bis morgen
        # frischicken", sentence-final punctuation goes missing, and it runs
        # ~1.7x slower. Russian->English and German->English already come out
        # right in a single pass. Turn this on only if you regularly start a
        # sentence in English and finish it in another language, and prefer
        # the cloud backend, which handles all of this properly.
        "per_segment_language": False,
        "segment_min_pause": 0.35,
        # Whisper pads every piece to a 30-second window, so each segment is
        # a full extra pass. These two keep a long dictation with many natural
        # pauses from turning into a dozen of them.
        "segment_max": 3,
        "segment_min_length": 1.2,
        "cloud": {
            # "gpt-transcribe" is the current model and the only one measured
            # here that transcribes a sentence which switches language. Tested
            # on this machine with the same mixed English/Russian clip:
            #
            #   gpt-transcribe          both halves, each in its own script
            #   gpt-4o-transcribe       dropped the English half entirely
            #   gpt-4o-mini-transcribe  dropped the English half entirely
            #   whisper-1               translated the Russian into English
            #
            # gpt-4o-transcribe also rejects the `languages` and `keywords`
            # fields outright ("not supported for this model").
            "model": "gpt-transcribe",
            # Key lookup order: api_key, then this environment variable, then
            # api_key_file. Prefer the file: VoiceType starts from a Startup
            # shortcut and only inherits environment variables that already
            # existed when it launched, so a newly set variable is invisible
            # until you sign in again. The file is read per request.
            #
            # It deliberately lives outside the project folder. A key in
            # config.json is one 'git add -f', or one cloud-sync folder,
            # away from leaking.
            "api_key_env": "OPENAI_API_KEY",
            "api_key": "",
            "api_key_file": "%APPDATA%\\VoiceType\\openai.key",
            # The languages you actually speak. This is not decoration: it is
            # the setting that buys mid-sentence switching. On a Russian
            # sentence ending in English, gpt-transcribe dropped the English
            # half with no list and with ["ru", "en"], but transcribed both
            # halves with the full ["en", "ru", "de"]. Keep every language you
            # use in here, and keep "en" first.
            #
            # It copes with more than you might expect. A single 21.8s
            # utterance that went English -> German -> Russian -> Kazakh came
            # back correct in all four, across three scripts, in 3.4s. Kazakh
            # was not even in the list at the time, which suggests the list
            # steers the model rather than restricting it.
            "languages": ["en", "ru", "de", "kk"],
            # Literal terms you expect it to hear: names, jargon, product
            # names. e.g. ["Kubernetes", "RealtimeSTT", "Grafana"].
            "keywords": [],
            # Free-form description of the recording, to steer style.
            "prompt": "",
            # 15, not 30. Measured on this machine the request takes 1.1-2.6s
            # for ordinary clips, and the worst seen in real use was 7.7s,
            # so anything past 15s is stuck rather than slow. Waiting the old 30s and
            # only then falling back to a local model that takes under two
            # seconds is a bad trade: it makes a network problem cost half a
            # minute of staring at the pill.
            "timeout": 15,
            # If the API errors or times out, transcribe locally instead of
            # losing what you just said.
            "fallback_to_local": True,
        },
    },
    "cleanup": {
        # Tidy the transcript with a small chat model: drop filler words,
        # fix punctuation. Needs the same API key. Adds about a second.
        "enabled": False,
        "model": "gpt-4o-mini",
        "instructions": "",
        "timeout": 20,
    },
    "hotkey": {
        # Hold Ctrl+Alt this long before recording engages. Also what stops
        # ordinary Ctrl+Alt+<key> shortcuts and AltGr from triggering us.
        "engage_delay": 0.25,
        # Released before this (measured from first press) = tap -> latched
        # recording. Held longer = push-to-talk, stops on release.
        "tap_max": 0.7,
        # Right Alt reports as "alt gr" on some layouts. Off by default so
        # typing accented characters never starts a recording.
        "accept_altgr": False,
        # Any other key pressed during the combo cancels the recording.
        "cancel_on_other_key": True,
        # How often to check the keyboard hook is still alive. Windows drops
        # low-level hooks silently, after a sleep or if a callback ever
        # overruns its timeout, and the only symptom is that Ctrl+Alt stops
        # working while the app carries on looking healthy. When nothing has
        # been typed for this long we inject a key bound to nothing and check
        # our own hook sees it, reinstalling if it does not. 0 disables.
        "health_check_seconds": 20,
        # Moving the mouse also counts as input to Windows but never reaches a
        # keyboard hook, so the check above cannot tell a dead hook from an
        # idle one. This caps how often the hook is actually replaced, which
        # turns that ambiguity into a harmless refresh when you return to the
        # machine instead of constant churn while you use the mouse.
        "min_reinstall_seconds": 60,
    },
    "recording": {
        # In latched mode, stop automatically after this much silence.
        # 0 disables auto-stop (then only a second Ctrl+Alt tap stops it).
        "latch_silence_timeout": 2.5,
        # Hard cap so a stuck key can never record forever.
        "max_seconds": 300,
        # Discard recordings shorter than this (accidental taps).
        "min_seconds": 0.35,
        # Whisper invents plausible sentences out of silence, so a recording
        # with no real speech in it must never reach the clipboard. We run
        # WebRTC VAD over the captured audio and require an unbroken run of
        # this many 20 ms frames. 12 frames = 240 ms.
        #
        # Measured on this laptop: real speech gives runs of 125-178 frames,
        # while four seconds of room noise peaks at 4. Neither loudness nor a
        # total frame count separates them. The idle noise floor already
        # sits near 0.48 of full scale and scatters ~11% false positives.
        # Run length does, and it does not depend on how long you spoke.
        "min_speech_run": 12,
        # WebRTC VAD aggressiveness, 0 (permissive) to 3 (strict).
        #
        # 1, not 2. WebRTC VAD gets less sensitive as the input gets quieter,
        # and this laptop's microphone records very quietly. Measured on real
        # speech captured through it, longest run of speech frames:
        #
        #                       aggr=2      aggr=1
        #   English speech        19          40
        #   Russian speech         8          23     <- 8 fails the test below
        #   silence                4           5
        #
        # At 2 a real Russian sentence scored below the threshold and was
        # thrown away as silence. At 1 both languages clear it comfortably and
        # silence still does not.
        "vad_aggressiveness": 1,
        # Boost quiet recordings to this peak before transcribing. Whisper and
        # the API both degrade on faint audio, Russian first, and this mic
        # peaks around 0.08 where 0.9 is available.
        #
        # Applied to the transcription audio ONLY, never to the speech test
        # above. Normalising before the VAD would scale the noise floor up
        # with everything else: silence then reads as 300 speech frames out of
        # 300, the silence guard never fires, and Whisper is free to invent a
        # sentence out of room hiss again.
        "normalize_for_transcription": True,
        "normalize_target_peak": 0.9,
        # Do not amplify beyond this, or near-silence becomes loud noise.
        "normalize_max_gain": 8.0,
        "silero_sensitivity": 0.4,
        "webrtc_sensitivity": 3,
    },
    "audio": {
        "sample_rate": 16000,
        "chunk_size": 512,
        # null = system default microphone.
        "input_device_index": None,
    },
    "output": {
        # Always put the transcript on the clipboard.
        "copy_to_clipboard": True,
        # "paste" = Ctrl+V into the focused window, "type" = synthesize
        # keystrokes, "none" = clipboard only.
        "insert_method": "paste",
        "append_space": True,
        # Wait for you to let go of Ctrl/Alt/Shift/Win before inserting.
        "modifier_release_timeout": 5.0,
    },
    "overlay": {
        "width": 620,
        "height": 58,
        # Gap between the pill and the top of the taskbar.
        "margin_bottom": 14,
        "corner_radius": 16,
        "opacity": 0.96,
        "hide_delay": 1.6,
        # Show the live preview text while you speak. It comes from
        # model.realtime (tiny by default), which is a far weaker model than
        # whatever produces the final transcript. With the cloud backend
        # they are different systems entirely, so the preview regularly says
        # something quite different from what you end up with. It is drawn in
        # the muted colour to make clear it is not the answer yet. Set false
        # to show only the waveform.
        "show_partial_text": True,
        "bars": 34,
        "font_family": "Segoe UI",
        "font_size": 11,
        "colors": {
            "background": "#101114",
            "border": "#2c3038",
            "text": "#f2f3f5",
            "muted": "#8b8f98",
            "recording": "#ff4d4f",
            "transcribing": "#f5a623",
            "done": "#34c759",
            "error": "#ff6b6b",
        },
    },
    "log_level": "INFO",
}


def _deep_merge(base, override):
    """Returns base updated with override, recursing into nested dicts."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def save(cfg):
    """Writes the full config back to disk, keeping user edits readable."""
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True
    except OSError as exc:
        logger.warning("Could not save config.json: %s", exc)
        return False


def load():
    """Loads config.json merged over the defaults, writing it if absent."""
    user_config = {}
    if CONFIG_PATH.exists():
        try:
            user_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable config.json: %s", exc)
    else:
        try:
            CONFIG_PATH.write_text(
                json.dumps(DEFAULTS, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Could not write default config.json: %s", exc)
    return _deep_merge(DEFAULTS, user_config)
