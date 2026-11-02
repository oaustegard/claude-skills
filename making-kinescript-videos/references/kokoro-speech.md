# Controlling Kokoro speech in a Kinescript scene

Everything here was measured on 2026-11-02 with kokoro 0.9.4, misaki 0.9.4 and
the voices in `hexgrad/Kokoro-82M`, calling `KPipeline(...)(text, voice, speed)`
the way `kinescript-kokoro` does. Pitch came from Praat (parselmouth), pauses
from a −40 dB silence scan, and transcripts from faster-whisper `small.en`.
A claim marked *source* comes from reading the misaki or kokoro code, not
from a measurement.

## Text changes made by `kine voice`

`kine voice` does four things to a sound's `text` before Kokoro sees it
(`kinescript/voice.py`, `split_marks` and `untag`):

- It removes `[[mark]]` word ids. The words file keeps them.
- It removes single-bracket tags (`[laughs]`) and lists them under `ignored` in its JSON output.
  Kokoro has no tags.
- It collapses all whitespace to single spaces. A newline in `text` therefore
  does **not** start a new Kokoro segment. For a separate segment, use a
  separate sound.
- It passes misaki links (`[word](...)`) through untouched, so every control
  below works inside a scene.

`speaker` reaches the plugin as one string. Its **first character picks the
language pipeline** (`a` American, `b` British), so that character must be
the language letter even for a blend or a file path.

## See the phonemes before you listen

Every pronunciation problem shows up in the phoneme string, which takes
seconds to print and needs no model weights:

```python
from kokoro import KPipeline
g2p = KPipeline(lang_code="a", model=False)   # "b" for British voices
for line in ["Meet Kinescript.", "Meet [Kinescript](/kˈɪnəskɹˌɪpt/)."]:
    print(line, "->", " | ".join(r.phonemes for r in g2p(line)))
```

Run it with the plugin's Python (`~/kokoro-env/bin/python` in the skill's setup). The first call downloads
spaCy's `en_core_web_sm`. Under `uv`, set `VIRTUAL_ENV` first, or the download
fails with "No virtual environment found".

## Pronunciation

### Inline phonemes: `[word](/phonemes/)`

The phonemes between the slashes replace misaki's guess for that word. The words file still shows the word as written.

Write them in **Kokoro's alphabet**, not textbook IPA. The model looks each
character up in its vocabulary and drops any it lacks
without a warning
(`kokoro/model.py`, `filter(... self.vocab.get(p) ...)`, *source*):

| Write | Not | Sound |
|---|---|---|
| `ɡ` (U+0261) | `g` | g in *go*. ASCII `g` is not in the vocabulary: `[Huginn](/hˈugɪn/)` came out as "Koo-in" |
| `A` `I` `W` `Y` | `eɪ` `aɪ` `aʊ` `ɔɪ` | the vowels of *day*, *my*, *now*, *boy* |
| `O` (American), `Q` (British) | `oʊ`, `əʊ` | *go* |
| `ʤ` `ʧ` | `dʒ` `tʃ` | *judge*, *church*, one symbol each |
| `ɹ` | `r` | English r |
| `ᵊ` `ᵻ` | | the small vowels in *pupil* (`pˈipᵊl`) and *wanted* |
| `T` | | the American flap in *thirty* (`θˈɜɹTi`); misaki writes `T`, and `ɾ` is also accepted |
| `ˈ` `ˌ` | `'` `,` | primary and secondary stress, placed before the stressed vowel |
| `ː` | | British long vowels only (`ʃˈiː`) |

The vowel sets differ by language. American:
`AIOWYbdfhijklmnpstuvwzæðŋɑɔəɛɜɡɪɹɾʃʊʌʒʔʤʧˈˌθᵊᵻ`. British:
`AIQWYabdfhijklmnpstuvwzðŋɑɒɔəɛɜɡɪɹʃʊʌʒʤʧˈˌːθᵊ`. Use the set that matches the
voice's first letter.

The easiest way to write phonemes is to copy them. Print the G2P of a
respelling or a similar word that comes out right, then paste its phonemes
into the link.

