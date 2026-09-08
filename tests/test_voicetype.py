"""Tests for the parts of VoiceType that need no microphone.

Most of this project is Win32 behaviour and live audio, which is awkward to
test in CI. These cover the pure logic underneath: audio maths, the segment
merging, the cloud request shapes, config merging and the capped log stream.

Run them:

    .venv\\Scripts\\python.exe -m unittest discover -s tests -v

They use only the standard library plus numpy, so CI can run them on a machine
with no sound card.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from voicetype import config as config_module          # noqa: E402
from voicetype.transcribe import (                     # noqa: E402
    CloudBackend, _default_prompt, _join_segments, _merge_spans,
    pcm_to_float, pcm_to_wav,
)

RATE = 16000


def tone(seconds, freq=200.0, amplitude=0.4, rate=RATE):
    """A voiced-sounding buffer. Not speech, but not silence either."""
    t = np.arange(int(seconds * rate)) / rate
    wave = np.sin(2 * np.pi * freq * t) * amplitude
    return (wave * 32767).astype(np.int16).tobytes()


def silence(seconds, rate=RATE):
    return np.zeros(int(seconds * rate), dtype=np.int16).tobytes()


class AudioMaths(unittest.TestCase):
    def test_pcm_to_float_round_trips_scale(self):
        pcm = np.array([0, 16384, -16384], dtype=np.int16).tobytes()
        out = pcm_to_float(pcm)
        self.assertEqual(out.dtype, np.float32)
        self.assertAlmostEqual(out[0], 0.0, places=4)
        self.assertAlmostEqual(out[1], 0.5, places=3)
        self.assertAlmostEqual(out[2], -0.5, places=3)

    def test_pcm_to_float_handles_empty(self):
        self.assertEqual(len(pcm_to_float(b"")), 0)

    def test_pcm_to_wav_has_a_riff_header(self):
        wav = pcm_to_wav(tone(0.1), RATE)
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertIn(b"WAVE", wav[:16])
        # 16-bit mono at the rate we asked for.
        self.assertEqual(int.from_bytes(wav[24:28], "little"), RATE)
        self.assertEqual(int.from_bytes(wav[34:36], "little"), 16)


class MergeSpans(unittest.TestCase):
    """Whisper pads every piece to 30s, so segment count is what costs time."""

    def test_caps_the_number_of_segments(self):
        spans = [(i * RATE, i * RATE + RATE) for i in range(10)]
        merged = _merge_spans(spans, RATE, max_segments=3, min_keep=0.0)
        self.assertLessEqual(len(merged), 3)

    def test_absorbs_segments_that_are_too_short(self):
        spans = [(0, RATE * 2), (RATE * 3, RATE * 3 + RATE // 10)]
        merged = _merge_spans(spans, RATE, max_segments=5, min_keep=1.2)
        self.assertEqual(len(merged), 1, "a 0.1s span should not survive")

    def test_keeps_span_order_and_bounds(self):
        spans = [(0, RATE), (RATE * 2, RATE * 3), (RATE * 4, RATE * 5)]
        merged = _merge_spans(spans, RATE, max_segments=2, min_keep=0.0)
        self.assertEqual(merged[0][0], 0)
        self.assertEqual(merged[-1][1], RATE * 5)
        for lo, hi in merged:
            self.assertLess(lo, hi)

    def test_empty_input(self):
        self.assertEqual(_merge_spans([], RATE, 3, 1.2), [])


class JoinSegments(unittest.TestCase):
    def test_drops_trailing_ellipsis_except_on_the_last_piece(self):
        joined = _join_segments(["I said this...", "and then that..."])
        self.assertEqual(joined, "I said this and then that...")

    def test_skips_empty_pieces(self):
        self.assertEqual(_join_segments(["one", "  ", "two"]), "one two")

    def test_no_doubled_spaces(self):
        self.assertNotIn("  ", _join_segments([" one ", " two "]))


class CloudRequestShapes(unittest.TestCase):
    """The fallback ladder must degrade, never drop the languages list.

    Sending `languages` is what buys mid-sentence switching, so a bug that
    silently dropped it would look like a quality regression rather than a
    broken request.
    """

    def setUp(self):
        self.cfg = config_module.load()
        self.cfg["transcription"]["cloud"]["languages"] = ["en", "ru", "de"]
        self.cfg["transcription"]["cloud"]["keywords"] = ["Kubernetes"]
        self.backend = CloudBackend(self.cfg)

    def test_first_shape_sends_the_language_list(self):
        first = self.backend._field_variants("")[0]
        self.assertEqual(first.get("languages[]"), ["en", "ru", "de"])
        self.assertEqual(first.get("keywords[]"), ["Kubernetes"])

    def test_ladder_degrades_to_a_singular_language(self):
        variants = self.backend._field_variants("")
        singular = [v for v in variants if "language" in v]
        self.assertTrue(singular, "no singular-language fallback in the ladder")
        self.assertEqual(singular[0]["language"], "en")

    def test_every_shape_names_the_model(self):
        for fields in self.backend._field_variants(""):
            self.assertIn("model", fields)

    def test_a_pinned_language_overrides_the_list(self):
        first = self.backend._field_variants("de")[0]
        self.assertEqual(first.get("languages[]"), ["de"])


class SteeringPrompt(unittest.TestCase):
    """Accented speech gets transliterated without this.

    A German phrase read in a Russian accent came back as Cyrillic gibberish
    on 6 attempts out of 6 with no prompt, and 0 out of 6 with one. The
    wording is deliberately short: a longer, more explicit version failed all
    6, so this is not a knob to elaborate on casually.
    """

    def test_names_every_configured_language(self):
        prompt = _default_prompt(["en", "ru", "de", "kk"])
        for name in ("English", "Russian", "German", "Kazakh"):
            self.assertIn(name, prompt)

    def test_reads_as_a_sentence(self):
        self.assertEqual(_default_prompt(["en", "ru", "de"]),
                         "The speaker mixes English, Russian and German.")

    def test_no_prompt_when_there_is_nothing_to_mix(self):
        self.assertEqual(_default_prompt(["en"]), "")
        self.assertEqual(_default_prompt([]), "")

    def test_unknown_codes_still_produce_something(self):
        self.assertIn("zz", _default_prompt(["en", "zz"]))

    def test_a_configured_prompt_wins(self):
        cfg = config_module.load()
        cfg["transcription"]["cloud"]["prompt"] = "my own wording"
        fields = CloudBackend(cfg)._field_variants("")[0]
        self.assertEqual(fields.get("prompt"), "my own wording")

    def test_generated_prompt_is_used_when_none_is_set(self):
        cfg = config_module.load()
        cfg["transcription"]["cloud"]["prompt"] = ""
        cfg["transcription"]["cloud"]["languages"] = ["en", "de"]
        fields = CloudBackend(cfg)._field_variants("")[0]
        self.assertEqual(fields.get("prompt"),
                         "The speaker mixes English and German.")


class ConfigMerge(unittest.TestCase):
    def test_user_values_win_but_defaults_survive(self):
        merged = config_module._deep_merge(
            config_module.DEFAULTS, {"model": {"final": "small"}}
        )
        self.assertEqual(merged["model"]["final"], "small")
        self.assertEqual(
            merged["model"]["realtime"], config_module.DEFAULTS["model"]["realtime"]
        )

    def test_merge_does_not_mutate_the_defaults(self):
        before = config_module.DEFAULTS["model"]["final"]
        config_module._deep_merge(config_module.DEFAULTS,
                                  {"model": {"final": "large-v3-turbo"}})
        self.assertEqual(config_module.DEFAULTS["model"]["final"], before)

    def test_defaults_that_were_chosen_by_measurement(self):
        # These have measurements behind them in docs/accuracy.md. If you are
        # changing one, change it here too and say why in the pull request.
        rec = config_module.DEFAULTS["recording"]
        self.assertEqual(rec["vad_aggressiveness"], 1)
        self.assertEqual(rec["min_speech_run"], 12)
        self.assertTrue(rec["normalize_for_transcription"])
        self.assertIsNone(config_module.DEFAULTS["model"]["initial_prompt"])


class HardwareResolution(unittest.TestCase):
    def test_explicit_values_are_left_alone(self):
        from voicetype.hardware import resolve_hardware
        self.assertEqual(resolve_hardware("cpu", "int8"), ("cpu", "int8"))

    def test_auto_compute_type_follows_the_device(self):
        from voicetype.hardware import resolve_hardware
        self.assertEqual(resolve_hardware("cuda", "auto")[1], "float16")
        self.assertEqual(resolve_hardware("cpu", "auto")[1], "int8")

    def test_auto_device_resolves_to_something_usable(self):
        from voicetype.hardware import resolve_hardware
        device, compute = resolve_hardware("auto", "auto")
        self.assertIn(device, ("cpu", "cuda"))
        self.assertIn(compute, ("int8", "float16"))


class CappedLogStream(unittest.TestCase):
    """A runaway dependency once wrote 8.7 GB here. It must not happen twice."""

    def _stream_class(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voicetype_run", ROOT / "run.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._CappedStream

    def test_stops_writing_at_the_limit(self):
        capped = self._stream_class()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.log"
            stream = capped(path, "w", 1000)
            for i in range(500):
                stream.write("a traceback line {}\n".format(i))
            stream.flush()
            stream.close()
            self.assertLess(path.stat().st_size, 1500)
            self.assertIn("limit", path.read_text(encoding="utf-8"))

    def test_write_reports_the_full_length_even_when_dropping(self):
        capped = self._stream_class()
        with tempfile.TemporaryDirectory() as tmp:
            stream = capped(Path(tmp) / "out.log", "w", 10)
            stream.write("x" * 50)
            # print() checks the return value; lying about it breaks callers.
            self.assertEqual(stream.write("y" * 30), 30)
            stream.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
