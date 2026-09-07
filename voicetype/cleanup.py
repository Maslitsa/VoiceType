"""Optional LLM tidy-up pass over the raw transcript.

This is what Wispr Flow's "AI enhancement" actually is: strip filler words,
fix punctuation and casing, leave the wording alone. It runs after
transcription and adds a round trip, so it is off by default.

The prompt is deliberately conservative. A cleanup pass that paraphrases is
worse than none at all, because you cannot tell what it changed.
"""

import logging

logger = logging.getLogger("voicetype.cleanup")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_INSTRUCTIONS = (
    "You clean up dictated text. Return ONLY the corrected text, with no "
    "commentary, quotes or explanation.\n"
    "Rules:\n"
    "- Keep the speaker's exact wording, language and meaning. Never "
    "translate, paraphrase or add content.\n"
    "- If the text mixes languages, keep each part in its original language.\n"
    "- Remove filler words and false starts (um, uh, э, эм, ну, like, "
    "you know) and stutter repetitions.\n"
    "- Fix punctuation, capitalisation and obvious speech-to-text errors.\n"
    "- Preserve any deliberate formatting the speaker dictated.\n"
    "- If the text is already clean, return it unchanged."
)


class Cleaner:
    """Sends the transcript through a small chat model for tidying."""

    def __init__(self, config):
        self._cfg = config["cleanup"]
        self._cloud = config["transcription"]["cloud"]

    @property
    def enabled(self):
        return bool(self._cfg["enabled"])

    def _api_key(self):
        key = (self._cloud.get("api_key") or "").strip()
        if key:
            return key
        import os
        return (os.environ.get(self._cloud["api_key_env"]) or "").strip()

    def clean(self, text):
        """Returns the tidied text, or the original if anything goes wrong."""
        if not self.enabled or not text.strip():
            return text
        key = self._api_key()
        if not key:
            logger.warning("Cleanup is on but there is no API key")
            return text

        import httpx

        instructions = self._cfg.get("instructions") or DEFAULT_INSTRUCTIONS
        try:
            response = httpx.post(
                OPENAI_CHAT_URL,
                headers={
                    "Authorization": "Bearer {}".format(key),
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._cfg["model"],
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": text},
                    ],
                },
                timeout=float(self._cfg["timeout"]),
            )
            if response.status_code != 200:
                logger.warning(
                    "Cleanup API %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return text
            payload = response.json()
            cleaned = payload["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("Cleanup failed; keeping the raw transcript")
            return text

        if not cleaned:
            return text
        # A cleanup pass should tidy, not rewrite. If the length changes
        # wildly the model has gone off-script, so keep the original.
        ratio = len(cleaned) / max(1, len(text))
        if ratio < 0.5 or ratio > 1.6:
            logger.warning(
                "Cleanup changed length too much (%.2fx); keeping raw text",
                ratio,
            )
            return text
        if cleaned != text:
            logger.info("Cleanup applied (%d -> %d chars)",
                        len(text), len(cleaned))
        return cleaned
