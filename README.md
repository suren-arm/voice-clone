# Voice Story Studio

Open-source voice cloning and story narration as a web application. Clone
your own voice from a 10–30 second recording, or skip that entirely and use a
built-in default voice. Write text or generate an original fairy tale in
English or Armenian, then narrate it — optionally with a background ambience
mixed under the narration. Everything runs on your own backend; fairy-tale
text generation is the only feature that calls a third-party API, and it
supports **four interchangeable providers** so no single AI vendor is
required — see [AI Providers](#ai-providers).

**Voice cloning model:** [Chatterbox Multilingual V3](https://github.com/resemble-ai/chatterbox)
by Resemble AI — MIT-licensed **code *and* weights**, 23 languages, zero-shot
cloning from ~10 seconds of audio, neural watermarking built in.

**Default voices:** [espeak-ng](https://github.com/espeak-ng/espeak-ng)
(GPL-3.0, already a runtime dependency — see [Features](#features)) — real,
native English and Armenian synthesis, no recording required, honestly
labelled "Classic" quality rather than passed off as natural neural speech.

**Story generation:** any of OpenAI, Google Gemini, Anthropic Claude, or a
self-hosted Ollama model — see [AI Providers](#ai-providers) for how the
provider abstraction works and which is used when.

```
                                        ┌─▶ VoiceCloningEngine ─▶ PyTorch (CUDA/CPU/MPS)
Browser ──HTTPS──▶ FastAPI ──┬─ speech ─┤
 record/type         REST    │          └─▶ espeak-ng (default voices, en + hy)
 playback                    │                    │
                              └─ stories ─▶ StoryService ─▶ AiProviderRegistry
                                                                  │
                                              OpenAI · Gemini · Claude · Ollama
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
- [AI Providers](#ai-providers)
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
  - [Cloudflare vs Render at a glance](#cloudflare-vs-render-at-a-glance)
  - [Cloudflare (frontend)](#cloudflare-frontend)
  - [Render (backend)](#render-backend)
  - [Why both are needed](#why-both-are-needed)
  - [Deploying the frontend to Cloudflare](#deploying-the-frontend-to-cloudflare)
  - [Deploying the backend to Render](#deploying-the-backend-to-render)
  - [Deployment verification](#deployment-verification)
  - [Deployment troubleshooting](#deployment-troubleshooting)
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

## AI Providers

Fairy-tale text generation is **provider-independent** — it depends on an
abstraction (`AiTextProvider`, in `backend/app/services/ai_providers/`), never
on a specific vendor's SDK. No single AI company is required: with none of
the four configured, every other feature (cloning, TTS, playback, background
mixing) still works, and story generation returns a clear "not configured"
error instead of failing on a hardcoded provider.

| Provider | Env var(s) | Kind | Notes |
|---|---|---|---|
| **OpenAI** | `OPENAI_API_KEY` (+ `OPENAI_MODEL`, default `gpt-5.5`) | paid | Needs a billing-enabled account |
| **Google Gemini** | `GEMINI_API_KEY` (+ `GEMINI_MODEL`, default `gemini-3.5-flash`) | **free-tier** | A Google AI Studio key is free, no billing account or card required, on Flash-class models (rate-limited) — verified 12 Sept 2026, re-check before relying on it, free tiers change |
| **Anthropic Claude** | `ANTHROPIC_API_KEY` (+ `ANTHROPIC_MODEL`, default `claude-opus-5`) | paid | Optional, like every other provider — no longer mandatory |
| **Ollama (local)** | `OLLAMA_BASE_URL` (+ `OLLAMA_MODEL`, default `qwen2.5:7b`) | **local** | The genuinely no-vendor-cost option — see below |

Model defaults were verified against each vendor's own current SDK/docs at
implementation time (12 September 2026) rather than assumed from memory —
this space moves fast, so re-verify before changing them blind.

### Provider selection

`GET /api/v1/ai/providers` reports id/name/kind/availability for all four
(never a key) so the frontend's "AI Provider" dropdown on the Create Fairy
Tale screen only ever offers what is actually configured — an unconfigured
provider is shown disabled ("Not configured"), not selectable, so a user can
never pick a provider and then hit an infrastructure error.

`StoryRequest.provider` is `"auto"` by default, or an exact provider id:

- **An exact id** (`"openai"`, `"gemini"`, `"anthropic"`, `"ollama"`) is used
  exactly as asked, or the request fails with a clear error — it never
  silently substitutes a different provider. Picking OpenAI and being billed
  on Anthropic instead would be a genuinely bad surprise.
- **`"auto"`** tries, in order: `AI_PREFERRED_PROVIDER` if set and available,
  then the built-in priority (`openai` → `gemini` → `anthropic` → `ollama`),
  or — if `AI_AUTO_PREFER_FREE=true` — free-tier/local providers before paid
  ones. This is the only mode allowed to move between providers.

### Why Ollama for the free/local option

A genuinely free option needs to run somewhere with no per-token vendor fee.
Self-hosting an LLM **inside this app's own backend container** was
considered and rejected: the deployed Render Starter instance already runs
Chatterbox (multiple hundred MB of loaded model + PyTorch), and even a small
open model (Qwen2.5, Llama 3.2, Gemma) needs several more GB of RAM alongside
it — not realistic on that plan without either upgrading it or starving
Chatterbox. Ollama is implemented as a real, working provider
(`ollama_provider.py`, talking to Ollama's own REST API) that activates the
moment `OLLAMA_BASE_URL` points at a real Ollama server — your own machine in
development, or a self-hosted box with more RAM in production. That is what
makes it the "no mandatory paid API key, ever" answer: cost is whatever you
already pay to run that server, not a per-request vendor fee.

Model choice, if you do self-host: `qwen2.5:7b` is the default (broader
multilingual training coverage than similarly-sized Llama/Gemma models,
which matters for Armenian quality) for a host with a few GB of RAM to spare;
`qwen2.5:3b` is a lighter, faster alternative for a more constrained host, at
some quality cost. Neither has been benchmarked here for Armenian output
quality specifically — verify before relying on it for that language, same
standard applied to every other Armenian claim in this README.

Gemini's free tier (see table above) is this deployment's practical
"no-cost-to-try" path today, since it needs no infrastructure of your own —
Ollama remains the answer for "no vendor at all, ever."

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
does not re-download gigabytes. `docker-compose.yml` forwards every
[provider-specific](#provider-specific-ai-text-generation) variable from your
shell/`.env` into the `api` container, so setting e.g. `GEMINI_API_KEY` in
`.env` before `docker compose up` is enough to make "Create Fairy Tale" work
the same way it does under plain `uvicorn`.

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

Full list with comments in [`.env.example`](.env.example) (backend + Docker
Compose) and [`frontend/.env.example`](frontend/.env.example) (frontend).
Every variable below is read by real code — nothing here is aspirational —
see [`backend/app/core/config.py`](backend/app/core/config.py) for the
backend's `Settings` class and
[`frontend/src/services/apiClient.ts`](frontend/src/services/apiClient.ts)
for the one frontend variable.

### Required

| Variable | Where | Default | Notes |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Frontend (build-time) | `http://localhost:8000` | The only thing that tells the frontend where the API is. Baked into the static bundle — changing it needs a rebuild, not a restart |

Nothing on the **backend** is strictly required to boot — every variable has a
working default for local development. In production, set `CORS_ORIGINS` (see
[Deployment-only](#deployment-only) below) or the frontend simply cannot call
the API from a browser.

### Optional (backend core)

| Variable | Default | Notes |
|---|---|---|
| `VOICE_ENGINE` | `chatterbox` | or `mock` for development and CI |
| `CHATTERBOX_VARIANT` | `multilingual` | `multilingual` \| `english` \| `turbo` (no `nano` -- see below) |
| `DEVICE` | `auto` | `cuda` \| `cpu` \| `mps` \| `auto` |
| `PRELOAD_MODEL` | `false` | Load weights at boot instead of on first request |
| `MAX_UPLOAD_BYTES` | 25 MiB | |
| `MAX_TEXT_CHARS` | 2000 | Caps worst-case request latency |
| `REQUIRE_CONSENT` | `true` | Do not disable in production |
| `RATE_LIMIT_ENABLED` | `true` | |
| `ENABLE_EXPERIMENTAL_ARMENIAN` | `true` | API-only; the UI never exposes cloned+Armenian regardless |
| `DATABASE_URL` | `sqlite:///storage/voice_studio.db` | Any SQLAlchemy URL |
| `STORAGE_DIR` | `storage` | Recordings, generated audio, the SQLite file |

### Provider-specific (AI text generation)

**At least one of the four is required for "Create Fairy Tale" to work.**
Every other feature (recording, cloning, Text to Speech, playback, download,
background ambience) works with all four unset. Full explanation:
[AI Providers](#ai-providers).

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` / `OPENAI_MODEL` | unset / `gpt-5.5` | Paid, needs billing enabled |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | unset / `gemini-3.5-flash` | Free tier, no billing account needed — cheapest way to try this feature |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | unset / `claude-opus-5` | Paid |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | unset / `qwen2.5:7b` | Self-hosted; the no-vendor-cost option — see [Why Ollama](#why-ollama-for-the-freelocal-option) |
| `AI_PREFERRED_PROVIDER` | unset | "auto" mode tries this provider first if configured |
| `AI_AUTO_PREFER_FREE` | `false` | "auto" mode tries free-tier/local providers before paid ones |
| `RATE_LIMIT_STORY_PER_HOUR` | `30` | |

### Deployment-only

Set these on the **host** (Render's Environment tab, or your own server) —
they either have no sensible default for local development or are secrets
that must never be committed:

| Variable | Local default | Notes |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | **Must** list the frontend's exact production origin, comma-separated, no trailing slash, never `*` |
| `ENVIRONMENT` | `development` | `production` switches logging to structured JSON |

None of the four AI provider variables is individually required — "Create
Fairy Tale" works with any subset configured (including zero, where it
returns a clear "not configured" error instead of breaking).

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

POST   /api/v1/stories/generate             generate a fairy tale (English or Armenian,
                                             provider: "auto" or an exact provider id)
GET    /api/v1/ai/providers                 which AI providers are configured (never a key)

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
# Backend — 191 tests, mock engine + real espeak-ng, no torch weights, ~18 s
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
Full step-by-step walkthrough (dashboard clicks, exact field values, GitHub
Actions alternative): **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#cloudflare-pages--render-the-shipped-config)**.
What follows here is the part every developer actually needs: what each
platform is responsible for, why both exist, and how to verify it worked.

```
Browser
   │  HTML/CSS/JS (static)          HTTPS API calls (fetch)
   ▼                                        │
Cloudflare Pages                            ▼
  Next.js static export ─────────▶  Render Web Service (Docker)
  frontend/out/                       FastAPI + Chatterbox (CPU, Turbo)
  CLOUDFLARE_BUILD=1                  backend/Dockerfile.render · render.yaml
                                       │
                                       ├── AI Story Generation (StoryService)
                                       │     ├── OpenAI        (optional)
                                       │     ├── Google Gemini (optional, free tier)
                                       │     ├── Anthropic     (optional)
                                       │     └── Ollama        (optional, self-hosted)
                                       │
                                       ├── Voice cloning (Chatterbox, PyTorch/CPU)
                                       ├── Default-voice TTS (espeak-ng, en + hy)
                                       ├── Audio mixing (ffmpeg: narration + ambience)
                                       └── SQLite + /app/storage (persistent disk)
```

The browser talks **directly** to Render over HTTPS — Cloudflare Pages is a
static file host here, not a reverse proxy in front of the API. There is no
request path that goes browser → Cloudflare → Render; it is two independent
HTTPS endpoints the frontend bundle happens to know about.

### Cloudflare vs Render at a glance

| Component | Hosted on | Responsibility |
|---|---|---|
| Frontend (Next.js UI) | **Cloudflare Pages** | Static HTML/JS/CSS, global CDN, HTTPS, the domain the user visits |
| Backend API | **Render** (Docker web service) | FastAPI, voice cloning (Chatterbox/PyTorch), default-voice TTS (espeak-ng), audio mixing (ffmpeg), SQLite + file storage |
| OpenAI / Gemini / Anthropic | **External API** (called from the backend only) | Fairy-tale story text generation |
| Ollama | **Your own server** (optional, self-hosted) | Free/local alternative story generation |
| Voice cloning model (Chatterbox) | **Render** (bundled in the backend image) | Zero-shot speech synthesis |

**Why both are needed:** Cloudflare Workers/Pages has no PyTorch runtime, so
it is architecturally unable to run this backend at all — that alone forces a
second host for anything that loads Chatterbox. Render was picked for that
half because it builds a plain Dockerfile, needs no platform-specific
rewrite, and bundles a persistent disk for `storage/` + the model cache into
the same service (no separate volume product to wire up). Cloudflare Pages
remains the right choice for the *frontend* half on its own merits — this app
needs no Workers runtime adapter, since every route is already a static,
client-rendered page (verified by `grep` across `frontend/src`, not assumed):
`next build` with `CLOUDFLARE_BUILD=1` (see `frontend/next.config.ts`)
produces a plain static export that Cloudflare's global CDN serves with free
HTTPS on a `*.pages.dev` subdomain (or your own custom domain).

### Cloudflare (frontend)

- **What's hosted:** the compiled static export of the Next.js app —
  plain HTML/CSS/JS, no Node server, no Workers runtime.
- **Cloudflare product:** **Pages**, not Workers. (Workers is used nowhere in
  this app — mentioned only to be explicit, since both are "Workers & Pages"
  in Cloudflare's current dashboard.)
- **Why Cloudflare specifically:** free static hosting with a global CDN,
  automatic HTTPS (microphone capture requires a secure context — plain HTTP
  will not work), and a Git-integration deploy that needs zero servers of its
  own to maintain.
- **Build command:** `CLOUDFLARE_BUILD=1 npm run build` (from `frontend/`) —
  the env var flips `next.config.ts` to `output: 'export'`. A plain
  `npm run build` (no `CLOUDFLARE_BUILD`) produces a Node server build
  instead, which Cloudflare Pages cannot serve.
- **Deployed directory:** `frontend/out/` (verified: contains `index.html`,
  per-route `.html` files, `_next/`, and the security-header `_headers` file
  copied in from `frontend/public/_headers`).
- **How it reaches the backend:** `NEXT_PUBLIC_API_URL`, set as a Cloudflare
  Pages **build-time** environment variable, is compiled directly into the
  static JS bundle (see `frontend/src/services/apiClient.ts`) — the browser
  calls that URL over plain HTTPS with no proxying through Cloudflare.
- **How it's deployed:** either Cloudflare's own Git integration (dashboard →
  connect repo → auto-builds on every push to the production branch), or the
  included `.github/workflows/deploy-cloudflare-pages.yml` — use one or the
  other, not both (see [Deploying the frontend](#deploying-the-frontend-to-cloudflare)).

### Render (backend)

- **What's hosted:** the full Python/FastAPI backend — API routes, the
  Chatterbox voice-cloning engine (PyTorch, CPU), espeak-ng default-voice
  synthesis, ffmpeg audio mixing, SQLite, and the file storage tree.
- **Service type:** Render **Web Service**, `runtime: docker`, defined as
  code in [`render.yaml`](render.yaml) (a Render "Blueprint").
- **Repository / root:** this repository; Docker build context is the repo
  root (`.`) because the image needs both `backend/` and the sibling `ai/`
  package.
- **Build:** `docker build -f backend/Dockerfile.render .` — a single-stage
  CPU image (Python 3.11-slim + ffmpeg + libsndfile1 + espeak-ng + the CPU
  build of torch).
- **Start command:** baked into the image, not set separately in the
  dashboard — `uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1`
  (one worker: the model is loaded per process, so a second worker would
  double memory for no throughput gain on a single CPU instance).
- **Plan / region:** `starter` / `oregon` in the shipped Blueprint — the free
  plan's 512 MB RAM is too tight for PyTorch + a loaded model, and free
  services spin down on idle.
- **Health check:** `GET /health` (`healthCheckPath` in `render.yaml`) →
  `{"status": "ok", "engineLoaded": false, "version": "0.1.0"}` — the
  liveness probe Render polls to know the deploy succeeded.
- **Persistent disk:** 5 GB mounted at `/app/storage` — survives redeploys,
  so user voices and the SQLite database are not wiped on every push.
- **Public URL:** assigned by Render on first deploy, shown in its dashboard —
  typically `https://voice-clone-api.onrender.com`, or
  `https://voice-clone-api-<random>.onrender.com` if that exact name is
  already taken by another Render account.
- **Environment variables:** set in the Render dashboard → the service →
  **Environment** tab (see [Render environment variables](#render-environment-variables)
  below) — never in `render.yaml` for anything secret, since that file is
  committed to git (`sync: false` in the Blueprint marks exactly which
  variables must be set by hand, per-deployment, instead).

#### Render environment variables

Render Dashboard → your Web Service → **Environment**. Set whichever of these
apply — see [Configuration](#configuration) for defaults and what each does:

```
CORS_ORIGINS          (required in production — the Cloudflare Pages origin)
OPENAI_API_KEY        (optional — at least one AI provider needed for Fairy Tale)
GEMINI_API_KEY        (optional — free tier, no billing account needed)
ANTHROPIC_API_KEY     (optional)
OLLAMA_BASE_URL       (optional — only if you run your own Ollama server)
```

Never put values in this README, in `render.yaml`, or in any committed file —
only variable *names* belong in version control.

### Why both are needed

Restating it plainly, since it's the one thing every new contributor asks:
Cloudflare **cannot** run this backend — Workers has no PyTorch runtime, full
stop — so a second, ordinary container host is not optional, it is the only
way this app's voice cloning works at all. Render is that host. Once a real
container host exists anyway, there is no reason to *also* run the frontend
there: Cloudflare Pages is free, faster (CDN-distributed static files beat a
Node server for a client-rendered app), and needs no server process to keep
alive. Two platforms, two genuinely different jobs — not redundancy.

### Secrets belong on the backend, never in the frontend

**Never** put an OpenAI, Gemini, Anthropic, or any other private API key
inside the frontend build or browser JavaScript — anything prefixed
`NEXT_PUBLIC_` (the *only* frontend variable this app has is
`NEXT_PUBLIC_API_URL`) ends up readable in plain text by anyone who opens
DevTools, because it is compiled directly into the static bundle Cloudflare
serves to every visitor.

```
Correct:    Browser ──▶ Backend (Render) ──▶ AI provider   (key stays server-side)
Never:      Browser ──▶ AI provider directly, using a key embedded in the JS bundle
```

Every AI provider key in this app already lives only in
`backend/app/core/config.py`'s `Settings`, read from the Render environment —
the frontend never sees them, not even indirectly (`GET /api/v1/ai/providers`
reports only id/name/kind/availability booleans, never a key value — see
[AI Providers](#ai-providers)).

### Deploying the frontend to Cloudflare

**Option A — Cloudflare's own Git integration (simplest):**

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages** →
   **Create** → **Pages** → **Connect to Git** → select this repository.
2. Build settings:

   | Field | Value |
   |---|---|
   | Build command | `CLOUDFLARE_BUILD=1 npm run build` |
   | Build output directory | `frontend/out` |
   | Root directory | `frontend` |
3. **Settings → Environment variables** (Production environment):
   `NEXT_PUBLIC_API_URL` = your Render backend's URL.
4. Deploy. Every subsequent push to the production branch (Cloudflare's own
   Git integration, not the GitHub Actions workflow) redeploys automatically.

**Option B — the included GitHub Actions workflow**
(`.github/workflows/deploy-cloudflare-pages.yml`): builds and publishes via
`cloudflare/pages-action` on every push, driven from CI instead of
Cloudflare's dashboard integration. Needs `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID` as repository secrets, and `NEXT_PUBLIC_API_URL` as a
repository variable — see the comment block at the top of that workflow file
for the exact one-time setup. **Use one option or the other, not both** — running
both against the same Pages project makes them race each other on every push.

Full walkthrough with exact dashboard screenshots-in-words:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#cloudflare-pages--render-the-shipped-config).

### Deploying the backend to Render

1. [dashboard.render.com](https://dashboard.render.com) → **New** →
   **Blueprint** → connect this GitHub repository.
2. Render reads [`render.yaml`](render.yaml) and proposes one service,
   `voice-clone-api`. Accept it — every build/start/health-check setting is
   already defined in that file, nothing to fill in by hand.
3. It will fail its first health check with no `CORS_ORIGINS` set yet —
   expected; that value only exists once the frontend has its own URL (step 3
   below).
4. Once deployed, copy the assigned URL from the Render dashboard.
5. Set the AI provider key(s) you want under **Environment** (see
   [Render environment variables](#render-environment-variables) above) — at
   least one is required for "Create Fairy Tale" to work.
6. After deploying the frontend (previous section), come back here and set
   `CORS_ORIGINS` to the frontend's exact origin — Render redeploys
   automatically on save.

Full walkthrough: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#cloudflare-pages--render-the-shipped-config).
Other backend hosting options (GPU providers, Hugging Face Spaces, a single
self-hosted box) are documented there too — the Render path above is what
this repository ships pre-configured for, not the only one that works.

### Deployment verification

After deploying both halves, work through this list against the **live**
URLs (not localhost):

- [ ] `GET https://<your-render-url>/health` returns `{"status": "ok", ...}`
- [ ] The Cloudflare Pages URL loads the home page
- [ ] Opening the frontend with DevTools open shows `GET /api/v1/system/info`
      succeeding with **no CORS error** in the console
- [ ] Text to Speech works with a **default voice** (English)
- [ ] Text to Speech works with a **default voice** (Armenian)
- [ ] Voice cloning: record/upload → create a voice → narrate with it
- [ ] `GET /api/v1/ai/providers` shows **at least one** provider `available: true`
- [ ] **Create Fairy Tale** actually generates a story (not a 503)
- [ ] Background ambience ("Mystical") audibly mixes under narration
- [ ] Generated audio plays back in the browser
- [ ] Generated audio downloads correctly

### Deployment troubleshooting

**Old UI is still displayed after a deploy**
Check: you pushed to the branch Cloudflare Pages' *production* branch is set
to (its `production_branch`, set once at project creation — a mismatch here
makes Cloudflare treat the deploy as a non-production *preview*, so the live
URL never updates); the Cloudflare Pages build actually succeeded (dashboard
→ your project → Deployments); the build output directory is `frontend/out`,
not `.next` or `out/` from the wrong working directory; and finally your own
browser/CDN cache (hard-refresh) before assuming the deploy itself is stale.

**"Create Fairy Tale" says the provider is not configured**
Check `GET /api/v1/ai/providers` on your **backend** URL directly — it lists
every provider with an `available` boolean, never a key. If all four are
`false`, no `*_API_KEY` / `OLLAMA_BASE_URL` is set on Render; set one under
**Environment** and Render will redeploy automatically. This error is
expected and correct, not a bug, until at least one is set.

**Frontend loads but every API call fails**
Almost always CORS or a stale backend URL, not a backend outage:
- Open DevTools → Network tab. A CORS error in the console (not a 4xx/5xx
  status) means `CORS_ORIGINS` on Render doesn't exactly match the frontend's
  origin (scheme + host, no trailing slash, no path).
- `net::ERR_NAME_NOT_RESOLVED` or similar means `NEXT_PUBLIC_API_URL` was
  wrong **at the time the frontend was built** — fix it and redeploy the
  frontend, since it cannot be changed at runtime.
- Confirm the Render service itself is live: `curl https://<render-url>/health`.

**Local backend works but production fails**
Check, in order: Render's **Logs** tab for the actual exception (far more
informative than a generic 500 in the browser); that every environment
variable you rely on locally is also set on Render (a local `.env` is never
uploaded — Render only sees the dashboard's **Environment** tab); that the
build actually installed everything (`backend/requirements.txt`, not
`requirements-ci.txt`, is what `Dockerfile.render` installs — the CI-only
file deliberately omits the heavy `torch`/`chatterbox-tts` stack); and that
ffmpeg/espeak-ng are present (they are baked into `backend/Dockerfile.render`
already — if a custom Docker change removed them, narration and background
mixing break silently for real audio while the mock engine still passes).

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
