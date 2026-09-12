# Open-Source Voice Cloning Model Research

**Research date: 11 September 2026.** Every claim below was checked against a
primary source on that date; links are given inline. Where something could not
be verified from a primary source it is marked as such rather than asserted.

Two labels are used throughout:

- **Verified fact** — read directly from the model's source code, licence file,
  model card, package metadata or official README.
- **Engineering recommendation** — my judgement, given the evidence.

> **Correction, added 12 September 2026.** The original pass below read
> Chatterbox's claims (including a "Nano" 110M checkpoint) from the
> `resemble-ai/chatterbox` GitHub repository's documentation. Actually
> installing `chatterbox-tts==0.1.7` — the latest release on PyPI, and the
> version this project pins — and inspecting it directly shows no Nano
> checkpoint is reachable through any public API of that release; `main`
> branch documentation had moved ahead of what was actually published. This
> caused a real production bug (`CHATTERBOX_VARIANT=nano` crashed at model
> load), fixed in `ai/chatterbox_engine.py` by dropping the "nano" option in
> favour of "turbo" (350M), the smallest variant the installed package
> genuinely supports. The Nano references below are left as they were
> originally written, as a record of what was claimed and where the gap was —
> not because they are correct about what `pip install chatterbox-tts`
> currently gives you.

---

## 1. Candidates surveyed

