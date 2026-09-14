# Voice Story Studio

Open-source voice cloning and story narration as a web application. Clone
your own voice from a 10–30 second recording, or skip that entirely and use a
built-in default voice. Write text, generate an original fairy tale, or
**upload a PDF / paste a public web link and have the app read it to you**
(see [Book Reader](#book-reader)) — in English or Armenian, then narrate it,
optionally with a background ambience mixed under the narration. Everything
runs on your own backend; fairy-tale text generation is the only feature that
calls a third-party API, and it supports **four interchangeable providers**
so no single AI vendor is required — see [AI Providers](#ai-providers). The
Book Reader needs none of them: PDF/web extraction and narration are pure
backend pipelines, no LLM involved.

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
                              ┌─ speech ┤
                              │         └─▶ espeak-ng (default voices, en + hy)
                              │                    │
Browser ──HTTPS──▶ FastAPI ──┼─ stories ─▶ StoryService ─▶ AiProviderRegistry
 record/type         REST    │                                  │
 playback                    │              OpenAI · Gemini · Claude · Ollama
                              │
                              └─ books ──▶ DocumentService ─┬─▶ PdfDocumentExtractor (pypdf)
                                              │              └─▶ WebDocumentExtractor (trafilatura,
                                              │                   SSRF-safe fetch)
                                              ▼
                                        ReadingService ─▶ (same speech pipeline above)
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
- [Book Reader](#book-reader)
  - [PDF upload](#pdf-upload)
  - [HTTP/HTTPS link reading](#httphttps-link-reading)
  - [Security: SSRF protection](#security-ssrf-protection)
  - [Reading range and long-book chunking](#reading-range-and-long-book-chunking)
  - [Local testing](#local-testing-book-reader)
- [Quick start](#quick-start)
- [Local development](#local-development)
- [Docker](#docker)
- [GPU setup](#gpu-setup)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Design system](#design-system)
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
- [Why Cloudflare and Render Are Both Used](#why-cloudflare-and-render-are-both-used)
- [Hosting Alternatives](#hosting-alternatives)
- [Roadmap](#roadmap)

---

## Features

- **Two voice sources.** *My Cloned Voice* (Chatterbox, requires a recording)
  or *Default Voice* (espeak-ng, no recording — English and Armenian).
- **Three modes.** *Text to Speech* for text you write yourself, *Create
  Fairy Tale* — describe characters, an idea, age group, length and tone, and
  an AI provider generates an original story you can edit before narrating —
  and **Book Reader** — upload a PDF or paste a public web link, pick what to
  read, and narrate it (see [Book Reader](#book-reader)).
- **English and Armenian.** Manual text, fairy-tale generation, Book Reader
  extraction, and default-voice TTS all genuinely support both. Cloned-voice
  narration does not yet support Armenian — the UI disables that specific
  combination and explains why, rather than allowing a request that fails
  obscurely (see [Armenian](#armenian)).
- **Background ambience.** Optional, mixed under the narration via ffmpeg —
  *None*, *Mystical*, *Calm*, *Forest* and *Bedtime* (all self-generated,
  license-free synth pads; see `scripts/generate_ambience.py`). The narration
  stays clear over any of them, guarded three ways: every track keeps its
  energy out of the 150 Hz–5 kHz speech corridor (enforced at generation time
  *and* by `tests/unit/test_ambience_speech_safety.py`), the mix ducks the
  ambience under speech with a sidechain compressor, and the background gain
  is capped regardless of the slider. Measured: mixing moves the narration's
  speech-band energy by about 0.1%.
- **Long-text-safe narration.** Fairy tales and books are chunked at
  paragraph/sentence boundaries — never mid-word — synthesized per chunk, and
  concatenated, so a long text doesn't risk a single giant, fragile TTS call.
- Everything from the original voice-cloning app is unchanged: recording,
  upload, consent, voice management, playback, download, watermarking.

### Support matrix

**Supported languages — the same three everywhere:** 🇬🇧 English (`en`),
🇦🇲 Հայերեն / Armenian (`hy`), 🇷🇺 Русский / Russian (`ru`).

| | English | Հայերեն | Русский |
|---|---|---|---|
| Text to Speech | ✅ | ✅ | ✅ |
| Fairy-tale generation | ✅ (native) | ✅ (native, not translated) | ✅ (native, not translated) |
| Fairy-tale narration | ✅ | ✅ | ✅ |
| Default ("studio") voice | ✅ espeak-ng `en-us` | ✅ espeak-ng `hy` + `hyw` | ✅ espeak-ng `ru` |
| Cloned voice ("My Voice") | ✅ | ❌ model cannot speak it | ⚠️ multilingual variant only |
| Background ambience | ✅ (5 options) | ✅ | ✅ |
| Book Reader — PDF extraction | ✅ | ✅ (real Unicode, no mojibake) | ✅ (Cyrillic verified) |
| Book Reader — web article extraction | ✅ | ✅ | ✅ |
| Book Reader — narration | ✅ | ✅ (studio voice) | ✅ (studio voice) |

"✅" means genuinely supported and tested, not merely accepted by the API.

**Cloned-voice limitations are real, not policy.** Voice *cloning* and
*speaking a language in a cloned voice* are different capabilities:

- **English** — cloneable and speakable in every Chatterbox variant.
- **Armenian** — no open-source zero-shot cloning model supports it (verified;
  see [docs/ARMENIAN.md](docs/ARMENIAN.md)). The studio voices speak it
  natively, so the UI disables the cloned path and says
  *"This voice cannot speak Հայերեն. Please choose another voice."*
- **Russian** — in Chatterbox's `multilingual` variant only. The deployed
  configuration is `turbo`, which is English-only, so on production Russian
  narration uses the studio voice.

None of this is hardcoded in the UI. `GET /api/v1/system/info` publishes a
`supportsClonedVoice` / `supportsDefaultVoice` flag per language, read off the
engines actually loaded, and the voice picker only ever offers voices that
speak the chosen language — so an unsupported combination cannot be selected,
let alone submitted.

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
> **The transliteration bridge is no longer in the speech path.** Armenian
> script can be transliterated into Russian orthography (a much closer
> phonological fit than Latin) so a cloned voice can approximate it, and
> `POST /api/v1/speech` used to do exactly that behind a flag. It was removed:
> the studio voices speak Armenian natively, so the approximation was strictly
> worse than the supported path while still being reachable. The
> transliteration itself remains in `ai/armenian.py` as the documented starting
> point for a fine-tuning pipeline — see [docs/ARMENIAN.md](docs/ARMENIAN.md).

Expect a recognisable Armenian accent with wrong stress placement from the
experimental path — not real Armenian TTS. What was verified for both
questions (why espeak-ng over Piper's GPL-2.0 voice or Meta's non-commercial
MMS-TTS; why Russian and not Latin for the transliteration bridge; the
fine-tuning path to real cloning support): **[docs/ARMENIAN.md](docs/ARMENIAN.md)**.

Disable the experimental cloned-voice bridge (API-only; the UI never exposed
it).

---

## Book Reader

Upload a PDF, or paste a public web link (an article or a PDF URL), and have
the app extract the readable text and narrate it — in your cloned voice or a
default voice, with the same optional background ambience as everything
else. This is a **separate workflow** from Text to Speech's text box: the
`/book-reader` screen never asks you to paste text yourself.

```
PDF Upload / URL
       │
       ▼
DocumentService ──┬─▶ PdfDocumentExtractor (pypdf)
                   └─▶ WebDocumentExtractor (SSRF-safe fetch + trafilatura)
       │
       ▼
Document + DocumentSection (persisted; original PDF bytes are never kept)
       │
       ▼
Extracted-text preview (paginated, one page/section at a time)
       │  user picks: Entire / Pages / Section, language, voice, speed, background
       ▼
ReadingService (resolves the range, enforces MAX_BOOK_NARRATION_CHARS)
       │
       ▼
SpeechService.generate_for_book  ──▶  (the same TTS/mixing pipeline every
                                        other feature uses)
       │
       ▼
Generation (playable + downloadable exactly like any other narration)
```

**No AI/LLM involved by default.** PDF and web extraction are pure parsing
and boilerplate-removal pipelines (`pypdf`, `trafilatura`) — reading a book
never calls OpenAI, Gemini, Claude or Ollama, and needs none of the four
provider keys from [AI Providers](#ai-providers) configured. (Optional future
features like "Summarize this chapter" would use that same provider
architecture — see [Known limitations](#known-limitations) for what is and
isn't built yet.)

### Supported document types

| Input | How it's identified | Notes |
|---|---|---|
| Uploaded PDF | Magic-byte check (`%PDF-`) — never the `.pdf` extension alone | Encrypted/password-protected and scanned (no text layer) PDFs are rejected with a clear message, not silently emptied |
| Public PDF URL | Response `Content-Type` **and** magic bytes — whichever says PDF | A `.html` URL that actually serves a PDF (or vice versa) is still handled correctly |
| Public web article URL | Whatever isn't identified as a PDF, run through `trafilatura` | Navigation, ads, cookie banners, footers and scripts are stripped — verified in tests against a realistic boilerplate-heavy page, not assumed |

### PDF upload

```
PDF Upload → validate (type, size, page count, encryption) → extract text
  → detect structure (page-by-page, best-effort heading per page)
  → display extracted text (paginated preview) → user selects reading range
  → generate narration
```

Validated before anything is parsed further: real file content (not the
filename), total size (`MAX_PDF_BYTES`, default 20 MiB), page count
(`MAX_PDF_PAGES`, default 500), and encryption state (an empty-password
"encrypted" PDF — common for permission-only restrictions — is transparently
unlocked; a genuinely password-protected one is rejected with a clear
message). **Scanned PDFs** (little or no extractable text on most pages) are
detected and reported — *"This PDF appears to contain scanned pages and does
not have extractable text"* — never silently returned as empty. OCR is not
implemented in this version (see [Known limitations](#known-limitations)).

### HTTP/HTTPS link reading

Paste a link to an article or a PDF. The backend determines which it actually
is from the real HTTP response — content-type header and magic bytes — never
from the URL's own spelling, and extracts accordingly (see the table above).
This is a **read-only, single-page tool**: it processes only the exact
page/document you give it. There is no crawler, no search, and no feature
that looks for other copies of a book elsewhere — see
[Copyright-aware behaviour](#security-ssrf-protection) below.

### Security: SSRF protection

Fetching a URL on the server's behalf is treated as a security-sensitive
feature (`backend/app/services/documents/security.py`), not a thin wrapper
around an HTTP client:

- **Only `http://`/`https://`** — `ftp://`, `file://`, and anything else is
  rejected outright, with the message *"Invalid URL. Only public HTTP and
  HTTPS links are supported."*
- **DNS-resolved target validation.** The hostname is resolved and every
  returned address is checked against loopback, private (RFC 1918/4193),
  link-local, multicast, reserved and unspecified ranges before any request
  is made — this blocks `localhost`, `127.0.0.1`, `::1`, internal IPs, and
  cloud metadata endpoints (`169.254.169.254` and friends fall under
  link-local, already covered).
- **Every redirect hop is re-validated**, not just the first URL — a public
  page that redirects to an internal address is refused exactly like
  requesting the internal address directly. Redirects are capped
  (`BOOK_FETCH_MAX_REDIRECTS`, default 5).
- **Bounded resources**: separate connect/read timeouts
  (`BOOK_FETCH_CONNECT_TIMEOUT_SECONDS` / `BOOK_FETCH_READ_TIMEOUT_SECONDS`)
  and a byte cap (`MAX_REMOTE_DOWNLOAD_BYTES`) enforced while *streaming* the
  response — a server that omits or lies about `Content-Length` cannot bypass
  it.
- **Never a general-purpose proxy.** There is no way to retrieve raw bytes
  from an arbitrary internal host through this feature; only the extracted,
  normalized text of a public document ever comes back.

**Documented limitation:** the DNS check resolves the hostname once, before
connecting; a small residual window for adversarial DNS-rebinding remains
(the target's own DNS server could answer differently a moment later), which
would need a transport that pins the exact validated IP to close completely.
This covers the overwhelming majority of real SSRF attempts (literal internal
addresses, `localhost`, known metadata hostnames); a deployment with a
stricter threat model should add network-level egress control (a firewall or
forward proxy) alongside it. See the module's own docstring for the full
reasoning.

### Reading range and long-book chunking

A book may be hundreds of pages; "Start Reading" never sends the whole thing
to the TTS engine in one call. Pick **Entire Document**, a **Page range**
(PDF only — an HTML article has no pages), or a **Selected Section** (a
heading-delimited block of a web article, or a single PDF page). Whatever is
selected is capped at `MAX_BOOK_NARRATION_CHARS` (default 12,000 characters —
larger than a single manual/fairy-tale request's cap, but still a bounded
batch, not an unbounded book): choosing a smaller range is how a full book
gets read in this version, rather than a background job queue this project
does not have yet (see [Known limitations](#known-limitations)). Within
whatever range is selected, the existing paragraph/sentence-safe chunker
(`ai/text_chunking.py`) still applies before synthesis, exactly as it does
for fairy tales.

**Resume reading.** The last document, reading range, voice and language are
remembered in the browser (`localStorage`) so returning to `/book-reader`
offers a "Resume" option — session-level, by design (see
[Known limitations](#known-limitations) for why this isn't a database
table).

**Cleanup.** The original PDF (uploaded or downloaded) is **never written to
disk** — it is parsed entirely in memory and discarded. Only the extracted
text and section metadata persist, in the same SQLite database as everything
else, for `DOCUMENT_RETENTION_HOURS` (default 24) before a startup sweep
removes it — a book is not meant to become a permanent library entry.
Generated narration audio follows the same lifecycle as any other
`Generation` (kept until you delete it, exactly like Text to Speech output).

### Local testing (Book Reader)

```bash
# A small English PDF and a small Armenian PDF -- either from your own
# files, or generate quick test fixtures the way the test suite does:
cd backend && python3 -c "
from tests.conftest import make_pdf_bytes
open('/tmp/en.pdf', 'wb').write(make_pdf_bytes(['Chapter One\n\nHello world.']))
open('/tmp/hy.pdf', 'wb').write(make_pdf_bytes(['Գլուխ մեկ\n\nԲարև աշխարհ։']))
"
curl -F "file=@/tmp/en.pdf" http://localhost:8000/api/v1/books/upload
curl -F "file=@/tmp/hy.pdf" http://localhost:8000/api/v1/books/upload

# A public HTML article and a public PDF URL
curl -X POST http://localhost:8000/api/v1/books/from-url \
  -H 'Content-Type: application/json' -d '{"url":"https://example.com/some-article"}'
```

Cases worth trying by hand, all of which return a clear error (never a crash
or a silent empty result):

| Case | Expected |
|---|---|
| A non-HTTP URL (`ftp://…`, `file://…`) | `422 unsupported_url` — "Only public HTTP and HTTPS links are supported." |
| An internal address (`http://127.0.0.1/`, `http://localhost/`) | `422 unsupported_url` — blocked as a private/local target |
| A URL that 404s or times out | `502 remote_fetch_failed` with the real reason |
| A redirect loop | `502 remote_fetch_failed` — "Too many redirects" |
| A file far larger than `MAX_PDF_BYTES`/`MAX_REMOTE_DOWNLOAD_BYTES` | `413 payload_too_large` (upload) or `502` (remote) |
| An empty or corrupted PDF | `422 document_invalid` |
| A password-protected PDF | `422 document_invalid` — "password-protected" |
| A scanned (image-only) PDF | `422 document_scanned` — "appears to contain scanned pages" |

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

### Optional (Book Reader)

No AI provider needed — see [Book Reader](#book-reader). All have working
defaults; tune them to your deployment's memory/disk budget.

| Variable | Default | Notes |
|---|---|---|
| `MAX_PDF_BYTES` | 20 MiB | Uploaded PDF size cap |
| `MAX_PDF_PAGES` | `500` | Applies to an uploaded PDF and one fetched from a URL alike |
| `MAX_REMOTE_DOWNLOAD_BYTES` | 20 MiB | Cap for a URL-fetched PDF or HTML page |
| `BOOK_FETCH_CONNECT_TIMEOUT_SECONDS` | `5` | |
| `BOOK_FETCH_READ_TIMEOUT_SECONDS` | `20` | |
| `BOOK_FETCH_MAX_REDIRECTS` | `5` | |
| `MAX_BOOK_NARRATION_CHARS` | `12000` | One "Start Reading" call's text budget — see [Reading range and long-book chunking](#reading-range-and-long-book-chunking) |
| `DOCUMENT_RETENTION_HOURS` | `24` | Extracted text/metadata older than this is swept on startup |
| `RATE_LIMIT_BOOK_INGEST_PER_HOUR` | `20` | Upload + URL-fetch requests |
| `RATE_LIMIT_BOOK_NARRATE_PER_HOUR` | `30` | |

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
│   │   ├── main.py              app factory, middleware, health, default-voice/doc-cleanup bootstrap
│   │   ├── api/v1/              voices · speech · generations · stories · books · system
│   │   ├── assets/ambience/     self-generated background tracks (mystical/calm/forest/bedtime)
│   │   ├── core/                config · errors · security · rate limiting
│   │   ├── db/                  engine, session, base
│   │   ├── models/              SQLAlchemy: Voice, Generation, AuditEvent, Document, DocumentSection
│   │   ├── schemas/             Pydantic request/response (camelCase)
│   │   ├── repositories/        data access
│   │   └── services/
│   │       ├── documents/       Book Reader: PdfDocumentExtractor · WebDocumentExtractor ·
│   │       │                    security (SSRF-safe fetch) · ReadingService · DocumentService
│   │       └── voice · speech · story · language · default_voices · storage
│   ├── tests/{unit,api,integration,ai}/
│   ├── requirements.txt         full stack
│   ├── requirements-ci.txt      no torch — what CI installs
│   └── Dockerfile               cpu + gpu targets
│
├── frontend/
│   ├── src/
│   │   ├── app/                 App Router pages, incl. fairy-tale/ · book-reader/
│   │   │                        globals.css holds the design tokens (see Design system)
│   │   ├── components/          shared UI (Dropzone, AudioPlayer, Field, Card, …)
│   │   ├── features/            voices/ · speech/ · story/ · book-reader/
│   │   ├── hooks/               useRecorder · useVoices · useDefaultVoices · useSystemInfo · …
│   │   ├── services/            the only code that knows the API exists (incl. books.ts)
│   │   ├── types/               API contract types
│   │   └── utils/               format · audio · validation · voiceCapability · bookReaderSession
│   ├── e2e/                     Playwright
│   └── Dockerfile
│
├── docs/                        research, architecture, API, security, …
├── scripts/                     download_model.py · benchmark.py · generate_ambience.py
├── storage/                     voices/ · generated/ (gitignored — the Book Reader keeps no PDF here)
└── docker-compose{,.gpu}.yml
```

`ai/` sits outside `backend/` on purpose: it has no web dependencies, so a
standalone GPU worker can import it later without dragging FastAPI along.

---

## Design system

The audience is children, with adults nearby. The interface is built for the
child first; anything an adult or an engineer needs is one click away rather
than on the front door.

**Tokens live in `frontend/src/app/globals.css`.** Components never hard-code a
colour, radius or spacing value.

| Token group | Purpose |
|---|---|
| `--joy-grape` / `-sky` / `-sun` / `-mint` / `-coral` (+ `-soft`) | One hue per feature, so a colour consistently means a place in the app: fairy tale is grape, Book Reader is sky, text-to-speech is mint, voice creation is coral |
| `--bg`, `--bg-sunken`, `--text`, `--text-muted`, `--border`, `--border-strong` | Surfaces and type, each with a `prefers-color-scheme: dark` value |
| `--accent`, `--accent-soft` | The single interactive colour |
| `--radius`, `--radius-lg`, `--radius-pill` | Soft geometry |
| `--space-1` … `--space-7` | The only spacing scale |
| `--tap: 44px` | Minimum tap target (WCAG 2.5.5), applied to buttons, nav links and segmented options |
| `--font`, `--font-reading` | The UI stack includes `Noto Sans Armenian`, so Հայերեն renders in family rather than falling back mid-sentence |

**Rules the UI follows:**

- **Plain language over product language.** Fields ask "Who is in your story?",
  not "Characters". Buttons say "✨ Create My Story", not "Generate".
- **Engineering detail is disclosed, never deleted.** Model, device, sample
  rate and licence sit behind *Studio status* on the home page; render time,
  RTF and file size behind *Technical details* on the result screen; the AI
  provider behind *Advanced settings* on the story form.
- **Joyful, not noisy.** One static gradient, one scale transform on drag-over.
  No animated backgrounds, no autoplay, no sound effects. A global
  `prefers-reduced-motion: reduce` block turns off what motion there is.
- **Every emoji is decorative.** All are `aria-hidden="true"` beside a real text
  label, so a screen reader hears "Read a Book", not "open book Read a Book".

A full account of what changed and why — including what was deliberately left
alone — is in **[REFACTORING_REVIEW.md](REFACTORING_REVIEW.md)**.

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

POST   /api/v1/books/upload                 upload a PDF (multipart), extract its text
POST   /api/v1/books/from-url               fetch a public http(s) link (PDF or article), extract it
GET    /api/v1/books/{id}                   document metadata (title, language, page/section count)
GET    /api/v1/books/{id}/sections          paginated section list (titles/lengths, never full text)
GET    /api/v1/books/{id}/sections/{index}  one section's full text (the preview screen)
POST   /api/v1/books/{id}/narrate           narrate a range (entire/pages/section) — returns a
                                             Generation, same playback/download as everything else
DELETE /api/v1/books/{id}                   delete the extracted document (narrations are unaffected)

GET    /api/v1/system/info                  engine, languages, limits (incl. Book Reader limits)
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

`POST /books/{id}/narrate` is the one exception that does *not* reuse
`POST /speech` directly: `SpeechRequest.text` has its own hard ceiling sized
for hand-typed/generated text, so book narration calls a book-specific
service entry point (`SpeechService.generate_for_book`) with a larger,
separately-configured budget (`MAX_BOOK_NARRATION_CHARS`) — but it is the
exact same underlying chunking, synthesis, background-mixing and
`Generation`-persistence code path, just reached with a different ceiling.
See [Book Reader](#book-reader).

---

## Testing

```bash
# Backend — 308 tests, mock engine + real espeak-ng, no torch weights, ~30 s
cd backend && pytest

# By layer
pytest tests/unit tests/api tests/integration

# Real cloning model — opt-in, downloads weights
pytest -m ai tests/ai

# Frontend — 77 unit tests
cd frontend && npm run test:run

# End-to-end — 16 tests, desktop + mobile viewports
npm run test:e2e
```

| Suite | What it covers |
|---|---|
| `tests/unit` | Path traversal, filename sanitisation, audio validation, container sniffing, silence trimming, rate limiting, Armenian transliteration, the engine contract, PDF extraction (English/Armenian/mixed/encrypted/scanned), SSRF blocking, HTML boilerplate removal, reading-range resolution |
| `tests/api` | Every endpoint: consent gating, bad formats, oversized uploads, quotas, empty/overlong text, unknown IDs, byte ranges, pagination, Book Reader upload/from-url/sections/narrate (remote HTTP mocked — no test depends on a real website) |
| `tests/integration` | The full journey; conditioning-cache reuse; cascade delete; audit trail; rate limits end to end |
| `tests/ai` | Real Chatterbox: language set, conditioning round trip, synthesis, **watermark detectability**, RTF |
| `frontend` (Vitest) | Formatting, file validation, the API client's error handling, the audio player, the dropzone, the generate form, the Book Reader form (upload, URL load, reading-range selection, narration, Armenian blocking, resume) |
| `e2e` (Playwright) | Create → generate → play → download → delete, real `MediaRecorder` capture, the Armenian labelling path, API-failure handling, phone-width layout, Book Reader upload/URL/preset flow |

Total: **401 tests** across four layers.

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
| **No OCR** | A scanned (image-only) PDF is detected and clearly reported, not silently emptied — but its text is never extracted. Deliberately not built for this version; see [Book Reader](#book-reader) |
| **No AI book features yet** | Summarize/translate/simplify/explain a section are not implemented — reading a book never requires an AI provider today. The existing multi-provider architecture is the natural place to add them later, opt-in per action |
| **No whole-book single download** | Narration is generated per selected range (a bounded batch), each as its own downloadable `Generation` — there is no "compile the entire book into one audio file" feature yet |
| **No background job queue for narration** | A book-sized narration is still one synchronous HTTP request, capped at `MAX_BOOK_NARRATION_CHARS` per call — the same constraint (and the same reasoning) as every other synchronous generation in this app |
| **SSRF check has a residual DNS-rebinding window** | The hostname is resolved and validated before connecting, not pinned for the connection itself — see [Security: SSRF protection](#security-ssrf-protection) for the full reasoning and mitigation |
| **Resume reading is session/browser-local** | `localStorage`, not a database row — clearing site data forgets it, and it does not follow you to another device |

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
- [ ] **Book Reader**: upload a small PDF and confirm the extracted-text preview shows real text
- [ ] **Book Reader**: paste a public article URL and confirm it extracts (not a raw-HTML dump)
- [ ] **Book Reader**: narrate a page range and a selected section, both successfully
- [ ] **Book Reader**: an internal/private URL (e.g. `http://127.0.0.1/`) is rejected with a 422, not fetched
- [ ] Background ambience (any of the five) audibly mixes under narration
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

## Why Cloudflare and Render Are Both Used

A full evidence-based review of this question — including whether the
backend could move to Cloudflare, and whether that would be cheaper — lives
in **[CLOUDFLARE_BACKEND_FEASIBILITY.md](CLOUDFLARE_BACKEND_FEASIBILITY.md)**.
Short version:

**Cloudflare** hosts the frontend (Cloudflare Pages): a static Next.js
export, served free from Cloudflare's global CDN with automatic HTTPS. No
Workers, no Functions, no server process — verified by the absence of any
`wrangler` config anywhere in this repository. This is the right tool for a
static, client-rendered app and costs nothing.

**Render** hosts the backend: a single, always-warm Python process that
keeps a ~350M-parameter PyTorch voice-cloning model (Chatterbox) resident in
memory, shells out to `ffmpeg` and `espeak-ng` as real subprocesses, and
reads/writes a persistent disk (SQLite database, cloned-voice reference
audio, generation history). None of that is optional plumbing — it is the
actual workload.

**Why the backend is not on Cloudflare:** Cloudflare Workers — the product
most people mean by "run it on Cloudflare" — cannot run this backend under
any interpretation of "compatible," for three independent reasons, any one
of which alone is disqualifying:

1. **A 128 MB memory ceiling, hard-capped on every plan.** The voice-cloning
   model alone is roughly 1.4 GB in memory — over 10× the entire budget,
   before a single request is served.
2. **No subprocess execution, at any tier.** `ffmpeg` and `espeak-ng` are
   invoked as real subprocesses throughout this codebase (`ai/audio_mix.py`,
   `ai/espeak_engine.py`) — Workers' sandbox does not run native binaries.
3. **No persistent filesystem.** Workers' filesystem is in-memory and
   destroyed with the isolate; cloned voices and generation history need to
   outlive a single request by months, not milliseconds.

**Cloudflare Containers** — a real Docker-container product, distinct from
Workers — is the honest alternative that actually could run this exact
image, and the feasibility review evaluates it in full rather than dismissing
it. The blocker there is different: Container disk is ephemeral by design,
wiped on every restart, so adopting it safely means rewriting this app's
storage onto Durable Objects/R2 first — a real re-architecture, not a
redeploy — and even then, keeping a resident model warm (to avoid re-paying
its load cost on every cold start) erodes the pay-per-use pricing that makes
Containers attractive for bursty workloads in the first place. **Not
recommended today**; see the full report for the complete analysis, cost
comparison, and a phased path if this is ever revisited.

The one genuinely easy, low-risk Cloudflare win identified — and not yet
adopted, because the benefit is currently marginal — is moving the
AI-provider proxy (`app/services/ai_providers/`, a stateless HTTP passthrough
to OpenAI/Gemini/Anthropic/Ollama with no local compute) to a Worker. Worth
revisiting if Render's own cost or load ever becomes a real constraint.

## Hosting Alternatives

| Option | Verdict | Why |
|---|---|---|
| **Current: Cloudflare Pages + Render** (recommended, unchanged) | Keep | Already matches the workload — static/CDN for the frontend, persistent resident-model host for the backend. ~$8.25/month. |
| Cloudflare Workers for the whole backend | **Not viable** | 128 MB memory ceiling, no subprocess execution, no persistent filesystem — see above. |
| Cloudflare Containers for the whole backend | Possible, not recommended now | Ephemeral disk requires a storage rewrite (Durable Objects/R2) before it's safe; not clearly cheaper once kept warm to avoid cold-starting the model on every request. |
| Hybrid: AI-provider proxy on a Cloudflare Worker, everything else on Render | Good future option, not urgent | Real, low-risk win for the one part of the backend that's already a stateless HTTP proxy — but adds a third deployed service for a currently-marginal benefit. |

See **[CLOUDFLARE_BACKEND_FEASIBILITY.md](CLOUDFLARE_BACKEND_FEASIBILITY.md)**
for the full decision matrix, cost comparison (current published pricing,
not assumed), free-tier analysis, and a phased migration plan for if this is
ever revisited.


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
