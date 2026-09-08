# The demo clip

`four_languages.wav` is 11 seconds of one sentence that changes language three
times, with no pause at the switches:

> I already sent the invoice, aber ich warte noch auf eine Antwort, но клиент
> до сих пор не ответил, сондықтан ертең қоңырау шаламын.

English, then German, then Russian, then Kazakh. It means "I already sent the
invoice, but I am still waiting for a reply, but the client still has not
answered, so tomorrow I will call."

Run it yourself:

```
.venv\Scripts\python.exe tools\try_demo.py --both
```

## What comes back

Measured on this clip, on a laptop with no GPU. Local is `base` on CPU with
int8, which is the default.

| Backend | Time | Result |
| --- | --- | --- |
| OpenAI | 3.6s | `I already sent the invoice. Aber ich warte noch auf eine Antwort. Но клиент до сих пор не ответил. Сондықтан ертең қоңырау шаламын.` |
| Local, default | 1.7s | `I already sent the invoice.` |
| Local, `per_segment_language: true` | 1.6s | `I already sent the invoice.` |
| Local, `per_segment_language: true` and `segment_min_pause: 0.05` | 5.2s | `I already sent the invoice. Не ответил. Сонд ртан? Ертен конрау шаламын.` |

The cloud row is three out of three across repeated runs.

The second row is not a typo. Splitting on pauses cannot help when there are no
pauses to split on: the joins in this clip are 70ms and `segment_min_pause`
defaults to 350ms. Drop the threshold far enough and the splitter does fire,
which is the third row, and it recovers some of the Cyrillic but loses the
German and mangles the Kazakh.

That is the honest state of the local backend. It is better than plain Whisper
on multilingual audio and it is not as good as sending a `languages` list to a
model that accepts one.

## How the clip was made

Four requests to OpenAI's `gpt-4o-mini-tts`, one per language, same voice
throughout, trimmed of leading and trailing silence and joined with 70ms gaps.

One request per language is necessary rather than tidy. Handed the whole mixed
sentence at once, the voice locks onto a single language and reads the rest
phonetically. Russian came back as "Nur Klient dusich pone atwitel". OpenAI's
speech synthesis has the same one-language-per-utterance limit that its
transcription models do, which is the exact problem this project exists to work
around.

## Why this is not quite a fair test

**The speech is synthetic, and synthetic speech is cleaner than real speech.**

A real speaker does not pronounce the final -r in "aber". It vocalises to a
schwa, so a microphone hears roughly "abe", and coming out of Kazakh the model
is already decoding Cyrillic and returns "абы". That was a real bug, and the
`keywords` field in `config.json` exists because of it. The TTS voice
pronounces "aber" fully every time, so this clip never triggers it.

So treat this as a floor, not a ceiling. It proves the four-language claim is
real. It does not prove your voice will do as well on the first try.

If you want a harder test, record yourself saying the same sentence and point
the tool at it:

```
.venv\Scripts\python.exe tools\try_demo.py my_recording.wav --both
```

Any 16-bit wav works, mono or stereo, at any sample rate.