Keep each link to one word. misaki joins `[New York](...)` into one timed word.
Put a space or punctuation on both sides of a link. `Meet[Kinescript](/…/)now`
ran the words together and spoke the link twice.

### Stress links and capitals

| Syntax | Effect |
|---|---|
| `[word](+1)`, `[word](+2)` | raise stress one or two steps; any integer is accepted (*source*) |
| `[word](-1)`, `[word](-2)` | lower it; `-2` removes it (`[really](-2)` → `ɹiᵊli`) |
| `[word](0.5)`, `[word](-0.5)` | half steps (*source*) |
| `WORD` in capitals | the same as `+2` (*source*) |
| `Word` capitalised | `+0.5`, too small to matter on a sentence's first word |
| `*word*` | unpredictable: `*she*` lost its asterisks, but `*really*` was read "asterisk really asterisk". Don't use it |

Stress is the only emphasis Kokoro has, and it works on a word that was
unstressed. In "I never said she stole it", `she` measured 0.15 s at
−3.6 semitones under the line's median. `[she](+2)` and `SHE` both gave
`ʃˈi`, 0.21 s and +0.0 st against the median, so the word was 40% longer and 3.6 semitones
higher. Raising stress on a word that already has primary stress (`NEVER`)
changed nothing.

`[she](+1)` gives secondary stress (`ʃˌi`), a lighter lift.

Capitals also trigger acronym handling. A word in capitals that is not in
the dictionary is spelled out: `KINESCRIPT` came out as the ten letters
K-I-N-E-S-C-R-I-P-T, and `MUNINN` as six. Use capitals for emphasis only on
ordinary words, and a `+2` link on anything else.

### Number flags: `[150](#flags#)`

| Text | Said |
|---|---|
| `150` | one hundred fifty, in both American and British pipelines |
| `[150](#a#)` | a hundred fifty |
| `[150](#&#)` | one hundred **and** fifty (the British reading) |
| `[101](#n#)` | one hundred'n one ("and" run into "hundred") |

Flags combine: `[150](#a&#)` is "a hundred and fifty".

### Respelling

Respelling works when the letters are unambiguous: "Moonin" gives `mˈunɪn`
for Muninn, which on its own comes out "MYOO-nin". It fails on English
spelling rules: "Hoogin" gives `hˈuʤɪn` (HOO-jin), because g before i is
soft. "Hoo-ghin" gives `hˈuɡˈɪn` with the hard g. Each hyphenated piece is
stressed, though, so a respelling can carry stress where the name has none.
Prefer the phoneme link and keep respelling for quick drafts.

## Numbers, abbreviations and symbols

Measured with the American pipeline unless noted. Fix a row that reads
wrong by rewriting the text or using a phoneme link.

| Text | Said | Fix if wrong |
|---|---|---|
| `NASA` | NASS-uh (word) | |
| `GPU`, `N.A.S.A.`, `U.S.` | letters spelled | |
| `SQL` | sequel | `S Q L` for letters |
| `JSON` | J-S-O-N, spelled | `[JSON](/ʤˈAsᵊn/)` |
| `Dr. Smith` | doctor | |
| `Main St.` | Main **saint** | write `Street` |
| `vs.` | versus | |
| `1990`, `2026` | nineteen ninety, twenty twenty-six | |
| `2007` | two thousand seven (the year reading for 2000–2009) | `twenty oh seven` if wanted |
| `1500` | fifteen hundred: every bare 4-digit number reads as a year | `1,500` reads as a count |
| `007` | **seven** (leading zeros dropped) | `[007](/dˈʌbᵊl ˈO sˈɛvən/)` or words |
| `404` | four hundred four | `four oh four` |
| `3.14`, `0.5` | three point one four, zero point five | |
| `10,000`, `1,000,000` | ten thousand, one million | |
| `1st`, `23rd` | first, twenty-third | |
| `$5.50`, `£3`, `€12` | five dollars and fifty cents, three pounds, twelve euros | |
| `50% & more @ home + extras` | percent, and, at, plus | |
| `4:30` | four, pause, thirty | `four thirty` |
| `11/02/2026` | eleven zero two twenty twenty-six | write the date in words |
| `555-1234` | five hundred fifty-five, twelve thirty-four | `5 5 5, 1 2 3 4` |
| `austegard.com` | austegard, pause, com: the dot is read as a full stop | `austegard dot com` |
| `well-known` | one word, `wˌɛlnˈOn` | |

