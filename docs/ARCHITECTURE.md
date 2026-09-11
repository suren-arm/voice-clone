# Architecture

## The decision, first

**Backend inference, with browser-side preprocessing — Option C (hybrid).**

```
┌──────────────────────────── Browser ────────────────────────────┐
│  MediaRecorder capture · format/size pre-checks · playback      │
│  Next.js 15 + TypeScript                                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS · REST · JSON + multipart
                                ▼
┌──────────────────────────── FastAPI ────────────────────────────┐
│  routers → services → repositories                              │
│  validation · consent · rate limits · audit                     │
└──────────┬──────────────────────────────────────┬───────────────┘
           │                                      │
           ▼                                      ▼
┌── VoiceCloningEngine (abstract) ──┐   ┌── Storage ──────────────┐
│  ChatterboxEngine  │  MockEngine  │   │  SQLite  │  filesystem  │
│         PyTorch → CPU / CUDA / MPS │   │  metadata │  audio      │
└────────────────────────────────────┘   └─────────────────────────┘
```

### Why not browser inference (Option A)

Rejected on the evidence, not on principle:

| Requirement | Reality for Chatterbox |
|---|---|
| Model download | 0.5B params ≈ 1 GB at fp16, per visitor, before the first word |
| Runtime | PyTorch, with custom S3Gen/S3Tokenizer ops — no ONNX export exists |
| WebGPU | Would need a full re-implementation of the inference graph |
| Memory | ~2 GB of browser heap on a phone |

Browser TTS is real in 2026 — Kokoro-82M runs entirely client-side via
Transformers.js on WASM or WebGPU. But **Kokoro cannot clone voices**; it plays
preset voice packs. Every model that *can* clone is 4–10× larger and has no
browser runtime. Forcing one into the browser is not a trade-off, it is a
different product.

The browser still does the parts it is good at: capture, format and size
pre-checks, and playback. That is the "hybrid" in Option C.

### Why not pure backend with a dumb client (Option B)

That is essentially what this is. The distinction is that client-side validation
runs *before* upload, so a user who picks a 200 MB video gets told immediately
instead of after a slow upload. The server re-validates everything regardless —
client checks are a courtesy, never a control.

---

## Request flows

### Creating a voice

```
POST /api/v1/voices  (multipart: name, language, consent, source, audio)
  │
  ├─ rate limit (per IP, token bucket)
  ├─ read upload in 1 MiB chunks, abort past the limit   ← never buffers a huge body
  ├─ consent assertion required                          → 403 consent_required
  ├─ magic-byte container sniff                          → 422 invalid_audio
  ├─ ffmpeg decode → mono float32 @ 24 kHz
  ├─ duration + level validation                         → 422 invalid_audio
  ├─ trim silence · peak-normalise to −1 dBFS
  ├─ write storage/voices/<id>/reference.wav
  ├─ engine.create_voice()  ── speaker encoder + speech tokenizer + S3Gen ref
  │     └─ storage/voices/<id>/conds.pt                  ← the expensive part, once
  ├─ INSERT voices  ·  write metadata.json
  └─ audit: voice.created
```

Blocking work runs in Starlette's threadpool (`run_in_threadpool`), so one slow
conditioning job does not stall the event loop.

### Generating speech

```
POST /api/v1/speech  {voiceId, text, language}
  │
  ├─ rate limit
  ├─ load voice                                          → 404 voice_not_found
  ├─ resolve language (Armenian bridge if needed)        → 422 unsupported_language
  ├─ text length check                                   → 422 validation_error
  ├─ engine.synthesize()
  │     ├─ load conds.pt into model.conds                ← no reference re-read
  │     ├─ T3 → speech tokens → S3Gen → 24 kHz waveform
  │     └─ PerTh watermark
  ├─ write storage/generated/<id>.wav
  ├─ INSERT generations (duration, RTF, watermark, experimental flag)
  └─ 201 { id, audioUrl, durationSeconds, realTimeFactor, ... }
```

---

## Design decisions, and what would change them

### Synchronous generation, no queue

`POST /speech` blocks until the WAV exists. Justified by the numbers: Chatterbox
runs well under RTF 1.0 on a GPU, so 30 seconds of speech takes a few seconds.
A queue would add Redis, a worker process, a polling client and a whole class of
"job stuck in `pending`" bugs, to solve a problem that does not exist yet.

**Introduce `POST /jobs` + `GET /jobs/{id}` when any of these becomes true:**

- p95 generation exceeds ~30 s (measure with `scripts/benchmark.py`)
- text limits rise past a few thousand characters
- more than one concurrent user per GPU
- a proxy or CDN in front of the API caps request duration below generation time

The response shape is already forward-compatible: a job-completion payload would
be the same `Generation` resource this endpoint returns today, so clients would
gain a polling step and change nothing else.

### JSON with `audioUrl`, not raw `audio/wav`

Returning bytes directly is simpler for exactly one use case. It loses:

- the history list (nothing to list — the audio was never persisted or indexed)
- the RTF, watermark and provenance metadata the safety story relies on
- byte-range seeking in the player
- cacheability, and a URL a mobile client can hand to `AVPlayer`/`ExoPlayer`

One extra round trip is a good price for all of that.

### One engine instance, one lock

`ai/registry.py` holds a process-wide singleton, and `ChatterboxEngine` guards
load and inference with a single `RLock`. Two reasons: the model object carries
mutable conditioning state (`model.conds`), so concurrent `generate()` calls
would interleave voices; and one GPU cannot usefully run two of these at once
anyway. The Docker image runs `--workers 1` for the same reason — a second
worker doubles VRAM for no throughput.

**Scaling past one GPU** replaces the lock with N single-worker API containers
behind a load balancer, sharing storage and the database. No application change
beyond the storage swap below.

