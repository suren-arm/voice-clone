# Armenian Language Support

**Research date: 11 September 2026.**

## The short version

> **Native Armenian support: none.**
> No open-source zero-shot voice-cloning model supports Armenian, as of this date.
>
> **Possible experimental Armenian support: yes, and it ships in this app** —
> behind a flag, labelled as experimental everywhere it appears.

Those two statements are kept strictly separate throughout the product: in the
API (`native: false, experimental: true` on the language option), in the UI (an
"Experimental language" warning before you generate, and an "Experimental
output" banner after), and on the stored record (`experimental = true` on the
generation row).

---

## What was verified

### Chatterbox does not support Armenian

Read directly from `chatterbox/mtl_tts.py`:

```
SUPPORTED_LANGUAGES = {ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh}
```

23 entries. No `hy`. Passing `language_id="hy"` raises `ValueError`; the app
never does — the language service intercepts it first.

The same holds for XTTS-v2 (17 languages), CosyVoice 2 (zh/en/ja/ko + Chinese
dialects), F5-TTS (public zh/en checkpoints), OpenAudio S1 and IndexTTS-2.5
(zh/en/ja/es/ar).

### Native Armenian TTS exists — but it cannot clone

| Model | Language | License | Cloning |
|---|---|---|---|
| [`facebook/mms-tts-hye`](https://huggingface.co/facebook/mms-tts-hye) | Eastern Armenian | CC-BY-NC-4.0 | No |
| [`facebook/mms-tts-hyw`](https://huggingface.co/facebook/mms-tts-hyw) | Western Armenian | CC-BY-NC-4.0 | No |

VITS-based, one fixed synthetic voice each, non-commercial. Genuinely useful if
you want *Armenian speech*; useless if you want *someone's Armenian voice*.

### Armenian G2P is available

eSpeak NG lists both Armenian voices in
[`docs/languages.md`](https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md):

| Code | Variant |
|---|---|
| `hy` | East Armenian |
| `hyw` | West Armenian |

`ai/armenian.py` exposes this as `armenian_ipa(text, dialect="hy")`. It is not
used for synthesis — Chatterbox consumes graphemes, not phonemes — but it is
what a fine-tuning pipeline would build a phoneme-aligned dataset with, and it
lets you inspect what the transliteration below is actually approximating.

### Armenian training data exists, and it is thin

Mozilla Common Voice Scripted Speech **25.0** (released 9 March 2026), `hy-AM`:

| Metric | Value |
|---|---|
| Clips | 38,398 |
| Recorded | 57.41 hours |
| **Validated** | **34.31 hours** |
| Speakers | 586 |

34 hours across 586 speakers is enough to fine-tune an existing multilingual
model. It is not enough to train one from scratch.

---

## What this app does: the transliteration bridge

Selecting `hy` transliterates Armenian script into the orthography of a language
the model *does* speak, and lets that language's own grapheme-to-phoneme run.

```
Armenian text  →  transliteration  →  Chatterbox (ru)  →  cloned voice
Բարև Ձեզ։         барев дзез.          native ru G2P       your timbre
```

### Why Russian and not Latin

Russian orthography is a much closer phonological fit for Eastern Armenian than
English spelling is:

| Armenian | IPA | Russian | English-Latin |
|---|---|---|---|
| ժ | /ʒ/ | ж | zh |
| շ | /ʃ/ | ш | sh |
| չ | /tʃʰ/ | ч | ch |
| ց | /tsʰ/ | ц | ts |
| խ | /χ/ | х | kh |
| ձ | /dz/ | дз | dz |
| ռ | /r/ (trilled) | р | rr |

Each of those is a single, unambiguous Russian letter with a regular
letter-to-sound mapping. The English column relies on digraphs an English G2P
will interpret through English phonotactics — `kh` frequently becomes /k/, `rr`
becomes an English approximant. Russian also handles the vowel inventory
(ը /ə/ → ы is imperfect but closer than any English vowel spelling).

The Latin path is still implemented (`transliterate(text, "en")`) because
Western Armenian speakers often prefer Latin transliteration conventions, and
because it is a useful comparison.

The implementation also handles the two Eastern Armenian word-initial
allophones — ե is /je/ and ո is /vo/ at word start — the ու and և digraphs, and
Armenian punctuation (`։ ՝ ՜ ՞ ՛ ֊`), which the target tokenizer would otherwise
render as noise.

### What you actually get

Honestly: **an Armenian-accented approximation in the cloned timbre.**

- The voice identity is preserved — that part is real, cloning is
  language-independent in this architecture.
- Pronunciation is approximately right for most consonants.
- **Stress is wrong.** Armenian stresses the final syllable; Russian does not,
  and the model will place stress by Russian rules.
- Consonant clusters Armenian permits and Russian does not are mangled.
- Aspiration contrasts (թ/տ, փ/պ, ք/կ) are largely lost — Russian does not have
  them.

It is good enough to be recognisably Armenian and useful for demos and personal
use. It is not good enough to ship to Armenian speakers as a product feature,
which is why it is flagged rather than presented as support.

### Turning it off

```bash
ENABLE_EXPERIMENTAL_ARMENIAN=false
```

`hy` then disappears from `GET /system/info`, from the UI language dropdowns,
and is rejected with `unsupported_language` by the API. Nothing else changes.

---

## The production path: fine-tuning

The only way to get real Armenian is to teach a model Armenian. The cheapest
credible route:

### 1. Data

| Source | Hours | Notes |
|---|---|---|
| Common Voice 25.0 `hy-AM` | 34.3 validated | Many speakers, variable quality |
| Public-domain Armenian audiobooks | varies | Needs forced alignment |
| Commissioned studio recordings | 5–20 | Best quality per hour; costs money |

Target **20–50 hours** of clean, transcribed Eastern Armenian across at least
50 speakers. Multi-speaker matters: a single-speaker fine-tune will collapse the
cloning ability you are trying to keep.

### 2. Tokenizer vocabulary extension

Chatterbox's `MTLTokenizer` has no Armenian graphemes. The Armenian block must
be added to the vocabulary and the T3 text-embedding matrix resized, with the
existing rows preserved. Community fine-tuning toolkits already implement this
step — [`gokhaneraslan/chatterbox-finetuning`](https://github.com/gokhaneraslan/chatterbox-finetuning)
advertises "smart vocabulary extension" plus LoRA support. **Not verified**: I
have not audited that toolkit; treat it as a starting point, not a dependency.

### 3. Training

- Fine-tune the **T3** (text → speech token) stage. Leave **S3Gen** alone — the
  vocoder is language-agnostic and retraining it risks the audio quality you
  already have.
- LoRA rather than full fine-tuning: far less VRAM, and it keeps the base
  model's 23 languages intact instead of catastrophically forgetting them.
- Hold out a multi-language eval set and check it every epoch. The failure mode
  to watch for is Armenian improving while German quietly degrades.

### 4. Wiring it in

**Correction, 12 September 2026:** this section originally described a
`CHATTERBOX_T3_MODEL` environment variable selecting a checkpoint path at
load time. That mechanism does not exist in `chatterbox-tts==0.1.7` (the
pinned PyPI release) — verified by installing it and inspecting
`ChatterboxMultilingualTTS.from_pretrained()` directly: it takes only
`device` and always downloads the `t3_mtl23ls_v2` checkpoint from Hugging
Face, with no parameter to point it at a local, fine-tuned file. The
env var and the `_resolve_multilingual_t3_model()` helper this section
referenced were written against upstream's `main` branch, which is ahead of
what has actually been published — the same gap documented in
[MODEL_RESEARCH.md](./MODEL_RESEARCH.md).

Wiring in an Armenian fine-tune therefore needs one small, real code change
in `ai/chatterbox_engine.py::_build_model()`: replace the `from_pretrained`
call for the `multilingual` branch with `ChatterboxMultilingualTTS.from_local(
ckpt_dir, device=self.device)` pointed at a local directory containing the
fine-tuned `t3_mtl23ls_v2.safetensors` alongside the checkpoint's other
required files (`ve.pt`, `s3gen.pt`, the tokenizer json, `conds.pt`) — `
from_local` is already part of this release's real, verified API. Everything
downstream of that — `ChatterboxEngine.info().languages`, which the API and
UI read their language list from — needs no change: add `hy` there and it
becomes a native language everywhere, and the experimental-Armenian warnings
disappear on their own since they are driven by the `experimental` flag on
the language option, not hardcoded in the UI.

### 5. Licensing

Chatterbox's weights are MIT, so a fine-tune can be released under whatever
terms you choose — **but the training data carries its own licence**. Common
Voice is CC-0, which is clean. MMS-TTS outputs are CC-BY-NC, so do **not**
distil from them into a model you intend to use commercially.

---

## Alternatives considered and rejected

| Approach | Verdict |
|---|---|
| **MMS-TTS `hye` alongside Chatterbox** | Real Armenian, but a fixed voice — it cannot be the *user's* voice, which is the entire product. Non-commercial licence too. Worth adding as a separate "Armenian (no cloning)" engine if plain Armenian TTS is wanted. |
| **eSpeak NG phonemes fed to Chatterbox** | The tokenizer expects graphemes in the target language's orthography, not IPA. Feeding IPA produces gibberish. Would require the tokenizer change from the fine-tuning path anyway. |
| **Cross-lingual XTTS-v2 hack** | Same problem, worse licence, no Armenian either. |
| **Translate Armenian → Russian, then speak Russian** | Produces fluent *Russian*. The user asked for Armenian. Rejected: transliteration at least preserves the Armenian words. |
| **Commercial API for Armenian only** | Defeats the point of a self-hosted open-source app, and sends the user's cloned voice to a third party. |