A word that is in no dictionary goes to espeak-ng (`Zyxqwv` → `zˈɪkskʊv`). If
espeak fails to load, kokoro logs "EspeakFallback not Enabled: OOD words will
be skipped" and drops such words from the audio without an error (*source*,
`kokoro/pipeline.py`). A name missing from the phoneme print is the sign.

### Homographs

misaki picks between readings by spaCy's part-of-speech tag, which is right
most of the time and wrong on short or habitual sentences:

| Text | Said | Right? |
|---|---|---|
| Yesterday I read a book. | `ɹˈɛd` | yes |
| I read books. / I read the report every day. | `ɹˈɛd` | **no**, present tense |
| Lead the team. | `lˈid` | yes |
| A lead pipe. | `lˈid` | **no**, the metal |
| I live here. / Live music. | `lˈɪv` / `lˈIv` | yes |
| Record a record. | `ɹəkˈɔɹd` / `ɹˈɛkəɹd` | yes |
| The wind blew. / Wind the clock. | `wˈɪnd` / `wˈInd` | yes |

Pin the one you mean: `[read](/ɹˈid/)`, `[lead](/lˈɛd/)`.

## Pauses

Silence between "scene" and "Check" in "Write the scene_Check it now.", with each
mark below put in place of `_` (`af_heart`, rate 1):

| Between them | Silence |
|---|---|
| a space | none |
| `—`, `–`, ` - ` | 0.07 s |
| `…` (one character) | 0.09 s |
| `,` | 0.11 s |
| `;` | 0.18 s |
| `:` | 0.20 s |
| `!` | 0.22 s |
| `?`, `...` (three dots), `.` | 0.25–0.26 s |
| `. .` | 0.25 s, no more than one period |

A quarter second is the longest pause punctuation makes, and stacking marks
does not lengthen it. For a longer beat, end the sound and start the next
line as its own sound, cued after it: `"at": "vo1.out+0.6"`.

A spaced hyphen is unreliable. It became `—` in the sentence above, and in
`a - b` it vanished. Write `—` or a comma.

Every Kokoro clip starts with 0.3–0.4 s of silence before the first word
and ends with about 0.4–0.6 s after the last. Cue visuals to a word
(`"at": "vo1:render"`), not to `vo1.in`, which is a third of a second early.

## Intonation

**Kokoro does not raise its pitch for a question.** Last-word pitch change,
first third to last third of the word:

| Line | af_heart | am_michael | bf_emma | bm_george |
|---|---|---|---|---|
| You're ready. | −10.0 | −5.7 | −3.1 | −10.3 |
| You're ready? | −9.2 | −6.1 | −2.9 | −10.5 |
| Are you ready? | −10.4 | −5.1 | −2.9 | −8.8 |
| Ready? | −2.8 | −2.6 | −2.9 | −11.0 |
| Ready, or not? | +0.5 | −3.9 | −1.8 | −10.1 |

All values are semitones. The `?` changes the pause after it and little
else. Wh-questions and `!` also fall. Kokoro's vocabulary includes the
arrows `↗ ↘ ↓ →`, but inside a phoneme link they did not make a rise
(`ɹˈɛdi↗` fell 12 st). Leave them out.

There is no SSML, no emotion or style control and no tag support. What you
can control is:

- **Voice choice.** Pitch spread over one test sentence ranged from 2.6
  semitones SD (`bf_emma`) and 2.8 (`af_heart`) to 4.6 (`af_bella`) and
  6.8 (`af_nicole`, a soft, slow voice).
- **Stress links** on the words that carry the point.
- **Sentence shape.** Short sentences and varied punctuation break up the
  falling contour that long lines settle into.