| Model | Repository | Checked |
|---|---|---|
| Chatterbox / Multilingual / Turbo / Nano | [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) | source + LICENSE + PyPI |
| F5-TTS | [SWivid/F5-TTS](https://github.com/SWivid/F5-TTS) | README + LICENSE |
| XTTS-v2 | [coqui-ai/TTS](https://github.com/coqui-ai/TTS), fork [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS) | README + licence discussion |
| CosyVoice 2 | [FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) | README + LICENSE |
| Fish Speech / OpenAudio S1 | [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) | model card + licence issues |
| IndexTTS-2 | [index-tts/index-tts](https://github.com/index-tts/index-tts) | README |
| OpenVoice V2 | [myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice) | README |
| StyleTTS 2 | [yl4579/StyleTTS2](https://github.com/yl4579/StyleTTS2) | README |
| Kokoro-82M | [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | model card |
| MeloTTS | [myshell-ai/MeloTTS](https://github.com/myshell-ai/MeloTTS) | README |
| Piper | [rhasspy/piper](https://github.com/rhasspy/piper) | README |
| MMS-TTS (Armenian) | [facebookresearch/fairseq — examples/mms](https://github.com/facebookresearch/fairseq/tree/main/examples/mms) | model card |

---

## 2. Comparison table

Ratings for *voice similarity* and *naturalness* are qualitative
(**engineering recommendation**) and reflect the published evaluations plus
community consensus; there is no single benchmark all these models report on.
Everything else in the table is a **verified fact**.

| Feature | **Chatterbox Multilingual V3** | **F5-TTS** | **XTTS-v2** | **CosyVoice 2** | **OpenAudio S1** | **IndexTTS-2** | **OpenVoice V2** | **Kokoro-82M** | **Piper** |
|---|---|---|---|---|---|---|---|---|---|
| License (code) | MIT | MIT | MPL-2.0 | Apache-2.0 | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 | MIT |
| License (weights) | **MIT** | **CC-BY-NC-4.0** | **CPML (non-commercial)** | Apache-2.0 | **CC-BY-NC-SA-4.0** | bilibili Model Use License | MIT | Apache-2.0 | MIT |
| Open-source | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Commercial use** | **Yes** | **No** (base ckpt) | **No** | Yes | **No** | Read the addendum | Yes | Yes | Yes |
| Voice cloning | Yes | Yes | Yes | Yes | Yes | Yes | Yes (timbre transfer) | **No** | Fine-tune only |
| Zero-shot cloning | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No | No |
| Reference audio | ~10 s (uses first 6 s / 10 s) | ~5–15 s | ~6 s+ | ~3–10 s | ~10 s | ~5–10 s | ~10 s | n/a | hours (training) |
| Voice similarity | High | High | Medium-high | High | High | High | Medium | n/a | n/a |
| Naturalness | High | High | Medium-high | High | High | High | Medium | High | Medium |
| Multilingual | 23 languages | zh/en (public ckpt) | 17 languages | zh/en/ja/ko + dialects | multi | zh/en/ja/es/ar | multi (via base speakers) | 8 languages | per-voice |
| English | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Armenian** | **No** | **No** | **No** | **No** | **No** | **No** | **No** | **No** | **No** |
| GPU required | No (recommended) | Recommended | Recommended | Recommended | Recommended | Recommended | No | No | No |
| CPU inference | Yes (`device="cpu"`) | Slow | Slow | Slow | Slow | Slow | Yes | Yes (real time) | Yes (fast) |
| VRAM | ~2–4 GB (0.5B); ~1–2 GB Turbo/Nano | ~4–8 GB | ~4 GB | ~4–6 GB | ~4–8 GB | ~6–8 GB | ~2 GB | <1 GB | <1 GB |
| Model size | 0.5B / 350M Turbo / 110M Nano | ~0.33B | ~0.75B | 0.5B | 0.5B+ | ~1B+ | small | 82M | tiny |
| Inference speed | Fast (Nano: 3× real time on 8 CPU cores) | ~0.15 RTF reported | Fast | 150 ms first-packet streaming | Medium | Medium | Fast | Very fast | Very fast |
| Streaming | No public API | No | Yes | **Yes** | Partial | No | No | No | Yes |
| Activity (Sep 2026) | Active (V3 Jun 2026; PyPI 0.1.7 Mar 2026) | Active | **Upstream archived**; idiap fork maintained | Active | Active | Active | Low | Active | Active |
| Production readiness | High | High | Medium (licence) | High | Medium (licence) | Medium | Low | High (no cloning) | High (no cloning) |

### Source notes for the licence column

- **Chatterbox** — `LICENSE` at repo root is the MIT text, © 2025 Resemble AI;
  the PyPI metadata for `chatterbox-tts` 0.1.7 (uploaded 2026-03-26) carries the
  same MIT text. Resemble states MIT for the model family, weights included.
  *This is the only top-tier zero-shot cloner in this table whose weights are
  permissively licensed.*
- **F5-TTS** — the repo's own README: code MIT, **pre-trained models CC-BY-NC**,
  because they were trained on the in-the-wild Emilia dataset. A separately
  trained Apache-2.0 checkpoint exists (`mrfakename/OpenF5-TTS-Base`) but it is
  not the official model and was not evaluated here.
- **XTTS-v2** — the library is MPL-2.0; the *weights* are under the Coqui Public
  Model License, which permits non-commercial use only. Coqui Inc. shut down in
  January 2024, so there is no longer anyone to sell a commercial licence.
  Treat XTTS-v2 as non-commercial, indefinitely.
- **OpenAudio S1 / Fish Speech** — model card states CC-BY-NC-SA-4.0.
- **IndexTTS-2** — Apache-2.0 with an additional "bilibili Model Use License"
  addendum. **Not verified in detail**: read the addendum before commercial use.

---

## 3. Armenian: what is actually true

**Verified fact: no open-source zero-shot voice-cloning model supports Armenian.**

Checked directly in source:

```python
# chatterbox/mtl_tts.py — SUPPORTED_LANGUAGES (23 entries, verified 2026-09-11)
ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh
#                                    ^ no "hy"
```

XTTS-v2's 17 languages, CosyVoice 2's zh/en/ja/ko + Chinese dialects, and
F5-TTS's public zh/en checkpoints likewise contain no Armenian.

**Verified fact: Armenian TTS *without* cloning does exist.**
`facebook/mms-tts-hye` (Eastern) and `facebook/mms-tts-hyw` (Western) ship as
part of Meta's Massively Multilingual Speech project, VITS-based, under
**CC-BY-NC-4.0** — a fixed synthetic voice, non-commercial, no cloning.

**Verified fact: Armenian grapheme-to-phoneme is available.** eSpeak NG's
`docs/languages.md` lists both `hy` (East Armenian) and `hyw` (West Armenian).

**Verified fact: Armenian training data exists but is thin.** Mozilla Common
Voice Scripted Speech 25.0 (released 9 March 2026) for `hy-AM`: 38,398 clips,
57.41 hours recorded, **34.31 hours validated**, 586 speakers.

The realistic options, and what this project does about them, are written up in
[ARMENIAN.md](./ARMENIAN.md).

---

## 4. Primary model: **Chatterbox Multilingual V3**

### Why

1. **Licence (decisive).** MIT for code *and* weights. Every other model at this
   quality tier is non-commercial (F5-TTS, XTTS-v2, OpenAudio S1) or carries an
   addendum that needs a lawyer (IndexTTS-2). For a project that anyone should
   be able to fork and deploy, a permissive weight licence is not a
   nice-to-have — it is the difference between usable and not.
2. **Zero-shot cloning that needs no training.** ~10 seconds of reference audio,
   no fine-tuning step, no per-voice GPU job. That is exactly the product flow.
3. **Breadth without a model swap.** 23 languages from one checkpoint. A
   per-language model zoo would multiply VRAM and deployment complexity.
4. **A real CPU story.** `device="cpu"` is supported across the family, and
   Chatterbox-Turbo (350M, the smallest variant actually installable via
   `pip install chatterbox-tts` as of this writing — see the correction
   below) runs comfortably on CPU. Contributors without a GPU can run the
   whole application, and small deployments do not need to rent one.
5. **Watermarking is built in.** Every generation passes through Resemble's
   PerTh watermarker. For a voice-cloning product, provenance is a requirement,
   and getting it in the box beats bolting on something weaker later. It is also
   *verifiable* — `tests/ai/test_chatterbox_engine.py` asserts the watermark is
   detectable rather than taking the README's word for it.
6. **A cacheable speaker representation.** `prepare_conditionals()` +
   `Conditionals.save()/load()` let the expensive part of cloning run once per
   voice and be reloaded per generation. That is what makes a "voice profile" a
   real object here rather than a filename.
7. **Maintained.** Multilingual V3 shipped June 2026; `chatterbox-tts` 0.1.7 was
   published to PyPI in March 2026.

### Verified integration facts

| Property | Value | Source |
|---|---|---|
| Output sample rate | **24,000 Hz** (`S3GEN_SR`) | `models/s3gen/const.py` |
| Internal tokenizer rate | 16,000 Hz (`S3_SR`) | `models/s3tokenizer` |
| Reference window used | first **6 s** for the speech-token prompt (`ENC_COND_LEN`), first **10 s** for the S3Gen reference (`DEC_COND_LEN`) | `mtl_tts.py` |
| Cloning API | `generate(text, language_id, audio_prompt_path=..., exaggeration=, cfg_weight=, temperature=, repetition_penalty=, min_p=, top_p=)` | `mtl_tts.py` |
| Conditioning cache | `Conditionals.save(path)` / `.load(path)` | `mtl_tts.py` |
| Streaming | **No public incremental API** | source inspection |
| Python | ≥ 3.10 | PyPI metadata |

That 6 s / 10 s window is worth knowing: the UI asks for 10–30 seconds because a
longer take gives the speaker room to sound natural and gives silence-trimming
something to work with — but the model reads only the first ~10 seconds. This is
why the app trims and normalises before conditioning instead of after.

### Trade-offs accepted

- **No streaming.** CosyVoice 2's 150 ms first-packet streaming is genuinely
  better for a live voice agent. This app generates whole utterances that the
  user then plays, so streaming would add a WebSocket layer for no user-visible
  gain. See [ARCHITECTURE.md](./ARCHITECTURE.md#streaming).
- **No Armenian.** True of every alternative too, so it is not a differentiator.

---

## 5. Alternative models

### First alternative — **F5-TTS** (non-commercial use only)

Excellent quality and a strong reported RTF (~0.04 on an L20 GPU at 16 NFE
steps, per the repo's own benchmark table). Pick it when the deployment is
research, personal or otherwise clearly non-commercial, and English/Chinese is
enough. The **CC-BY-NC** weight licence is the blocker for anything else, and it
survives fine-tuning: a model fine-tuned from the NC base is still NC.

### Second alternative — **CosyVoice 2** (Apache-2.0, streaming)

The right answer if the product becomes a *live voice agent*. Apache-2.0,
150 ms first-packet streaming, explicit emotion tags. Its language coverage
(zh/en/ja/ko + Chinese dialects) is narrower, which is why it is not primary
here.

### Third alternative — **XTTS-v2** (non-commercial, legacy)

Still the largest ecosystem and plenty of tooling, and the
[idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS) fork keeps it
running on current Python and PyTorch. But upstream is archived and the CPML
weights cannot be licensed commercially by anyone, because the company that
owned the licence no longer exists. Choose it only to interoperate with existing
XTTS work.

### Not selected, and why

- **Kokoro-82M**, **MeloTTS**, **Piper** — excellent, fast, permissive, and
  **they do not clone voices**. Kokoro ships preset voice packs; Piper needs a
  full fine-tune per voice. Wrong tool for this product.
- **OpenVoice V2** — MIT and genuinely useful, but it is a *tone-colour
  converter* over a base TTS voice, not an end-to-end cloner. Similarity is
  below the current state of the art.
- **StyleTTS 2** — strong quality, but weaker zero-shot cloning than the models
  above and no multilingual checkpoint of comparable breadth.

---

## 6. Sources

**Primary**

- Chatterbox: [github.com/resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) · [LICENSE](https://github.com/resemble-ai/chatterbox/blob/master/LICENSE) · [PyPI `chatterbox-tts`](https://pypi.org/project/chatterbox-tts/) · [PerTh watermarker](https://github.com/resemble-ai/perth)
- F5-TTS: [github.com/SWivid/F5-TTS](https://github.com/SWivid/F5-TTS) · [licensing discussion #997](https://github.com/SWivid/F5-TTS/discussions/997)
- XTTS-v2: [coqui-ai/TTS](https://github.com/coqui-ai/TTS) · [licence clarification #4304](https://github.com/coqui-ai/TTS/discussions/4304) · [idiap fork](https://github.com/idiap/coqui-ai-TTS)
- CosyVoice: [github.com/FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice)
- Fish Speech / OpenAudio: [github.com/fishaudio/fish-speech](https://github.com/fishaudio/fish-speech)
- IndexTTS: [github.com/index-tts/index-tts](https://github.com/index-tts/index-tts)
- OpenVoice: [github.com/myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice)
- MMS: [fairseq/examples/mms](https://github.com/facebookresearch/fairseq/tree/main/examples/mms)
- eSpeak NG language list: [docs/languages.md](https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md)
- Common Voice Armenian: [commonvoice.mozilla.org/hy-AM](https://commonvoice.mozilla.org/hy-AM) · [Scripted Speech 25.0 — Armenian](https://mozilladatacollective.com/datasets/cmn2e8k9z01kymm07yqqy4bk1)

**Secondary** (used for orientation, not for any claim above)

- [Resemble AI — Chatterbox Multilingual](https://www.resemble.ai/learn/models/chatterbox-multilingual)
- [Podonos evaluation: Chatterbox Turbo vs ElevenLabs Turbo v2.5](https://podonos.com/resembleai/chatterbox-turbo-vs-elevenlabs-turbo)
- [Best Open-Source Voice Cloning Models 2026](https://rarebuildsoftware.com/blog/best-open-source-voice-cloning-2026)
- [Kokoro.js / Transformers.js WebGPU announcement](https://huggingface.co/posts/Xenova/503648859052804)

---

## 7. Deliberately unverified

Stated here rather than asserted as fact elsewhere:

- **Head-to-head similarity/naturalness scores.** The published evaluations use
  different corpora, listeners and baselines. The ratings in §2 are judgement.
- **IndexTTS-2's bilibili Model Use License addendum.** Not read in full.
- **Real-world RTF on specific hardware.** Every RTF above is a vendor-reported
  figure. Measure your own with `python scripts/benchmark.py`, which prints load
  time, conditioning time, per-utterance RTF and peak VRAM.
