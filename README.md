# Voice Story Studio

Open-source voice cloning and story narration as a web application. Clone
your own voice from a 10–30 second recording, or skip that entirely and use a
built-in default voice. Write text or generate an original fairy tale in
English or Armenian, then narrate it — optionally with a background ambience
mixed under the narration. Everything runs on your own backend; the only
third-party call is to the Anthropic API, and only for fairy-tale text
generation.

**Voice cloning model:** [Chatterbox Multilingual V3](https://github.com/resemble-ai/chatterbox)
by Resemble AI — MIT-licensed **code *and* weights**, 23 languages, zero-shot
cloning from ~10 seconds of audio, neural watermarking built in.

**Default voices:** [espeak-ng](https://github.com/espeak-ng/espeak-ng)
(GPL-3.0, already a runtime dependency — see [Features](#features)) — real,
native English and Armenian synthesis, no recording required, honestly
labelled "Classic" quality rather than passed off as natural neural speech.

**Story generation:** [Claude](https://www.anthropic.com/claude) (Opus 5) via
the Anthropic API — generates fairy tales natively in the target language.

```
                                        ┌─▶ VoiceCloningEngine ─▶ PyTorch (CUDA/CPU/MPS)
Browser ──HTTPS──▶ FastAPI ──┬─ speech ─┤
 record/type         REST    │          └─▶ espeak-ng (default voices, en + hy)
 playback                    │                    │
                              └─ stories ─▶ Anthropic API (Claude)
                                                   │
                                     ffmpeg mixes narration + ambience
                                                   │
                                        SQLite + filesystem
```

---

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Why this model](#why-this-model)
- [Armenian](#armenian)
- [Quick start](#quick-start)
- [Local development](#local-development)
- [Docker](#docker)
- [GPU setup](#gpu-setup)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [API](#api)
- [Testing](#testing)
- [Security](#security)
- [Voice-cloning safety](#voice-cloning-safety)
- [Known limitations](#known-limitations)
- [Deployment](#deployment)
- [Roadmap](#roadmap)

---

## Features

- **Two voice sources.** *My Cloned Voice* (Chatterbox, requires a recording)
  or *Default Voice* (espeak-ng, no recording — English and Armenian).
- **Two modes.** *Text to Speech* for text you write yourself, and
  *Create Fairy Tale* — describe characters, an idea, age group, length and
  tone, and Claude generates an original story you can edit before narrating.
- **English and Armenian.** Manual text, fairy-tale generation, and default-voice
  TTS all genuinely support both. Cloned-voice narration does not yet support
  Armenian — the UI disables that specific combination and explains why,
  rather than allowing a request that fails obscurely (see
  [Armenian](#armenian)).
- **Background ambience.** Optional, mixed under the narration via ffmpeg —
  currently *None* and *Mystical* (a self-generated, license-free synth pad;
  see `scripts/generate_ambience.py`). The narration always stays louder and
  clearer than the background, whatever the volume slider is set to.
- **Long-text-safe narration.** Fairy tales are chunked at paragraph/sentence
  boundaries — never mid-word — synthesized per chunk, and concatenated, so a
  long story doesn't risk a single giant, fragile TTS call.
- Everything from the original voice-cloning app is unchanged: recording,
  upload, consent, voice management, playback, download, watermarking.

### Support matrix

| | English | Armenian |
|---|---|---|
| Manual text input | ✅ | ✅ |
| Fairy-tale generation | ✅ (native) | ✅ (native, not translated) |
| Default-voice TTS | ✅ (espeak-ng) | ✅ (espeak-ng, native phonetics) |
| Voice cloning (create a voice) | ✅ | ⚠️ experimental only ([docs/ARMENIAN.md](docs/ARMENIAN.md)) |
| Cloned-voice TTS | ✅ | ❌ disabled in the UI — see [Armenian](#armenian) |
| Background ambience (Mystical) | ✅ | ✅ |

"✅" means genuinely supported and tested, not merely accepted by the API.
Nothing in this table is marked supported based on what a model claims to do —
see [Armenian](#armenian) and [docs/ARMENIAN.md](docs/ARMENIAN.md) for what was
actually verified and why the one ❌ exists.

---

## Screenshots

> _Placeholder — add captures of the screens here._

| Screen | Path |
|---|---|
| Home — Voice Story Studio, two main modes | `/` |
| Text to Speech — language, voice source, voice, background | `/generate` |
| Create Fairy Tale — story params, editable text, narration | `/fairy-tale` |
| Create Voice — record or upload, guidance, consent | `/voices/new` |
| Generated Audio — player, RTF, download | `/history` |

---

## Why this model

Full research, comparison table and sources: **[docs/MODEL_RESEARCH.md](docs/MODEL_RESEARCH.md)**
(researched 11 September 2026, every claim linked to a primary source).

The short version — the licence decided it:

| Model | Weights licence | Commercial use | Zero-shot cloning | Languages |
|---|---|---|---|---|
| **Chatterbox Multilingual V3** | **MIT** | **Yes** | Yes | 23 |
| F5-TTS | CC-BY-NC-4.0 | No | Yes | zh/en |
| XTTS-v2 | CPML | No (and unlicensable — Coqui shut down) | Yes | 17 |
| OpenAudio S1 | CC-BY-NC-SA-4.0 | No | Yes | multi |
| CosyVoice 2 | Apache-2.0 | Yes | Yes | zh/en/ja/ko |
| Kokoro / Piper / MeloTTS | Permissive | Yes | **No cloning** | varies |

Chatterbox is the only model at this quality tier whose *weights* are
permissively licensed. Alongside that: 23 languages from one checkpoint, real
CPU support (Turbo, the smallest variant this package actually ships,
runs comfortably in real time on a few cores), a cacheable
speaker representation, and PerTh watermarking in the box — which
`tests/ai/` verifies rather than assumes.

**Alternatives:** F5-TTS for non-commercial work; CosyVoice 2 if you need
streaming for a live voice agent. Swapping either in means one new file in
`ai/` and one environment variable — see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#adding-another-model).

---

## Armenian

Two separate questions, two separate answers:

> **Armenian *default-voice* TTS (no cloning): yes, genuinely.** The Armenian
> default voice uses espeak-ng's built-in `hy` (Eastern Armenian) and `hyw`
> (Western Armenian) voices — real synthesis, correct native phonetics,
> honestly labelled "Classic" (formant, not neural) quality. This is what the
> Voice Story Studio UI uses for Armenian narration, and it is not gated
> behind any flag.
>
> **Native Armenian voice *cloning*: none.** No open-source zero-shot
> voice-cloning model supports Armenian, verified as of 11 September 2026.
> The UI does not offer "My Cloned Voice" + Armenian at all — it disables that
> combination with an explanation, rather than allowing a request through to
> an obscure backend error.
>
> **An experimental cloned-voice approximation exists behind a flag, for the
> raw API only.** Armenian script can be transliterated into Russian
> orthography (a much closer phonological fit than Latin) and spoken in your
> cloned voice via `POST /api/v1/speech`. It is labelled experimental in the
> API and on the stored record, but the Voice Story Studio UI does not expose
> it — see the reasoning above.

Expect a recognisable Armenian accent with wrong stress placement from the
experimental path — not real Armenian TTS. What was verified for both
questions (why espeak-ng over Piper's GPL-2.0 voice or Meta's non-commercial
MMS-TTS; why Russian and not Latin for the transliteration bridge; the
fine-tuning path to real cloning support): **[docs/ARMENIAN.md](docs/ARMENIAN.md)**.

Disable the experimental cloned-voice bridge (API-only; the UI never exposed
it) with `ENABLE_EXPERIMENTAL_ARMENIAN=false`.

---

## Quick start

### No GPU, no model download — the mock engine

The fastest way to see the whole application working. `VOICE_ENGINE=mock`
implements the full engine contract with tones instead of speech, so every
screen, endpoint and test runs in seconds on any laptop.

```bash
git clone <repository-url> && cd voice-clone

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-ci.txt          # no torch, no weights
VOICE_ENGINE=mock uvicorn app.main:app --reload

# Frontend, in a second terminal
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open **http://localhost:3000**.

### With the real model

```bash
cd backend
pip install -r requirements.txt             # pulls torch + chatterbox-tts
python ../scripts/download_model.py         # optional: pre-fetch weights
uvicorn app.main:app --reload
```

On CPU, set `CHATTERBOX_VARIANT=turbo` first — the 0.5B multilingual model on CPU
takes minutes per utterance.

---

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

→ API at http://localhost:8000, docs at http://localhost:8000/docs

**Requires `ffmpeg` on `PATH`.** Browsers record WebM/Opus (Chrome, Firefox) or
MP4/AAC (Safari), neither of which libsndfile can read. Without ffmpeg the app
falls back to libsndfile and only accepts WAV/FLAC/OGG.

```bash
sudo apt install ffmpeg libsndfile1     # Debian/Ubuntu
brew install ffmpeg                     # macOS
choco install ffmpeg                    # Windows
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

→ http://localhost:3000

`.env.local` holds one variable:

```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
```

It is **inlined at build time**, so changing it requires a rebuild. No component
ever hardcodes a backend URL — everything goes through `src/services/apiClient.ts`.

### Make targets

```bash
make help              # list everything
make install           # backend venv + npm install
make backend           # uvicorn --reload
make frontend          # next dev
make test              # backend pytest + frontend vitest
make e2e               # Playwright
make lint              # ruff + eslint + tsc
make benchmark         # RTF, VRAM, load times
```

---

## Docker

```bash
cp .env.example .env
docker compose up --build
```

→ frontend http://localhost:3000 · API http://localhost:8000

The CPU stack defaults to `CHATTERBOX_VARIANT=turbo`. Model weights are **not**
baked into the image — they land in a named `hf-cache` volume, so rebuilding
does not re-download gigabytes.

### GPU

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

Requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
The overlay switches to CUDA torch, the multilingual model, and
`PRELOAD_MODEL=true`.

Verify the GPU is visible:

```bash
docker compose exec api python -c "import torch; print(torch.cuda.get_device_name(0))"
```

---

## GPU setup

Install a CUDA build of torch **before** the requirements file, or pip will pull
the default wheel:

```bash
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r backend/requirements.txt
```

Then `DEVICE=cuda` (or leave `DEVICE=auto`, which prefers CUDA → MPS → CPU).

Apple Silicon: `DEVICE=mps`. CPU-only: `DEVICE=cpu` with `CHATTERBOX_VARIANT=turbo`.

Hardware recommendations and how to measure RTF on your own machine:
**[docs/PERFORMANCE.md](docs/PERFORMANCE.md)**.

---

## Configuration

Full list with comments in [`.env.example`](.env.example). The ones that matter:

| Variable | Default | Notes |
|---|---|---|
| `VOICE_ENGINE` | `chatterbox` | or `mock` for development and CI |
| `CHATTERBOX_VARIANT` | `multilingual` | `multilingual` \| `english` \| `turbo` (no `nano` -- see below) |
| `DEVICE` | `auto` | `cuda` \| `cpu` \| `mps` \| `auto` |
| `PRELOAD_MODEL` | `false` | Load weights at boot instead of on first request |
| `CORS_ORIGINS` | `http://localhost:3000` | Exact origins. Never `*` |
| `MAX_UPLOAD_BYTES` | 25 MiB | |
| `MAX_TEXT_CHARS` | 2000 | Caps worst-case request latency |
| `REQUIRE_CONSENT` | `true` | Do not disable in production |
| `RATE_LIMIT_ENABLED` | `true` | |
| `ENABLE_EXPERIMENTAL_ARMENIAN` | `true` | API-only; the UI never exposes cloned+Armenian regardless |
| `DATABASE_URL` | `sqlite:///storage/voice_studio.db` | Any SQLAlchemy URL |
| `ANTHROPIC_API_KEY` | unset | Required for "Create Fairy Tale"; unset disables just that feature |
| `STORY_MODEL` | `claude-opus-5` | |
| `RATE_LIMIT_STORY_PER_HOUR` | `30` | |

---

## Project structure

```
voice-clone/
├── ai/                          model-agnostic inference layer (no web deps)
│   ├── engine.py                VoiceCloningEngine contract, VoiceProfile
│   ├── chatterbox_engine.py     the real (cloning) implementation
│   ├── espeak_engine.py         default-voice synthesis (English + Armenian)
│   ├── mock_engine.py           dependency-free test double
│   ├── audio_processing.py      sniff → decode → validate → trim → normalise
│   ├── audio_mix.py             narration + background-ambience mixing (ffmpeg)
│   ├── text_chunking.py         paragraph/sentence-safe chunking for long text
│   ├── model_loader.py          device selection, weight download
│   ├── armenian.py              experimental transliteration bridge
│   └── registry.py              cloning-engine singleton
│
├── backend/
│   ├── app/
│   │   ├── main.py              app factory, middleware, health, default-voice bootstrap
│   │   ├── api/v1/              voices · speech · generations · stories · system
│   │   ├── assets/ambience/     self-generated background tracks (mystical.wav)
│   │   ├── core/                config · errors · security · rate limiting
│   │   ├── db/                  engine, session, base
│   │   ├── models/              SQLAlchemy: Voice, Generation, AuditEvent
│   │   ├── schemas/             Pydantic request/response (camelCase)
│   │   ├── repositories/        data access
│   │   └── services/            voice · speech · story · language · default_voices · storage
│   ├── tests/{unit,api,integration,ai}/
│   ├── requirements.txt         full stack
│   ├── requirements-ci.txt      no torch — what CI installs
│   └── Dockerfile               cpu + gpu targets
│
├── frontend/
│   ├── src/
│   │   ├── app/                 App Router pages, incl. fairy-tale/
│   │   ├── components/          shared UI
│   │   ├── features/            voices/ · speech/ · story/
│   │   ├── hooks/               useRecorder · useVoices · useDefaultVoices · useSystemInfo · …
│   │   ├── services/            the only code that knows the API exists
│   │   ├── types/               API contract types
│   │   └── utils/               format · audio · validation · voiceCapability
│   ├── e2e/                     Playwright
│   └── Dockerfile
│
├── docs/                        research, architecture, API, security, …
├── scripts/                     download_model.py · benchmark.py · generate_ambience.py
├── storage/                     voices/ · generated/ (gitignored)
└── docker-compose{,.gpu}.yml
```

`ai/` sits outside `backend/` on purpose: it has no web dependencies, so a
standalone GPU worker can import it later without dragging FastAPI along.

---

## API

Full reference: **[docs/API.md](docs/API.md)** · Interactive: `/docs`

```http
POST   /api/v1/voices                       create a voice profile (multipart)
GET    /api/v1/voices                       list your own voices
GET    /api/v1/voices/defaults              list the built-in default voices
GET    /api/v1/voices/{id}                  get one
GET    /api/v1/voices/{id}/sample           reference audio
DELETE /api/v1/voices/{id}                  delete voice + all its generations

POST   /api/v1/speech                       generate speech (cloned or default voice,
                                             optional backgroundSound/backgroundVolume)
GET    /api/v1/generations                  list (filter with ?voiceId=)
GET    /api/v1/generations/{id}             get one
GET    /api/v1/generations/{id}/audio       stream (Range) or ?download=true
DELETE /api/v1/generations/{id}             delete

POST   /api/v1/stories/generate             generate a fairy tale (English or Armenian)

GET    /api/v1/system/info                  engine, languages, limits
GET    /health                              liveness
```

`POST /speech` returns JSON with an `audioUrl` rather than raw bytes, so history,
provenance metadata and byte-range seeking all work — reasoning in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#json-with-audiourl-not-raw-audiowav).
Default voices are ordinary `Voice` rows (`source: "system"`, `engine:
"espeak-ng"`) so `POST /speech` needs no separate "default" endpoint — pass
one of their IDs as `voiceId` exactly like a cloned voice. They are excluded
from `GET /voices` and its pagination/quota (that endpoint is your own voices
only); fetch them from `GET /voices/defaults`.

`POST /stories/generate` is text-only: it returns `{title, text, language,
wordCount}`. Narrating the result — or any manually-typed text — is the same
`POST /speech` call, no separate "narrate" endpoint.

---

## Testing

```bash
# Backend — 153 tests, mock engine + real espeak-ng, no torch weights, ~16 s
cd backend && pytest

# By layer
pytest tests/unit tests/api tests/integration

# Real cloning model — opt-in, downloads weights
pytest -m ai tests/ai

# Frontend — 62 unit tests
cd frontend && npm run test:run

# End-to-end — 10 tests, desktop + mobile viewports
npm run test:e2e
```

| Suite | What it covers |
|---|---|
| `tests/unit` | Path traversal, filename sanitisation, audio validation, container sniffing, silence trimming, rate limiting, Armenian transliteration, the engine contract |
| `tests/api` | Every endpoint: consent gating, bad formats, oversized uploads, quotas, empty/overlong text, unknown IDs, byte ranges, pagination |
| `tests/integration` | The full journey; conditioning-cache reuse; cascade delete; audit trail; rate limits end to end |
| `tests/ai` | Real Chatterbox: language set, conditioning round trip, synthesis, **watermark detectability**, RTF |
| `frontend` (Vitest) | Formatting, file validation, the API client's error handling, the audio player, the dropzone, the generate form |
| `e2e` (Playwright) | Create → generate → play → download → delete, real `MediaRecorder` capture, the Armenian labelling path, API-failure handling, phone-width layout |

CI never loads a model: `requirements-ci.txt` omits torch entirely and
everything runs against `MockEngine`. The real-model suite is a separate,
manually triggered workflow.

---

## Security

Details: **[docs/SECURITY.md](docs/SECURITY.md)**

Implemented: chunked uploads with an early size abort · magic-byte container
sniffing (the extension is never trusted) · out-of-process ffmpeg decoding ·
three independent layers of path-traversal defence · audio served through the
API rather than a static mount · explicit CORS origins · token-bucket rate
limiting that does not trust `X-Forwarded-For` · text and control-parameter
bounds · a uniform error envelope that never leaks internals · non-root
containers.

> **No authentication.** The MVP is single-tenant: anyone who can reach the API
> owns every voice on it. Do not expose it directly to the internet — put it
> behind a VPN or an authenticating proxy until Phase 2.

---

## Voice-cloning safety

Details: **[docs/SECURITY.md](docs/SECURITY.md#part-2--voice-cloning-safety)**

- **Consent is enforced server-side.** `consent=true` is required; the API
  returns `403 consent_required` regardless of what the UI does, and the exact
  statement text and timestamp are stored on the voice record.
- **Deletion is complete.** Deleting a voice removes the reference audio, the
  speaker conditioning, the metadata *and every clip generated from it*.
  Verified by test.
- **Every generation is watermarked** with Resemble PerTh — and the test suite
  asserts the watermark is actually detectable rather than trusting the README.
- **Audit trail** of creation, generation and deletion, with the client address
  stored as a salted hash. Survives voice deletion.
- **Experimental output is labelled** wherever it appears.

Not built, deliberately: real-time impersonation tooling, bulk cloning from
scraped audio, or anything designed to remove a watermark.

---

## Known limitations

| Limitation | Detail |
|---|---|
| **No authentication** | Single-tenant. Phase 2. |
| **No native Armenian** | No open model has it. The bridge is an approximation — see [docs/ARMENIAN.md](docs/ARMENIAN.md) |
| **No streaming** | Chatterbox exposes no incremental API; whole utterances only |
| **Synchronous generation** | Correct at current RTF; the queue trigger points are written down |
| **Single GPU** | One worker, one lock. Multi-GPU needs the PostgreSQL + S3 + Redis swap |
| **CPU is slow for 0.5B** | Use `CHATTERBOX_VARIANT=turbo` (350M) on CPU |
| **No Nano checkpoint** | `chatterbox-tts` 0.1.7 (the pinned PyPI release) has no Nano model reachable through any public API, despite it being documented for the model family generally -- `turbo` (350M) is the smallest variant this package actually provides. See `ai/chatterbox_engine.py`'s module docstring |
| **ffmpeg strongly recommended** | Without it, only WAV/FLAC/OGG decode |
| **Rate limiting is per-process** | Wrong with more than one replica |
| **English-first UI** | The app speaks 23 languages; its own interface does not |
| **Quality is not guaranteed** | Zero-shot cloning depends heavily on the reference recording |

---

## Deployment

**Shipped and ready to run:** Cloudflare Pages (frontend) + Render (backend).
Full walkthrough: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#cloudflare-pages--render-the-shipped-config)**

```
Cloudflare Pages                     Render (Docker web service)
  Next.js static export  ──HTTPS──▶    FastAPI + Chatterbox (CPU, Turbo)
  frontend/out/ · CLOUDFLARE_BUILD=1   render.yaml · backend/Dockerfile.render
```

Cloudflare Workers has no PyTorch runtime, so the backend needs an ordinary
container host regardless of which Cloudflare product serves the frontend —
Render was chosen because it builds a plain Dockerfile with a persistent disk
for `storage/` and the model cache, no separate volume product required. The
frontend needs no Workers runtime adapter either: every route is already a
static, client-rendered page, so `next build` with `CLOUDFLARE_BUILD=1`
produces a plain static export Cloudflare Pages serves directly.

Three things to get right, wherever you deploy: `NEXT_PUBLIC_API_URL` is
compiled into the frontend bundle at build time (changing it needs a rebuild),
`CORS_ORIGINS` on the backend must list the frontend's exact origin, set
*after* the frontend's first deploy since that's when the URL is assigned, and
`ANTHROPIC_API_KEY` must be set on the backend host (Render environment
variable, not a build-time/frontend value) for "Create Fairy Tale" to work —
every other feature works without it.
**HTTPS is mandatory** — `getUserMedia` refuses to run outside a secure
context, so microphone recording simply will not work over plain HTTP. Both
platforms provide HTTPS by default on their `*.pages.dev` / `*.onrender.com`
domains, so this needs no extra configuration.

Other hosting options (GPU providers for the multilingual model, Vercel/Netlify
for the frontend, self-hosting both on one box) are still fully documented in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — the Cloudflare/Render path above is
the one this repository ships pre-configured for, not the only one that works.

---

## Roadmap

**Phase 1 — Web MVP** ✅
Record · upload · create voice · generate · play · download · delete ·
local storage · Docker · tests · CI

**Phase 2 — Accounts and scale**
Authentication · per-user ownership · PostgreSQL + Alembic · S3/MinIO ·
spoken challenge-phrase consent verification · abuse reporting

**Phase 3 — Throughput**
Job queue with `POST /jobs` + `GET /jobs/{id}` · dedicated GPU workers ·
streaming (likely with a CosyVoice 2 engine) · Prometheus metrics ·
Redis-backed rate limiting

**Phase 4 — Mobile**
Android (Kotlin) and iOS (Swift) clients against the **same** `/api/v1`.
No AI-layer redesign: all business logic is already server-side, the JSON is
camelCase, uploads are multipart, audio URLs are range-capable, and capabilities
are discovered at runtime from `/system/info`. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#future-mobile-clients).

---

## Licence

Application code: MIT.

**Model weights are separately licensed.** Chatterbox is MIT, which is why it
was chosen — but if you swap in F5-TTS (CC-BY-NC), XTTS-v2 (CPML) or OpenAudio
S1 (CC-BY-NC-SA), your deployment inherits a **non-commercial** restriction.
Check [docs/MODEL_RESEARCH.md](docs/MODEL_RESEARCH.md#2-comparison-table) before
switching engines.