- **Another backend** for a line that must rise or emote:
  `"backend": "elevenlabs"` acts on tags, and `chatterbox` copies the
  delivery of a reference clip given as its `speaker` (`kine docs`, SOUND).

## Pace

`rate` is Kokoro's `speed`. It changes tempo, not pitch (191 Hz median at
every rate), and wpm scales close to linearly with it. One 21-word sentence
at rate 1:

| Voice | wpm | median F0 | pitch SD (st) |
|---|---|---|---|
| af_heart | 212 | 191 | 2.8 |
| af_bella | 204 | 198 | 4.6 |
| af_nicole | 136 | 160 | 6.8 |
| am_michael | 197 | 110 | 3.5 |
| am_adam | 220 | 109 | 3.2 |
| am_puck | 209 | 103 | 4.5 |
| bf_emma | 228 | 178 | 2.6 |
| bm_george | 196 | 137 | 3.8 |
| bm_fable | 237 | 111 | 4.2 |
| bm_lewis | 207 | 85 | 3.6 |

Those figures come from one sentence with a single comma. Real narration
runs much slower, because every full stop and comma adds a pause: eleven
narration lines of one to three sentences each, in the
`bm_fable,bm_fable,bm_lewis` blend, measured 139 wpm at rate 0.78 and 179
wpm at 0.95. Measure on the actual script, then set `rate ≈ current rate ×
target ÷ measured`. At rate 1.5 (351 wpm) the first consonant went: "Kinescript" was
heard as "Einscript". At rate 0.6 a phantom syllable came before the first
word ("Check it now" was heard as "To check it now"), as hexgrad/kokoro issue #344
reports for slow speeds. Keep rate between about 0.7 and 1.3.

A one- or two-word line can sound unlike the same voice in a sentence
(Kokoro picks the voice's style by line length, *source*). Bundle short
utterances into one sound, as the model's `VOICES.md` on Hugging Face advises.

## Voices and blends

- `"speaker": "af_heart,af_bella"` averages the two voices' style tensors.
- **Weighted blends need no file: repeat a voice.** `"bm_fable,bm_fable,bm_lewis"` is ⅔ fable,
  ⅓ lewis (`load_voice` averages the list as given, *source*). Median F0:
  fable 111 Hz, lewis 85, equal blend 100, 2:1 blend 102, and a
  0.65/0.35 `.pt` blend (next item) 103.
- **A `.pt` file works as a speaker** (`load_single_voice` loads any name
  ending in `.pt`, *source*). Make one:
  ```python
  import torch
  from huggingface_hub import hf_hub_download
  v = lambda n: torch.load(hf_hub_download("hexgrad/Kokoro-82M", f"voices/{n}.pt"), weights_only=True)
  torch.save(0.65 * v("bm_fable") + 0.35 * v("bm_lewis"), "bm_muninn.pt")
  ```
  Name it so the first letter is the language, and give a path relative to
  the folder `kine voice` runs in. An absolute path starts with `/`, which is
  no language letter. `kine voice` decides whether to re-speak from the
  `speaker` string, so after changing the file's contents run
  `kine voice --force`.
- Blend voices of one language. The first letter sets the G2P, and the
  other voices only colour the sound.

## Long text

Kokoro takes at most 510 phonemes at a time. Longer text is cut at the
last `. ! ? …` that fits, then at `: ;`, then at `, —` (`waterfall_last`,
*source*). Each piece is generated alone, so the pitch resets at every cut.
Keep one sound to a few sentences, and split longer narration into sounds
cued one after another.

## Verification steps for a line

1. Print the phonemes. Every name, number and abbreviation is visible there.
2. Speak it with `kine voice`, which re-speaks only changed sounds.
3. Transcribe with faster-whisper (`pip install faster-whisper`, model
   `small.en`) for a word error rate, but do not trust
   it on coined names. It heard the correct `[Huginn](/hˈuɡɪn/)` as "Who
   can". A person has to judge a name.
4. Measure pace from the words file: words ÷ (last end − first start) × 60.
