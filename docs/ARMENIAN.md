# Armenian Language Support

**Research date: 11 September 2026. Updated: 12 September 2026 (default-voice
TTS research for the Voice Story Studio work — see the new section below).**

## The short version

> **Native Armenian voice *cloning*: none.**
> No open-source zero-shot voice-cloning model supports Armenian, as of this date.
>
> **Native Armenian *default-voice* TTS: yes** — `espeak-ng`'s built-in `hy`
> (Eastern Armenian) voice, real synthesis with correct phonetics, honestly
> labelled as a "Classic" (formant, non-neural) voice rather than passed off as
> natural neural speech. See "Default-voice Armenian TTS" below for why this
> was chosen over the neural alternatives that were evaluated and rejected.
>
> **Possible experimental Armenian *cloning* support: yes, and it ships in this
> app** — behind a flag, labelled as experimental everywhere it appears.

Those two statements about cloning are kept strictly separate throughout the
product: in the API (`native: false, experimental: true` on the language
option), in the UI (an "Experimental language" warning before you generate,
and an "Experimental output" banner after), and on the stored record
(`experimental = true` on the generation row). The default-voice path is a
separate, non-experimental capability — it does not clone anyone's voice, it
just speaks Armenian in a fixed synthetic voice, and it is labelled by quality
tier ("Classic"), not by an experimental/production distinction.

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
use. It is not good enough to ship to Armenian speakers as a product feature.

### It is no longer in the speech path

This bridge used to be reachable through `POST /api/v1/speech` behind an
`ENABLE_EXPERIMENTAL_ARMENIAN` flag. Both the bridge and the flag were removed
from that path: espeak-ng's `hy`/`hyw` voices speak Armenian *natively* and the
UI offers them, so the transliteration was strictly worse than the supported
option while still being one API call away. Asking a cloned voice for Armenian
now returns a plain refusal — *"This voice cannot speak Հայերեն. Please choose
another voice."* — and `hy` stays in `GET /system/info` with
`supportsClonedVoice: false`, which is what the UI filters on.

`armenian_ipa()` and `transliterate()` remain in `ai/armenian.py` as the
starting point for the fine-tuning work described below, and so the quality of
such a bridge can be inspected directly.

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

---

## Default-voice Armenian TTS (12 September 2026)

The Voice Story Studio work needed an Armenian *default voice* — a fixed,
non-cloned voice a user can pick for narration without ever recording
themselves, distinct from the voice-cloning question above. This is a
different, easier problem (no cloning required), but it still needs a real,
correctly-licensed model — not a placeholder. Verified via a GitHub
Actions runner (this sandbox cannot reach `huggingface.co` directly), every
candidate below was checked against the model's own stated license, not
assumed from how the model is described elsewhere.

### Candidates evaluated

| Option | Quality | License | Verdict |
|---|---|---|---|
| **`espeak-ng` built-in `hy`/`hyw` voices** | Formant/rule-based — robotic but linguistically correct | GPL-3.0 (the espeak-ng binary), but **already a runtime dependency** of `backend/Dockerfile.render` (used via subprocess, same pattern as `ffmpeg`) — shipping its Armenian voice adds no *new* license surface | **Chosen.** Zero new licensing risk, genuinely native Armenian phonetics for both Eastern (`hy`) and Western (`hyw`) Armenian, works entirely offline/CPU. Must be labelled "Classic" quality in the UI — it sounds mechanical, and claiming otherwise would violate the "do not fake voice availability" requirement in spirit. |
| **Piper `hy_AM-gor-medium`** ([`rhasspy/piper-voices`](https://huggingface.co/rhasspy/piper-voices)) | Neural (VITS/ONNX), natural-sounding, ~63MB, single speaker | The collection's blanket repo README says `license: mit`, but this specific voice's own `MODEL_CARD` states its training dataset (`davit312/piper-TTS-Armenian`) is **GPL-2.0** — confirmed by fetching the file directly. The blanket "mit" header covers Piper's own code/infra, not this voice's data. | **Rejected for now.** Real and good-quality, but GPL-2.0-encumbered in a way that is not obviously safe to embed in a product with different licensing goals. Documented here in case the product's licensing stance changes later — do not silently upgrade to this without re-deciding the tradeoff. |
| **`facebook/mms-tts-hye`** (Eastern Armenian) | Neural (VITS), single speaker | CC-BY-NC-4.0 (non-commercial) — corroborated by the sibling `facebook/mms-tts-hyw` being independently tagged `license:cc-by-nc-4.0` in Hugging Face's own model index (the `hye` repo's README fetch was blocked/gated at research time) | **Rejected**, same reason as the original research above: non-commercial clause is incompatible with a product that might ever be monetized. |
| **`ArthurYeghinyan/armenian-speecht5-sota`** | Neural (SpeechT5 + HiFi-GAN) | **Apache-2.0** — genuinely permissive | **Rejected on quality grounds, not license.** This is the only fully-permissive neural option found. Its own model card reports a **66.67% word error rate** against Whisper-large-v3 (vs. 43.04% WER on real human recordings) while simultaneously claiming to "surpass human acoustic clarity" — a self-contradictory, hype-driven presentation from a single-contributor upload with no independent verification available. A ~2-in-3 word error rate is not shippable quality. Worth re-evaluating later if this improves or a comparable Apache/MIT model appears, but not by trusting the README — by actually listening to output. |
| **`Anadilorg/Anadil_Armenian_TTS`** (LoRA on `openbmb/VoxCPM2`) | Unknown — untested | MIT | **Rejected**, not evaluated further: built on a large conversational base model almost certainly too heavy for the existing CPU-only Render Starter instance already running Chatterbox, and tagged for Western Armenian/Turkey rather than the Eastern Armenian (Armenia) this app targets. |

### Decision

Ship `espeak-ng`'s Armenian voice as the Armenian default voice, labelled
"Classic" in the capability model and UI (see the voice capability schema
added for the Voice Story Studio feature). Do not ship the Piper or MMS-TTS
options without a separate, explicit decision given their license
restrictions. Revisit the SpeechT5 option if a listening test (not just the
README) confirms usable quality, or if a comparably-licensed model with
verified quality appears later.

---

## Alternatives considered and rejected

| Approach | Verdict |
|---|---|
| **MMS-TTS `hye` alongside Chatterbox** | Real Armenian, but a fixed voice — it cannot be the *user's* voice, which is the entire product. Non-commercial licence too. Worth adding as a separate "Armenian (no cloning)" engine if plain Armenian TTS is wanted. |
| **eSpeak NG phonemes fed to Chatterbox** | The tokenizer expects graphemes in the target language's orthography, not IPA. Feeding IPA produces gibberish. Would require the tokenizer change from the fine-tuning path anyway. |
| **Cross-lingual XTTS-v2 hack** | Same problem, worse licence, no Armenian either. |
| **Translate Armenian → Russian, then speak Russian** | Produces fluent *Russian*. The user asked for Armenian. Rejected: transliteration at least preserves the Armenian words. |
| **Commercial API for Armenian only** | Defeats the point of a self-hosted open-source app, and sends the user's cloned voice to a third party. |
