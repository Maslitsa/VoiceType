# Accuracy: what was measured

Everything here was measured on one machine, a Ryzen 7 7730U laptop with no
GPU, using the scripts in [`tools/`](../tools). Your numbers will
differ. The *relationships* between them are the useful part.

---

## Languages

`model.language` is `""` by default, so Whisper detects the language of each
utterance. English, Russian and German all work without touching anything.

If auto-detect guesses wrong, **tray → Language** pins one. It applies to the
very next thing you say, with no restart and no model reload, and is
remembered.

German transcribes about as well as English here, umlauts included, in
0.9–1.5 s. Russian is the weakest of the three, for the reasons below.

Auto-detect on ordinary speech, `base` model:

| Clip | Detected | Result |
| --- | --- | --- |
| English, ordinary sentence | `en` (p=0.99) | exact |
| Russian, ordinary sentence | `ru` (p=0.99) | exact |
| German, ordinary sentence | `de` (p=1.00) | exact, umlauts included |
| "The quick brown fox…" pangram, synthetic voice | `uk` ✗ | Cyrillic nonsense |

It is dependable on normal speech, and only slipped on an artificial pangram
read by a robotic TTS voice.

### Pin the language only when the whole sentence is in it

Whisper commits to one language per utterance and *translates* anything spoken
in another. Pinning makes that worse, not better:

| Audio | Setting | Result |
| --- | --- | --- |
| Russian → English | auto | both halves correct |
| Russian → English | pinned `en` | Russian half **translated** into English |
| English → Russian | pinned `ru` | English half became garbled Cyrillic |

---

## Switching language mid-sentence

This is the problem VoiceType exists to solve.

### Locally: `per_segment_language`

`transcription.per_segment_language` (**off** by default) works around
Whisper's one-language-per-utterance rule by splitting the recording at pauses
and detecting the language of each piece.

```
"I already sent the invoice yesterday but клиент до сих пор не ответил"

off -> "...but Client has still not answered my letter"        (translated)
on  -> "I already sent the invoice yesterday but
        Клиент до сих пор не ответил на моё письмо."           (correct)
```

It is off by default because it only fixes **English → other**, and charges for
it everywhere else. A segment is transcribed without its surrounding context,
and that costs accuracy: "bis morgen früh schicken" came back as "bis morgen
frischicken", sentence-final punctuation goes missing, and it runs ~1.7× slower.
Russian → English and German → English already come out right in a single pass.

It also only helps when you actually *pause* at the switch. A seamless switch
still lands in one language.

`segment_max` (3) and `segment_min_length` (1.2 s) bound the cost. Whisper pads
every piece to a 30-second window, so each segment is a whole extra pass. One
minute of speech with natural pauses once produced seventeen of them and took
22 s instead of 3.

### Through OpenAI: the `languages` list

The request sends `transcription.cloud.languages`, a list, rather than a
single language, so the model expects all of them instead of committing to
whichever it hears first.

This is load-bearing, not decoration. On a Russian sentence ending in English,
`gpt-transcribe`:

| `languages` sent | Result |
| --- | --- |
| *(nothing)* | dropped the English half |
| `["ru", "en"]` | dropped the English half |
| `["en", "ru", "de"]` | **both halves, correct** |

Keep every language you use in that list, and keep `en` first. Pinning a
language in the tray overrides the list for that utterance.

> **This no longer reproduces on clean audio, and you should know that.**
>
> The table above was measured on real speech through a real microphone. Rerun
> today against synthesised speech, `gpt-transcribe` returns both halves
> correctly with **no list at all**, four times out of four, in both the
> Russian-to-English and English-to-Russian directions. The same holds for a
> four-language clip including Kazakh: every list from empty to complete
> returns all four.
>
> Two explanations fit, and they are not exclusive. Synthesised speech is
> cleaner than a real voice, and a language prior is exactly the kind of help
> that only matters when the audio is ambiguous. And `gpt-transcribe` is a
> hosted model that changes underneath us, so a measurement from weeks ago is
> not evidence about today.
>
> The list is still sent, it still costs nothing, and it still cannot hurt. But
> it is no longer demonstrably load-bearing, and the sentence above claiming it
> is should be read with that in mind. Check your own voice:
>
> ```
> tools\try_demo.py my_recording.wav --sweep
> ```

### Which cloud model

Measured on the same mixed English/Russian clip:

| Model | Result |
| --- | --- |
| **`gpt-transcribe`** | both halves, each in its own script |
| `gpt-4o-transcribe` | dropped the English half entirely |
| `gpt-4o-mini-transcribe` | dropped the English half entirely |
| `whisper-1` | translated the Russian into English |

`gpt-4o-transcribe` also rejects `languages` and `keywords` outright ("not
supported for this model"), so `gpt-transcribe` is the one to use.

OpenAI has been renaming these models and moved from a singular `language`
field to the `languages` list. Rather than guess, the client sends the newest
shape and steps back a version at a time if the server refuses: it drops a field
the error names as unknown, and falls back to singular `language` if the list is
rejected. It retries once or twice on a rate limit or a 5xx, since the
alternative is losing what you just said.

---

## Short utterances are the hard case

Everything above uses whole sentences. A short phrase with a proper noun in it
is much harder, because language identification has almost nothing to work
with.

Saying **"Türkenstraße 3"**, a German street name, came back as
**"Тюркенштрассе 3."**, transliterated into Cyrillic, from the *cloud* backend
with `languages: ["en", "ru", "de"]`.

The interesting part is that this is not reproducible with clean audio. The
same words synthesised with a German TTS voice were transcribed correctly by
every configuration tested:

| Setting | "Türkenstraße 3" | In a full sentence |
| --- | --- | --- |
| local `base`, auto-detect | ✅ correct | ✅ correct |
| local `base`, pinned `de` | ✅ correct | ✅ correct |
| cloud, `["en","ru","de"]` | ✅ correct | ✅ correct |
| cloud, `["de","en"]` | ✅ correct | ✅ correct |
| cloud, + `keywords` | ✅ correct | ✅ correct |
| cloud, pinned `de` | ✅ correct | ✅ correct |

So the failure is not the configuration. It is the combination of a real
speaker's accent, a quiet microphone, and two or three words of context, at
which point "is this German or Russian?" is genuinely ambiguous, and a
multilingual speaker's accent can tip it the wrong way.

**What to do about it**

1. **Pin the language** in the tray before dictating a bare name, address or
   term. It is the only thing that removes the ambiguity outright, and it takes
   effect on the very next thing you say.
2. **Say a sentence, not a fragment.** "Ich wohne in der Türkenstraße 3" gives
   the model enough to decide, and was correct everywhere.
3. **Add the words to `transcription.cloud.keywords`** if you dictate the same
   names often.
4. **Raise your microphone level.** Quiet audio degrades language
   identification before it degrades anything else.

---

## Model size: bigger is not better

`model.final`, median of three runs, for a 3.3 s phrase:

| Model | Time | Notes |
| --- | --- | --- |
| `tiny` | ~1 s | noticeably more mistakes |
| **`base`** (default) | **1.9 – 3.1 s** | correct on ordinary sentences in all three languages |
| `small` | 5.8 – 6.4 s | better on hard audio, but **dropped a whole clause** on every code-switch clip tested |
| `large-v3-turbo` | **16.6 – 17.9 s** | unusable here, and also dropped the English half of a switch |

Two things to take from this.

**Cost barely depends on how long you spoke.** Whisper always processes a
30-second window, so `small` takes ~6 s even for a three-second phrase.

**Bigger models are worse at code-switching.** Both `small` and
`large-v3-turbo` were *worse* than `base` on mixed-language clips: more capacity
means a stronger single-language prior, so they committed harder and silently
discarded the other half. On a CPU the cost is Whisper's encoder, and "turbo"
only slims the decoder, hence 17 s.

If you want better multilingual results, the cloud backend is the answer, not a
bigger local model.

---

## Latency: where the wait actually goes

RealtimeSTT's headline feature is real-time transcription, and it is worth
being precise about what that buys, because it is easy to expect the wrong
thing from it.

**It does not make the final transcript arrive faster.** What it does is
transcribe continuously *while you are still speaking*, with a small model, so
words appear as you say them. By the time you stop, you already know roughly
what it heard, and a two-second wait for the accurate version feels like
nothing, because you are not staring at an empty box wondering whether it
worked.

VoiceType uses RealtimeSTT for exactly that, plus the capture pipeline and the
voice-activity detection that ends a hands-free recording. The live preview in
the pill is this feature.

### Measured, five runs each

| Audio | local `base` (CPU) | cloud `gpt-transcribe` |
| --- | --- | --- |
| 2.9 s clip | 1.47 s (max 1.61) | 1.33 s median (max 2.03) |
| 8.2 s clip | 1.89 s (max 1.97) | 2.06 s median (max 2.56) |

Two things worth noticing.

**The cloud is not the fast option.** Its median is fine, but it is at the
mercy of your connection: the worst seen in ordinary use was **7.7 s**, for a
two-second clip, while the local model has never taken more than about two.
Choose the cloud for Russian, German and mid-sentence switching. Not for speed.

**Length barely matters.** 8.2 seconds of audio costs only ~0.4 s more than
2.9 seconds locally, because Whisper pads everything to a 30-second window.
Dictating a long paragraph is not slower than dictating a sentence.

### Things that do not help

- **Greedy decoding.** `beam_size: 1` measured 1.50–1.54 s against 1.61–1.73 s
  for the default 5, about a tenth of a second, and produced identical text
  on clean clips. Which means the only place it can differ is exactly the hard
  audio where the beam search is earning its keep. Not worth it.
- **A smaller final model.** `tiny` is roughly a second faster and noticeably
  worse. `base` is the right point on that curve.
- **Transcribing incrementally during the recording.** Tempting, and it is what
  the realtime preview already does. Doing it for the *final* text would mean
  transcribing segments without their surrounding context, which
  [measurably costs accuracy](#switching-language-mid-sentence), and would
  save around a second on a path that already takes under two.

### What did change

`transcription.cloud.timeout` is 15 s, not 30. Given a 1–3 s normal range and a
7.7 s worst case, anything past 15 s is stuck rather than slow, and waiting
half a minute before falling back to a model that answers in under two seconds
is a bad trade.

---

## Microphone level matters more than you would think

Whisper degrades unevenly when the input is quiet, and **Russian suffers
first**. The same sentence at full level and at about a tenth of it:

| Level | English | Russian |
| --- | --- | --- |
| full | exact | exact |
| ~10% of full | still exact | "Это Фроверка Система Голосового года Текстапа" |

Boosting the quiet recording back up recovered most of the Russian ("Это
проверка системы…") but not all of it. So if Russian is coming out badly, check
your input level in **Sound settings → Input** before changing models.

### The VAD gets less sensitive as the input gets quieter

Every recording is checked for real speech before transcription, because
Whisper invents sentences out of silence. That check is WebRTC VAD, and its
sensitivity depends on the absolute input level, which is how a real
spoken sentence can be thrown away as silence.

Longest unbroken run of speech frames, measured through a very quiet
microphone (peaks near 0.08 where 0.9 is available), threshold 12:

| Audio | `vad_aggressiveness: 2` | `vad_aggressiveness: 1` |
| --- | --- | --- |
| English speech | 19 | 40 |
| Russian speech | **8** ← discarded | 23 |
| silence | 4 | 5 |

At 2, a real Russian sentence scored below the threshold and was thrown away.
The default is 1, where both languages clear it comfortably and silence still
does not.

### Why the boost is not applied before the guard

`normalize_for_transcription` boosts quiet audio before transcribing, but
**never** before the speech guard. Normalising first scales the noise floor up
with everything else: silence at peak 0.044 then measures **300 speech frames
out of 300**, the guard never fires, and hallucinated sentences come back.

The guard sees raw audio. The transcriber gets a clean loud signal. They are
deliberately different.

---

## Local vs cloud, same degraded audio

All three sentences were played through speakers and picked up by the
microphone, so both backends got the same imperfect signal.

| Spoken | Local `base` | OpenAI |
| --- | --- | --- |
| *Können Sie mir den Bericht bis morgen früh schicken?* | "Das Treffen bringt darauf doll das Tag statt" | exact |
| *I already sent the invoice yesterday but клиент до сих пор не ответил…* | "I've already sent me an voice yesterday, but today children mind your piece more" | exact, both scripts |
| *Ich habe die Rechnung gestern geschickt aber the client has not replied…* | first half garbled | exact, both languages |

Reproduce it yourself:

```powershell
.venv\Scripts\python.exe tools\check_cloud.py
```

It synthesises the sentences with your installed Windows SAPI voices, sends
them, and prints the results and the cost.

---

## Limits that are Whisper's, not this app's

- **Russian is weaker than English locally.** Roughly two-thirds of Whisper's
  training audio is English, so the small models spend their capacity there and
  the gap widens as the model shrinks.
- **A noisy room is transcribed too.** The silence guard rejects genuine
  silence; it cannot tell your voice from a conversation next to you. Measured
  in a quiet room the microphone flags 11% of frames as speech, in a loud one
  86%.
- **Transcription happens after you stop speaking**, on CPU. The live preview
  is a separate, much smaller model.