### SQLite + local filesystem

Metadata in SQLite (WAL mode, `check_same_thread=False`); audio on disk. Nothing
about the schema assumes SQLite — it is plain SQLAlchemy 2.0.

**Move to PostgreSQL + S3/MinIO when** there is more than one API replica, or
the data outgrows one disk, or you want point-in-time recovery. The path:

1. `DATABASE_URL=postgresql+psycopg://…` — SQLAlchemy handles the rest. Add
   Alembic at the same time and replace the `create_all()` call in
   `db/session.py` with a migration step.
2. Implement `S3Storage` with the same method surface as `LocalStorage`
   (`voice_dir`, `reference_path`, `generation_path`, `delete_voice`, …) and
   inject it in `api/deps.py`. Only that file and `services/storage.py` change.
3. Serve audio via presigned URLs. `GenerationResponse.audioUrl` is already an
   opaque string to every client, so nothing downstream notices.

### In-process rate limiting

A dict of token buckets in `core/rate_limit.py`. Correct and free for one
process. **Wrong the moment there are two replicas** — swap the bucket store for
Redis; the call sites do not change.

`X-Forwarded-For` is deliberately not trusted, because it is client-controlled
unless a known proxy sets it. Behind a real proxy, run uvicorn with
`--proxy-headers --forwarded-allow-ips=<proxy>` so Starlette rewrites
`request.client` properly.

### Audio never served statically

No `StaticFiles` mount. Every byte goes through `GET /voices/{id}/sample` or
`GET /generations/{id}/audio`, which validate the ID against a strict pattern
and re-check the resolved path stays inside the storage root. That gives
per-request authorization somewhere to live when accounts arrive, and keeps the
on-disk layout private.

### Streaming

Chatterbox exposes no incremental generation API as of 2026-09-11 (verified by
source inspection). Even if it did, this product generates an utterance the user
then plays — streaming would add a WebSocket layer for no user-visible gain.

If the product becomes a live voice agent, streaming stops being optional, and
the model choice changes with it: CosyVoice 2 (Apache-2.0, 150 ms first-packet
streaming) is the alternative called out in
[MODEL_RESEARCH.md](./MODEL_RESEARCH.md#5-alternative-models). The
`EngineInfo.supports_streaming` flag already exists so clients can branch on it.

---

## How a voice is represented

Different models represent speaker identity differently. The abstraction covers
all of them:

| Model | Representation | Cacheable? |
|---|---|---|
| **Chatterbox** | `Conditionals`: speaker embedding + prompt speech tokens + S3Gen prompt features | **Yes** — `.save()` / `.load()` |
| XTTS-v2 | GPT conditioning latents + speaker embedding | Yes |
| F5-TTS | Reference mel + reference transcript | Partially |
| OpenVoice | Tone-colour embedding | Yes |
| CosyVoice 2 | Prompt speech tokens + speaker embedding | Yes |

`VoiceProfile` therefore always carries `reference_path` (the portable ground
truth) and *optionally* `conditioning_path` (a disposable, model-revision-
specific cache). An engine that cannot cache leaves it `None` and re-derives
from the reference every call; the rest of the application is unaffected.

**What is not stored:** no embeddings in the database. The conditioning bundle
is a multi-megabyte tensor blob tied to one model revision, so it lives beside
the audio on disk where it can be deleted or regenerated freely. The DB holds
metadata and paths.

This also means a model upgrade is safe: delete every `conds.pt`, and the next
generation for each voice re-derives conditioning from the reference audio
automatically (`_apply_conditioning` falls back and logs a warning on any cache
load failure).

---

## Adding another model

1. Implement `VoiceCloningEngine` in `ai/your_engine.py` — five methods.
2. Register a factory in `ai/registry.py`.
3. Set `VOICE_ENGINE=your_engine`.

Nothing in `backend/app/` or `frontend/` changes. The frontend reads its
language list, sample rate, limits and watermark status from
`GET /api/v1/system/info`, which is generated from `EngineInfo` — so a new model
with different languages updates the UI with no frontend deploy.

`MockEngine` is the proof that the abstraction is real: it implements the full
contract, including the conditioning-cache round trip, in ~150 lines with no
torch, and the entire API test suite runs against it.

---

## Future mobile clients

```
        Web (Next.js)  ─┐
     Android (Kotlin)  ─┼──→  Same REST API  ──→  VoiceCloningEngine
         iOS (Swift)   ─┘         /api/v1
```

The API is already client-agnostic, deliberately:

- **All business logic is server-side.** Validation, preprocessing, consent
  enforcement, conditioning and synthesis live in `services/` and `ai/`. The web
  frontend has no logic a mobile client would need to reimplement.
- **camelCase JSON** decodes cleanly into Kotlin data classes and Swift
  `Codable` structs with no custom key strategy.
- **Multipart upload** is what `MediaRecorder`, Android's `MediaRecorder` and
  iOS `AVAudioRecorder` all produce naturally. The server sniffs the container,
  so an Android `.m4a` or an iOS `.caf` needs no client-side conversion.
- **Range-capable audio URLs** are what `ExoPlayer` and `AVPlayer` expect.
- **Capability discovery** via `/system/info` means a shipped mobile app picks
  up new languages and limits without a store update.
- **Stable error codes** (`consent_required`, `invalid_audio`, `rate_limited`, …)
  are what clients branch on, not HTTP status alone or message text.
- **Versioned prefix** `/api/v1` lets a v2 land without breaking shipped apps.

The one thing a mobile client needs that does not exist yet is **authentication**
— today the API is unauthenticated and single-tenant, which is fine for a
self-hosted MVP and not fine for a published app. That is Phase 2, and it slots
in at `api/deps.py`: `client_key()` becomes a user ID, and the repositories gain
an owner filter.
