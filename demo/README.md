# The demo clip

`four_languages.wav` is 11 seconds of one sentence that changes language three
times, with no pause at the switches:

> I already sent the invoice, aber ich warte noch auf eine Antwort, но клиент
> до сих пор не ответил, сондықтан ертең қоңырау шаламын.

English, German, Russian, Kazakh. "I already sent the invoice, but I am still
waiting for a reply, but the client still has not answered, so tomorrow I will
call."

```powershell
.venv\Scripts\python.exe tools\try_demo.py --both
```

## What comes back

Local is `base` on CPU with int8, the default, on a laptop with no GPU.

| Backend | Time | Result |
| --- | --- | --- |
| OpenAI | 3.6s | all four languages, correct |
| Local, default | 1.7s | `I already sent the invoice.` |
| Local, `per_segment_language: true` | 1.6s | same |
| Local, `per_segment_language: true` and `segment_min_pause: 0.05` | 5.2s | `I already sent the invoice. Не ответил. Сонд ртан? Ертен конрау шаламын.` |

The second row is not a typo. Splitting on pauses cannot help when there are no
pauses: the joins in this clip are 70ms and `segment_min_pause` defaults to
350ms. Drop the threshold far enough and the splitter does fire, which is the
last row, and it recovers some of the Cyrillic but loses the German and mangles
the Kazakh.

## How it was made

Four requests to OpenAI's `gpt-4o-mini-tts`, one per language, same voice
throughout, trimmed of silence and joined with 70ms gaps.

One request per language, not one for the whole sentence. Given the mixed
sentence at once, the voice locks onto a single language and reads the rest
phonetically: the Russian came back as "Nur Klient dusich pone atwitel".
OpenAI's speech synthesis has the same one-language-per-utterance limit its
transcription models do.

The Windows voices cannot do this at all. There are four installed here, all
en-US, de-DE or ru-RU, so Kazakh would have to be read by the Russian voice and
a Kazakh speaker would hear that immediately.

## It is synthetic speech, which is easier

A real speaker does not pronounce the final -r in "aber". It vocalises to a
schwa, so the microphone hears roughly "abe", and coming out of Kazakh the
model is already decoding Cyrillic and returns "абы". That was a real bug, and
the `keywords` field in `config.json` exists because of it. The TTS voice
pronounces "aber" fully every time, so this clip never triggers it.

This clip proves the four-language claim is real. It does not prove your voice
will do as well. Record yourself saying the same sentence and point the tool at
it:

```powershell
.venv\Scripts\python.exe tools\try_demo.py my_recording.wav --both
```

Any 16-bit wav, mono or stereo, at any sample rate.
