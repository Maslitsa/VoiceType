"""System tray icon.

The app has no console and no window of its own, so this is the only place
you can see that it is running, pause it, or quit it.
"""

import logging
import os
import subprocess
import threading

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger("voicetype.tray")

_IDLE = (233, 236, 241)
_BUSY = (255, 77, 79)
_PAUSED = (120, 124, 132)


def _make_icon(color):
    """Draws a simple microphone glyph at tray resolution."""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Capsule body.
    draw.rounded_rectangle((24, 10, 40, 38), radius=8, fill=color)
    # Cradle.
    draw.arc((18, 22, 46, 46), start=0, end=180, fill=color, width=5)
    # Stem and base.
    draw.rectangle((30, 45, 34, 52), fill=color)
    draw.rectangle((22, 52, 42, 56), fill=color)
    return image


class Tray:
    """Wraps a pystray icon and runs its message loop on its own thread."""

    def __init__(
        self,
        config_path,
        log_dir,
        on_toggle,
        on_pause,
        on_quit,
        on_language=None,
        language="",
        language_options=None,
        on_backend=None,
        backend="local",
        on_cleanup=None,
        cleanup=False,
    ):
        self._config_path = config_path
        self._log_dir = log_dir
        self._on_toggle = on_toggle
        self._on_pause = on_pause
        self._on_quit = on_quit
        self._on_language = on_language
        self._language = language or ""
        self._language_options = language_options or {
            "Auto-detect": "",
            "English": "en",
        }
        self._on_backend = on_backend
        self._backend = backend or "local"
        self._on_cleanup = on_cleanup
        self._cleanup = bool(cleanup)

        self._status = "Starting…"
        self._paused = False
        self._icons = {
            "idle": _make_icon(_IDLE),
            "busy": _make_icon(_BUSY),
            "paused": _make_icon(_PAUSED),
        }
        self._icon = pystray.Icon(
            "VoiceType",
            self._icons["idle"],
            "VoiceType",
            menu=self._build_menu(),
        )
        self._thread = None

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(lambda _: self._status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start / stop dictation", self._toggle),
            pystray.MenuItem(
                "Pause Ctrl+Alt",
                self._toggle_pause,
                checked=lambda _: self._paused,
            ),
            pystray.MenuItem("Language", self._language_menu()),
            pystray.MenuItem("Transcribed by", self._backend_menu()),
            pystray.MenuItem(
                "Clean up with AI",
                self._toggle_cleanup,
                checked=lambda _: self._cleanup,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Edit settings", self._open_config),
            pystray.MenuItem("Open logs", self._open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit VoiceType", self._quit),
        )

    def _language_menu(self):
        """Radio list for pinning the language when auto-detect misfires."""
        options = tuple((self._language_options or {}).items())
        return pystray.Menu(*[
            pystray.MenuItem(
                label,
                self._make_language_setter(code),
                checked=self._make_language_check(code),
                radio=True,
            )
            for label, code in options
        ])

    def _make_language_setter(self, code):
        def setter(_icon=None, _item=None):
            self._language = code
            if self._on_language:
                self._on_language(code)
        return setter

    def _make_language_check(self, code):
        return lambda _item: self._language == code

    def _backend_menu(self):
        """Chooses between local CPU transcription and the OpenAI API."""
        options = (
            ("This laptop (offline)", "local"),
            ("OpenAI (needs API key)", "cloud"),
        )
        return pystray.Menu(*[
            pystray.MenuItem(
                label,
                self._make_backend_setter(value),
                checked=self._make_backend_check(value),
                radio=True,
            )
            for label, value in options
        ])

    def _make_backend_setter(self, value):
        def setter(_icon=None, _item=None):
            self._backend = value
            if self._on_backend:
                self._on_backend(value)
        return setter

    def _make_backend_check(self, value):
        return lambda _item: self._backend == value

    def _toggle_cleanup(self, _icon=None, _item=None):
        self._cleanup = not self._cleanup
        if self._on_cleanup:
            self._on_cleanup(self._cleanup)

    # -- menu handlers -----------------------------------------------------

    def _toggle(self, _icon=None, _item=None):
        threading.Thread(target=self._on_toggle, daemon=True).start()

    def _toggle_pause(self, _icon=None, _item=None):
        self._paused = not self._paused
        self._on_pause(self._paused)
        self.set_status("Paused" if self._paused else "Ready")

    def _open_config(self, _icon=None, _item=None):
        self._open(str(self._config_path))

    def _open_logs(self, _icon=None, _item=None):
        self._open(str(self._log_dir))

    @staticmethod
    def _open(target):
        try:
            os.startfile(target)  # noqa: S606 - opening the user's own files
        except OSError:
            subprocess.Popen(["explorer", target])

    def _quit(self, _icon=None, _item=None):
        self._icon.visible = False
        self._icon.stop()
        self._on_quit()

    # -- public API --------------------------------------------------------

    def start(self):
        self._thread = threading.Thread(
            target=self._icon.run, name="tray", daemon=True
        )
        self._thread.start()

    def stop(self):
        try:
            self._icon.stop()
        except Exception:
            logger.debug("Tray stop raised", exc_info=True)

    def set_status(self, status, busy=False):
        """Updates the tooltip, menu header and icon colour."""
        self._status = status
        try:
            self._icon.title = "VoiceType · {}".format(status)
            if self._paused:
                self._icon.icon = self._icons["paused"]
            else:
                self._icon.icon = self._icons["busy" if busy else "idle"]
            self._icon.update_menu()
        except Exception:
            logger.debug("Tray update raised", exc_info=True)
