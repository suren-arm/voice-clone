# Cloudflare Backend Feasibility Review

**Question asked:** why is the backend on Render instead of Cloudflare, and would moving it make the app cheaper or free?

**Method:** the repository was inspected directly (not assumed) for what the backend actually does — see [§ Current Deployment Architecture](#current-deployment-architecture). Cloudflare's current product capabilities and pricing were then checked against that inventory, not the other way around. `render.com` and `developers.cloudflare.com` are both unreachable from this session's network (confirmed by direct fetch attempts, consistent with earlier findings in this repository's own deployment docs) — every Cloudflare/Render pricing and limits figure below therefore comes from web search against third-party aggregators and cached copies of the official docs, cross-checked across at least two independent sources per figure, current as of **14 September 2026**. Where a figure could not be cross-checked, that is stated explicitly rather than presented as certain.

This is an investigation. **Nothing has been migrated.** No production configuration changed as part of this task.

---

## Contents

- [Executive Summary](#executive-summary)
- [Current Deployment Architecture](#current-deployment-architecture)
- [Why Render Is Currently Used](#why-render-is-currently-used)
- [Cloudflare Products Evaluated](#cloudflare-products-evaluated)
- [Workers Compatibility](#workers-compatibility)
- [FFmpeg Compatibility](#ffmpeg-compatibility)
- [TTS Compatibility](#tts-compatibility)
- [Voice Cloning Compatibility](#voice-cloning-compatibility)
- [PDF / Book Reader Compatibility](#pdf-book-reader-compatibility)
- [Filesystem Requirements](#filesystem-requirements)
- [Long-Running Jobs](#long-running-jobs)
- [Cloudflare Containers](#cloudflare-containers)
- [Cost Comparison](#cost-comparison)
- [Free Tier Analysis](#free-tier-analysis)
- [Performance Comparison](#performance-comparison)
- [Operational Complexity](#operational-complexity)
- [Security](#security)
- [Architecture Options](#architecture-options)
- [Decision Matrix](#decision-matrix)
- [Cost Matrix](#cost-matrix)
- [Recommended Architecture](#recommended-architecture)
- [Migration Plan](#migration-plan)
- [Risks](#risks)
- [Final Recommendation](#final-recommendation)
- [Final Questions, Answered](#final-questions-answered)

---

## Executive Summary

**Keep Render for the backend.** The backend is a stateful Python process that loads a ~350M-parameter PyTorch model into memory, shells out to `ffmpeg` and `espeak-ng` as native subprocesses, and serves requests that legitimately run for minutes. Every one of those three facts individually rules out a like-for-like move to Cloudflare Workers — Workers has a hard 128 MB memory ceiling with no override, no subprocess execution, and no native binaries. That is not a close call.

**Cloudflare Containers is a real, technically-capable alternative platform** for this exact workload (Docker image, `standard-1` instance = 0.5 vCPU / 4 GiB RAM / 8 GB disk, comparable to or better than Render's current Starter plan) — but its **disk is ephemeral by design**: every container restart starts from a fresh image, and this app's cloned voices, generation history and SQLite database currently live on a plain disk mount. Moving to Containers unchanged would silently delete user data on every restart. Making it safe means re-architecting storage onto Durable Objects and/or R2 — a real engineering project, not a redeploy.

**What genuinely is a good Workers fit today, and costs nothing extra to build:** the four AI story-generation providers are already a thin, stateless HTTP proxy with no local compute (`app/services/ai_providers/`). That slice could move to a Worker essentially as-is. Given it is four HTTP calls behind one interface already, the benefit of doing so — shaving a network hop for a feature gated behind an LLM call anyway — is marginal, and splitting one small backend into two deployed services has a real complexity cost. **Recommendation: don't split it out unless request volume or Render cost actually becomes a problem; if that day comes, this is the piece to move first.**

**On cost:** Cloudflare hosting for the frontend is already free (Cloudflare Pages, static export — already in use). Migrating the backend would not make the *application* free: the dominant cost driver isn't hosting, it's compute for a real ML model, and Cloudflare's own compute products either can't run that model (Workers) or need to be paid for at rates that, for a resident model process, land in the same $5-$25/month range as Render Starter/Standard — not the free tier. External AI provider costs (OpenAI/Gemini/Anthropic) are unaffected by *any* hosting choice: they're billed by the vendor, not by where the request originates.

**One real, low-cost, low-risk improvement Cloudflare already provides today**, independent of any backend migration: keep using Cloudflare Pages for the frontend, and optionally add R2 as a cheaper long-term store for generated audio if storage growth ever becomes the bottleneck (not needed at current scale — Render's disk is 5 GB at $0.25/GB/month = $1.25/month).

---

## Current Deployment Architecture

Verified directly from the repository (`render.yaml`, `backend/Dockerfile.render`, `docker-compose.yml`, `frontend/next.config.ts`, `.github/workflows/deploy-cloudflare-pages.yml`, `backend/requirements.txt`, and the actual service code) — not assumed.

```
Browser
   │
   ▼
Cloudflare Pages  (static export: frontend/next.config.ts, CLOUDFLARE_BUILD=1 → output: 'export')
   │  HTML/CSS/JS only -- no server, no Workers, no Functions, no wrangler config anywhere in this repo
   │  NEXT_PUBLIC_API_URL baked in at build time
   ▼
HTTPS
   ▼
Render Web Service  (backend/Dockerfile.render, plan: starter, region: oregon)
   │  FastAPI + Uvicorn, one process, one worker (CMD: --workers 1)
   ▼
FastAPI backend (Python 3.11, SQLAlchemy 2 + SQLite on a mounted persistent disk)
   │
   ├── Voice cloning: Chatterbox (PyTorch, chatterbox-tts==0.1.7)
   │     CHATTERBOX_VARIANT=turbo (350M params) in production
   │     Model loaded once per process, resident in RAM for the process lifetime
   │
   ├── Default-voice TTS: espeak-ng, invoked via subprocess (ai/espeak_engine.py)
   │     en / hy / hyw / ru voices
   │
   ├── AI story generation: 4 optional external HTTP APIs, pure proxy, no local compute
   │     OpenAI · Gemini · Anthropic · self-hosted Ollama (app/services/ai_providers/)
   │
   ├── Book Reader: PDF/HTML extraction, pure Python + lxml, no native ML deps
   │     pypdf (PDF) · trafilatura (HTML) · httpx (SSRF-safe URL fetch)
   │
   ├── Audio pipeline: ffmpeg, invoked via subprocess (ai/audio_mix.py, ai/audio_processing.py)
   │     container decode → background-ambience mixing (sidechaincompress) → speed (atempo)
   │
   └── Local persistent disk (/app/storage, 5 GB Render disk)
         voices/<id>/reference.wav + conds.pt (cloning cache) + metadata.json
         generated/<id>.wav
         voice_studio.db  (SQLite)
```

No queue, no worker pool, no background-job framework (Celery/RQ/arq/Dramatiq — none present). Every request is handled synchronously, in-process, by the one Uvicorn worker Render runs.

**What runs where, precisely:**

| Question | Answer | Evidence |
|---|---|---|
| Backend runtime | Python 3.11, single process | `backend/Dockerfile.render` |
| Backend framework | FastAPI + Uvicorn (1 worker) | `Dockerfile.render` CMD |
| Frontend framework | Next.js 15 (App Router), static-exported | `frontend/next.config.ts` |
| AI/TTS run locally | Yes — Chatterbox (PyTorch) + espeak-ng | `ai/chatterbox_engine.py`, `ai/espeak_engine.py` |
| External AI APIs | Yes — OpenAI/Gemini/Anthropic/Ollama, story text only, no audio | `backend/app/services/ai_providers/` |
| FFmpeg | Yes — 3 distinct uses via `subprocess.run` | `ai/audio_mix.py`, `ai/audio_processing.py` |
| PDF parsing | Yes — pypdf | `backend/app/services/documents/pdf_extractor.py` |
| HTML extraction | Yes — trafilatura | `backend/app/services/documents/web_extractor.py` |
| Temp files | Yes — `storage/tmp/`, cleaned on boot | `backend/app/services/storage.py` |
| Uploaded files stored locally | Yes — voice reference audio, permanently | `LocalStorage.reference_path` |
| Long-running requests | Yes — up to 300s client timeout on narration | `frontend/src/services/speech.ts`, `books.ts` |
| Background jobs | **No** — none exist; everything is synchronous request/response | grep across `backend/`, `ai/` |

---

## Why Render Is Currently Used

Not a guess — the repository states its own reasoning, and it checks out against the evidence above:

> *"Cloudflare cannot run the backend at all: Workers has no PyTorch runtime, so the split is Cloudflare for the frontend and an ordinary container host for the backend."* — `docs/DEPLOYMENT.md`

That claim is verified correct (see [Workers Compatibility](#workers-compatibility)). The concrete reasons Render specifically, over other container hosts, per `render.yaml`'s own comments:

1. Builds a plain Dockerfile with no platform-specific rewrite (`backend/Dockerfile.render` is a normal Docker build).
2. Offers a persistent disk for `storage/` and the Hugging Face model cache with no separate volume service to configure.
3. Needs no GPU — Chatterbox Turbo (350M) runs at usable speed on CPU.

One inaccuracy worth flagging in the repo's own comments, found during this review: `render.yaml` says *"Chatterbox Nano (110M params)"* is what justifies Starter over Free — but the code (`ai/chatterbox_engine.py`) explicitly does **not** offer a Nano variant (no such checkpoint exists in the pinned `chatterbox-tts==0.1.7` package), and production actually runs **Turbo (350M)**. The comment is stale; it doesn't change the underlying conclusion (Render is still needed either way), but it should be corrected for accuracy — not fixed in this task per its own instructions, noted here for follow-up.

---

## Cloudflare Products Evaluated

| Product | Role considered | Verdict for this app |
|---|---|---|
| **Cloudflare Pages** | Static frontend hosting | **Already in use.** Correct fit, no change recommended. |
| **Cloudflare Workers** | Full backend replacement | **Not practical** — see below. |
| **Workers (Node.js compat)** | Full backend replacement | Irrelevant — the backend is Python, not Node; compat mode doesn't add PyTorch/native-binary support anyway. |
| **Pages Functions** | Lightweight backend routes | Same underlying runtime as Workers (same 128 MB, same no-subprocess sandbox) — same verdict. |
| **Cloudflare Containers** | Full backend replacement | **Technically capable, not a drop-in** — see [§ Cloudflare Containers](#cloudflare-containers). |
| **Durable Objects** | Stateful coordination / SQLite-backed persistence | Relevant *only* if Containers is pursued, to survive ephemeral container disk. Not relevant to Workers-alone. |
| **Cloudflare Queues** | Background job execution | Would be needed for any Workers-based long-running job, but doesn't solve the memory/native-binary problem underneath — moot until that's solved. |
| **Cloudflare R2** | Object storage for audio/PDFs | Viable, egress-free, $0.015/GB-month. Not currently needed — see [§ Filesystem Requirements](#filesystem-requirements) on why not to reach for it prematurely. |
| **Cloudflare D1** | SQL database | Would replace SQLite if the backend ever left a single-process persistent-disk model. Not needed today. |
| **Cloudflare KV** | Key-value cache | No current use case in this app (no session cache, no feature-flag store). |
| **Workers AI** | Managed inference (TTS, LLM, etc.) | Now includes third-party voice-cloning-capable TTS models (MiniMax Speech 2.8, ElevenLabs, Deepgram Aura) as of 2026 — see [§ Voice Cloning Compatibility](#voice-cloning-compatibility) for why this is a *different* architecture, not a way to run the existing Chatterbox pipeline. |

---

## Workers Compatibility

**Verdict: NOT PRACTICAL.**

Checked against the actual backend, not against Workers' marketing:

| Requirement | Workers support | Source |
|---|---|---|
| Python | Via Pyodide (WebAssembly), Python 3.13+, pure-Python packages plus some with dynamic libs | Cloudflare Workers Python docs |
| Subprocess execution | **No.** "Anything that touches the filesystem, spawns subprocesses, or opens raw sockets will fail at runtime" | Cloudflare Workers Python docs |
| Native libraries (PyTorch, ffmpeg) | **No.** Pyodide runs WASM-compiled pure-Python-adjacent packages; PyTorch's C++/CUDA core and the `ffmpeg` binary are not WASM targets Workers support | Cloudflare Workers Python docs |
| Filesystem | Ephemeral, **in-memory only**, wiped when the isolate is destroyed, not shared across isolates | Cloudflare Workers Python docs |
| Memory per isolate | **128 MB hard limit — not raisable on any plan** | Cloudflare Workers limits |
| CPU time (paid plan) | 30s default, up to 5 min ceiling per HTTP request | Cloudflare Workers pricing/changelog |
| Request body size | 100 MB (Free/Pro), 200 MB (Business), 500 MB (Enterprise) | Cloudflare Workers limits |
| Subrequests | 50/request (Free), 10,000/request (Paid) | Cloudflare Workers limits |

**Three independent, each-sufficient reasons this backend cannot run on Workers unchanged:**

1. **The 128 MB memory ceiling is a hard platform constraint**, stated explicitly as not raisable by upgrading plans. Chatterbox Turbo alone is ~350M parameters — roughly **1.4 GB in float32**, over 10× the entire isolate budget, before PyTorch's own runtime overhead or a single request is served.
2. **No subprocess execution, anywhere, at any tier.** `ffmpeg` and `espeak-ng` are both invoked via `subprocess.run()` in this codebase (`ai/audio_mix.py`, `ai/audio_processing.py`, `ai/espeak_engine.py`). There is no WASM build of either shipped or usable this way inside a Worker's sandbox.
3. **No persistent filesystem.** Voice reference audio and generation history need to outlive a single request; Workers' filesystem is in-memory and isolate-scoped, gone the moment the isolate recycles.

This is not a "some tuning needed" situation. It is a hard architectural mismatch on three independent axes, any one of which alone is disqualifying.

---

## FFmpeg Compatibility

**Verdict: NO on Workers. YES, unchanged, on Containers.**

The exact current usage, read from the code:

| File | Use | Invocation |
|---|---|---|
| `ai/audio_processing.py` | Decode any uploaded container (WebM/Opus, MP4/AAC, etc.) to mono float32 PCM | `subprocess.run(["ffmpeg", ...], capture_output=True)`, piped via stdin/stdout, no temp file |
| `ai/audio_mix.py` `mix_with_background()` | Mix narration with a looped ambience track, sidechain-ducked so the ambience never masks speech | `subprocess.run`, reads/writes real WAV files on local disk |
| `ai/audio_mix.py` `apply_speed()` | Time-stretch narration via `atempo` (no pitch shift) | `subprocess.run`, reads/writes local files |

This is real, shell-executed FFmpeg with a real `-filter_complex` graph (`aformat`, `asplit`, `sidechaincompress`, `amix`, `alimiter`) — not a candidate for FFmpeg-WASM. FFmpeg-WASM builds are real but come with materially reduced codec support, no reliable `sidechaincompress`, and — critically — they still don't solve Workers' 128 MB memory ceiling, since the WASM runtime and its buffers have to fit inside the same isolate as everything else. **The task's own instruction not to hand-wave "WASM exists, therefore fine" is correct: proven, it is not fine for this workload.**

On **Cloudflare Containers**, this is moot: a Container is a real Linux environment running the same Docker image this app already builds (`backend/Dockerfile.render` already installs `ffmpeg` via `apt-get`). FFmpeg runs completely unchanged.

---

## TTS Compatibility

| TTS Component | Runs Today | Cloudflare Worker Compatible? | Reason |
|---|---|---|---|
| Chatterbox cloned-voice synthesis (en) | Local, PyTorch, resident model | **No** | 128 MB isolate limit; no native PyTorch runtime |
| espeak-ng default voice — English | Local subprocess | **No** | No subprocess execution in Workers |
| espeak-ng default voice — Armenian (hy/hyw) | Local subprocess | **No** | Same |
| espeak-ng default voice — Russian (ru) | Local subprocess | **No** | Same |
| Background-ambience mixing (all TTS output) | Local ffmpeg subprocess | **No** | Same |
| Reading-speed adjustment (atempo) | Local ffmpeg subprocess | **No** | Same |

Every row is "No" for the same underlying reasons already established — this table exists to be explicit per-component rather than asserting one blanket answer, as asked. All rows flip to "Yes, unchanged" under **Cloudflare Containers** specifically, because Containers run the real Docker image.

**A separate, real option that is not "run this on Cloudflare" but is worth naming honestly:** Workers AI's model catalog now includes third-party TTS models with cloning capability (MiniMax Speech 2.8, ElevenLabs) as managed, pay-per-call inference. That is not a migration of this code — it is *replacing* Chatterbox with a different vendor's hosted model, with different voice quality, different licensing, and an ongoing per-generation cost instead of a fixed monthly compute cost. It's a legitimate option to evaluate on its own merits some day; it is not evidence that "Cloudflare can run the current TTS pipeline," and this report does not conflate the two.

---

## Voice Cloning Compatibility

**Verdict: DEPENDS — no on Workers, no on Workers AI as a same-pipeline answer, technically yes on Containers, yes on a third-party API if you're willing to replace the model.**

Reviewed directly from `ai/chatterbox_engine.py`:

- Runs a **local ML model**: yes — `chatterbox-tts==0.1.7`, which pulls PyTorch, torchaudio, transformers, librosa.
- Needs PyTorch: yes, unconditionally.
- Needs CUDA: no — this deployment runs `DEVICE=cpu`, `CHATTERBOX_VARIANT=turbo` specifically because CPU inference is fast enough at 350M params (the 0.5B multilingual variant is documented in this repo's own `docs/PERFORMANCE.md` as "well above 1.0 RTF... expect minutes" on CPU — explicitly not chosen for that reason).
- Needs CPU-heavy inference: yes, every generation.
- Needs model files: yes — downloaded from Hugging Face on first load, cached (`HF_HOME`), not vendored in the image.

None of that runs inside a Workers isolate, for the reasons already given. It runs unchanged inside a Container with enough memory — `standard-1` (0.5 vCPU / 4 GiB) has more headroom for the model + PyTorch overhead than Render's current Starter plan (0.5 CPU / 512 MB — see the RAM discrepancy flagged in [§ Risks](#risks)).

---

## PDF / Book Reader Compatibility

**Verdict: YES for the extraction logic itself, on Workers — WITH real caveats on size limits and no persistence story. PARTIALLY overall, because it currently shares a process with the parts that can't move.**

This is the one part of the backend that was *not* immediately disqualified, and deserved real scrutiny rather than an assumed "PDF parsers don't run on serverless" verdict:

- **`pypdf`** is pure Python, no native/C extensions, no torch. `import pypdf; pypdf.PdfReader(...)` is the kind of pure-Python package Pyodide-based Python Workers can plausibly load.
- **`trafilatura`** depends on `lxml`, which is a C extension (libxml2/libxslt bindings) — this is exactly the "many packages that rely on dynamic libraries" category Cloudflare's Python Workers docs mention as sometimes-supported, sometimes-not. This was not verified working in this review; it would need an actual proof-of-concept deploy to confirm, not an assumption either way.
- **Size**: this app enforces `MAX_PDF_BYTES = 20 MiB` and `MAX_PDF_PAGES = 500` (`backend/app/core/config.py`) — comfortably inside Workers' 100 MB request body limit on the Free/Pro plan tier.
- **SSRF-safe URL fetching** (`backend/app/services/documents/security.py`) — DNS-resolved IP validation, manual redirect re-validation, streamed byte caps — is pure `httpx`-based logic with no native deps; this genuinely could run on a Worker using `fetch()`.
- **No persistent output needed for long**: extracted text is stored in SQLite with a 24-hour retention sweep (`document_retention_hours`), not kept forever like voice/generation data — so this is exactly the kind of short-lived data the task correctly warns not to reach for R2 for.

**Why "PARTIALLY" and not "YES" as a recommendation:** the extraction step could plausibly run on a Worker in isolation, but the very next step for every Book Reader request is narration — which needs Chatterbox or espeak-ng, neither of which can run there. Splitting "extract on Workers, narrate on Render" adds a network hop and two deploy targets for a feature that, end to end, is bottlenecked by the part that can't move anyway. Not recommended as a standalone migration; see [§ Architecture Options](#architecture-options) Option C for where this could fit in a broader split, and why this report doesn't recommend forcing it in isolation.

---

## Filesystem Requirements

Grepped directly, not assumed:

| Use | Location | Lifetime | Cloudflare replacement, if migrated |
|---|---|---|---|
| Voice reference audio | `storage/voices/<id>/reference.wav` | **Permanent**, until the user deletes the voice | R2 (object storage) — appropriate here, this data is genuinely long-lived |
| Cloning conditioning cache | `storage/voices/<id>/conds.pt` | Permanent, regenerable | R2, or regenerate on demand |
| Voice metadata mirror | `storage/voices/<id>/metadata.json` | Permanent | D1 or R2 |
| Generated speech | `storage/generated/<id>.wav` | Permanent (until user deletes / history retention) | R2 — appropriate |
| SQLite database | `storage/voice_studio.db` | Permanent, the system of record | D1, or Durable Objects SQLite storage — **not** a file on ephemeral disk |
| Scratch/tmp | `storage/tmp/` | Seconds — cleaned on boot and after use | In-memory buffer; **R2 would be the wrong tool here** — exactly the case the task warned against |
| Extracted book text | SQLite, 24h retention | Hours, not permanent | D1, or leave alone if Book Reader stays on Render |
| FFmpeg intermediate files | Sibling temp files during mix/speed adjustment, deleted immediately after | Seconds | N/A — this step can't run off-Render at all currently |

The honest summary: **most of what's on disk is genuinely long-lived and would need R2 + D1 (or Durable Objects) if the backend ever moved off a single persistent-disk host** — that part of a migration is real work, not a rubber stamp. The only place the task's caution about *not* over-reaching for R2 actually applies here is the two short-lived categories (scratch audio-mix temp files, book-extraction temp state), which should stay as in-memory/ephemeral concerns regardless of host.

---

## Long-Running Jobs

Read directly from the frontend's own client-side timeouts, which reflect what the backend is actually expected to take:

| Operation | Client timeout | Why it can be long |
|---|---|---|
| `POST /api/v1/speech` (any narration, incl. Fairy Tale) | **300 s (5 min)** | Chapter/book-length text is chunked (900 chars/chunk) and synthesized sequentially; CPU-bound inference, not I/O |
| `POST /api/v1/books/{id}/narrate` | **300 s** | Same synthesis path, capped per-request at `max_book_narration_chars=12,000` |
| `POST /api/v1/books/upload` (PDF ingest) | 120 s | Parsing + validation of up to 500 pages |
| `POST /api/v1/books/from-url` | 60 s | SSRF-safe fetch + extraction |

This repo's own `docs/PERFORMANCE.md` documents the underlying tradeoff precisely: at RTF (real-time factor) 1.0 on CPU, a 2000-character request takes ~2.5 minutes — "borderline, cap the text length"; above RTF 3.0, "queue required." Production intentionally runs the fastest CPU-viable variant (`turbo`) to stay in the synchronous-safe zone, and **there is currently no server-side generation timeout at all** (a dead `GENERATION_TIMEOUT_SECONDS` setting was found and removed earlier in this repository's history precisely because nothing enforced it) — a request is bounded only by Render's own proxy timeout.

**Compared with Cloudflare:** Workers' per-HTTP-request CPU-time ceiling is 5 minutes on the paid plan — coincidentally close to this app's own client timeout — but that's irrelevant given Workers can't run the workload at all (see above). On **Containers**, wall-clock duration is governed by the container's own lifecycle (it sleeps after an idle timeout, not mid-request), so a multi-minute synchronous narration request behaves the same as it does on Render today — no Queues, Durable Objects, or Workflows required *for this specific pattern*, because Render's own current architecture already doesn't use a queue either. If book-length narration volume grew enough to want async processing, that would be a real improvement to make on **either** platform, not something unique to Cloudflare.

---

## Cloudflare Containers

**Verdict: technically the closest Cloudflare equivalent to what Render does today. Not a drop-in. GA since April 2026, genuinely current-generation, not a beta product to be wary of on maturity grounds alone.**

Directly compared against Render Starter, using the current instance-type table:

| | Render Starter (current) | Cloudflare Containers `standard-1` |
|---|---|---|
| vCPU | 0.5 | 0.5 |
| RAM | **512 MB** | **4 GiB** |
| Disk | 5 GB persistent, $0.25/GB/mo | 8 GB, **ephemeral** |
| Docker | Plain Dockerfile | Plain Docker image |
| Python/native libs | Full support (it's a real VM) | Full support (it's a real container) |
| Base price | $7/month | Included in $5/mo Workers Paid (375 vCPU-min + 25 GiB-hr + 200 GB-hr/mo included, then metered) |
| Always-warm | Yes (paid tier, no spin-down) | No — sleeps on idle, cold-starts on next request |
| Persistence across restart | Yes (disk survives) | **No — disk is wiped on every restart** |
| Maturity | Long-established product | GA since 13 April 2026 |

**Comparison across every requested dimension:**

- **Docker compatibility**: equal — both run the same Dockerfile unmodified.
- **Python / native libraries (torch, ffmpeg)**: equal — both are real Linux environments.
- **AI models**: equal — model loading behaves identically in either.
- **Runtime duration**: Render is always-on; Containers sleep and cold-start, which reintroduces the model-load cold-start cost this repo just spent real effort eliminating from *boot* (see `f73f2fc` in this repo's own history: a 74s→4.7s fix for exactly this class of problem) — except here it would recur on every idle-then-request cycle, not once at deploy time.
- **Filesystem behavior**: this is the decisive difference. **Container disk is ephemeral by design** — confirmed from Cloudflare's own Containers docs: *"When a Container instance goes to sleep, the next time it is started, it will have a fresh disk... any data written directly to the container's filesystem, including SQLite databases, will be lost."* This app's entire storage model — SQLite DB, voice reference audio, generation history — sits on exactly that kind of plain disk mount today. Moving unchanged would silently delete user data on the first idle-then-restart cycle. Making it safe requires rewriting storage to go through Durable Objects (SQLite-backed, survives restarts) and/or R2 for the binary audio files — a genuine re-architecture of `backend/app/services/storage.py`, not a redeploy.
- **Startup time**: container boot itself is fast (100-300ms class, depending on image), but that figure is *container* cold start, not *this app's* cold start — model loading is the dominant cost here and is unaffected by which platform hosts the container.
- **Pricing**: active-use billing (pay only while a request is being handled or the container is explicitly kept warm) can be cheaper than an always-on Render instance *if* traffic is bursty and the operator accepts periodic cold starts; more expensive or roughly equal if kept warm continuously to avoid them, which for a model-loading workload is the realistic operating mode.
- **Production maturity**: GA for five months as of this review — real, not experimental, but with less of a track record than Render's years-old container hosting.

**Bottom line: possible, not free, not a clean win.** It would trade an always-on $7-8/month instance for a platform that's cheaper for bursty traffic and more expensive (in engineering time now, and likely in avoided-cold-start keep-warm cost later) for this app's actual usage pattern — a persistent model that should stay loaded.

---

## Cost Comparison

All figures are current published/aggregator pricing as of 14 September 2026, cross-checked across independent sources where possible (both `render.com` and `developers.cloudflare.com` are unreachable directly from this session — see the top of this document). **Account-specific actual billing was not available and is not invented — see [§ Render Cost Review](#render-cost-review-account-specific) below.**

| | Render (current) | Cloudflare Workers | Cloudflare Containers | Hybrid (Option C) |
|---|---|---|---|---|
| Base hosting | Starter: **$7/mo** | Free: $0; Paid: $5/mo | Included in $5/mo Workers Paid, metered beyond | Cloudflare Pages: $0 (already used) + Workers Paid $5/mo for the proxy slice |
| Persistent disk | 5 GB × $0.25/GB = **$1.25/mo** | N/A (no persistent disk on Workers) | N/A on the container itself — needs R2 (~$0.015/GB/mo) + Durable Objects | Render disk unchanged, $1.25/mo |
| Compute for the actual workload | Included in base price | **Cannot run the workload** | Metered: CPU $0.00002/vCPU-s beyond included 375 vCPU-min/mo | Render side unchanged |
| **Current total, hosting only** | **~$8.25/month** | N/A (not viable) | Roughly comparable to Render if kept warm; cheaper only if traffic is bursty enough to tolerate cold starts | ~$8.25/mo (Render) + $0-5/mo (Workers, likely within free tier at this app's request volume) |
| External AI (story generation) | Pass-through, vendor-billed | Same — hosting choice doesn't change this | Same | Same |

The AI-provider cost line is identical in every column because **it is determined by usage of OpenAI/Gemini/Anthropic, not by where the HTTP request that calls them originates.** This is the distinction the task explicitly asked to keep clear, and it holds regardless of architecture.

### Render cost review (account-specific)

From the repository configuration alone (`render.yaml`):

- Service type: `web`, `runtime: docker`, `plan: starter`
- Persistent disk: 5 GB, named `voice-clone-storage`, mounted at `/app/storage`
- Region: `oregon`
- No GPU service configured (correctly — CPU/turbo is what's deployed)

**What is not visible from the repository, and is not invented here:** the actual current Render invoice, whether any additional Render add-ons (custom domains, team seats, support tier) are active on the account, and whether usage-based overages (e.g. bandwidth beyond plan limits) have been incurred. Confirm these in the Render dashboard's Billing tab directly.

---

## Free Tier Analysis

**"Cloudflare has a free plan" is true and, on its own, tells you nothing about whether this app can run on it.** Checked against the actual workload:

| Free-tier limit | This app's actual demand | Fits? |
|---|---|---|
| Workers Free: 100,000 requests/day | Plausibly fits traffic-wise for a small-scale app | **Irrelevant** — Workers can't run the backend at all, see above |
| Workers Free: 10ms CPU time/request | A single Chatterbox synthesis call is **seconds to minutes** of CPU time | **Fails by 3-4 orders of magnitude**, independent of the memory/subprocess disqualifiers |
| R2 free tier: 10 GB storage, 1M Class A + 10M Class B ops/month, free egress | Voice + generation audio at current scale would plausibly stay under this for a while | Fits, **if** the app were re-architected to use R2 — not automatic |
| Containers: included in $5/mo Workers Paid (25 GiB-hr mem, 375 vCPU-min, 200 GB-hr disk/mo) | A model that should stay loaded and warm will burn through 375 vCPU-minutes (6.25 hours) fast under any real traffic | **Not free in practice** — becomes metered quickly for a resident-model workload |

**Direct answer to "could the app realistically run entirely free": NO**, not for the backend, under any Cloudflare product evaluated. The CPU-time-per-request alone on Workers' free tier is off by orders of magnitude for a real ML inference workload, and Containers' generous-sounding included compute is sized for bursty, short-lived jobs — not a process meant to hold a 350M-parameter model resident in memory continuously.

**What genuinely is free today, and already is:** the frontend, on Cloudflare Pages. That's not a hypothetical — it's the app's actual current architecture.

**External AI costs are separate and real, regardless of hosting.** OpenAI and Anthropic have no free tier for API usage; Gemini has a genuine free tier on Flash-class models (documented elsewhere in this repo's own README as the "no mandatory paid key" answer, alongside self-hosted Ollama). None of that changes based on whether the request that calls them originates from Render or from a Cloudflare Worker.

---

## Performance Comparison

No universal winner — each row depends on what's being compared:

| | Render (current) | Cloudflare (Workers, where applicable) | Cloudflare (Containers) |
|---|---|---|---|
| API latency (simple JSON) | Normal HTTP round-trip to Oregon | Faster for edge-local — Workers run at the edge, closer to the user globally | Similar to Render — a Container runs in one Cloudflare region per instance, not distributed by default |
| Cold start | N/A on Starter (always warm); would be ~74s→4.7s on a from-scratch boot after this repo's own recent fix, then model load on first synth request | Not applicable — can't run the workload | Container boot: sub-second to a few hundred ms; **then the same model-load cost as anywhere else** on first request after a cold container |
| TTS generation (once warm) | CPU-bound, RTF-dependent, same regardless of host — this is compute, not network | N/A | Identical to Render, same CPU class assumption |
| Voice cloning | Same — bound by CPU/model, not host | N/A | Same |
| FFmpeg mixing | Sub-second per operation, local disk I/O | N/A | Same, local-to-container disk I/O |
| PDF parsing | Fast, pure Python | Plausible on Workers (pure Python path), unverified for trafilatura's lxml dependency | Same as Render |
| Static frontend delivery | N/A (Cloudflare Pages already serves this) | **This is what Workers/Pages already does today, and does well** | N/A |

The honest conclusion: **for every CPU-bound operation this app actually performs (TTS, cloning, ffmpeg), performance is a function of CPU class and whether the model is warm — not of which platform hosts the container.** Cloudflare's edge-network latency advantage is real and already captured, today, by using Cloudflare Pages for the frontend. It would not meaningfully change the latency of a 30-second Chatterbox synthesis call regardless of which backend host serves it.

---

## Operational Complexity

| | Current (2 services) | Workers-only | Hybrid (Option C: 3 services) | Full Cloudflare (Option D: Containers, still ~2-3 services) |
|---|---|---|---|---|
| Number of deployed services | 2 (Cloudflare Pages, Render) | N/A — not viable | 3 (Pages, Worker, Render) | 2-3 (Pages, Container, optionally a thin Worker gateway) |
| Environment variables to manage | Split across 2 dashboards already (documented in README's Configuration section) | N/A | Split across 3 | Split across 2-3, plus container-specific env passthrough |
| Deploy pipelines | 2 (`deploy-cloudflare-pages.yml`, Render's own git-push auto-deploy) | N/A | 3 | 2-3, plus learning Cloudflare's container deploy tooling (`wrangler`, new to this repo — currently zero wrangler config exists anywhere) |
| Local development | `docker-compose.yml`, single `make dev`-style flow, already working | N/A | Same, plus a second local dev loop for the Worker | Same backend dev loop; would additionally need `wrangler dev` familiarity |
| Monitoring/logs | 1 place to look for backend logs (Render dashboard) | N/A | 2 places (Render + Cloudflare dashboard) | 1-2 places |
| Failure recovery | Well-understood Render restart/redeploy behavior | N/A | Two independent failure domains to reason about | New Cloudflare Container failure/restart semantics, less field experience in this repo's own history than Render's |

The task's own framing is exactly right here: *"An architecture that saves $2 but adds several Cloudflare products may not be a good tradeoff."* This app's current 2-service split is already about as simple as this workload permits. Every option that keeps the ML/FFmpeg workload off Cloudflare (current, and Option C without moving the AI proxy) adds the least complexity for the least benefit change. Full Containers migration (Option D) adds a third storage system (Durable Objects/R2) and a new deploy toolchain (`wrangler`) that has zero footprint in this repo today, in exchange for a hosting bill that is not clearly lower once kept warm.

---

## Security

**What Cloudflare would add, if any component moved there:**

- Edge-level DDoS protection and WAF — already partially benefiting the app today, since Cloudflare Pages sits in front of the static frontend.
- Workers' own rate limiting / bot-management products, if the AI-proxy slice moved there.

**What must not regress, verified against the current codebase:**

- **AI API keys remain backend-only.** Confirmed: `OPENAI_API_KEY`/`GEMINI_API_KEY`/`ANTHROPIC_API_KEY` are read only in `backend/app/services/ai_providers/*`, never serialized into any API response (`GET /api/v1/ai/providers` returns only a boolean `available` per provider — verified directly in `backend/app/schemas/ai_provider.py`). This holds regardless of host; a Worker-based proxy would need the same discipline re-verified, not assumed, if ever built.
- **Upload validation.** Audio and PDF validation (magic bytes, size caps, format sniffing) is backend logic, portable in principle to a Worker for the PDF path specifically — but moving it there without moving the narration step that follows it doesn't reduce attack surface, just relocates part of it.
- **SSRF protections** (`backend/app/services/documents/security.py`) — scheme allowlist, per-redirot-hop IP re-validation, streamed byte caps. This is `httpx`-based, portable logic; a documented residual limitation (DNS-rebinding) already exists and would need to be re-evaluated, not assumed safe, in any new runtime.
- **Internal service endpoints.** N/A today — there are no internal-only endpoints in this architecture; `/health` and the API are both meant to be public.

No security regression was found in the current architecture that a Cloudflare migration would fix, and no security improvement was found that isn't already captured by the frontend already being on Cloudflare Pages.

---

## Architecture Options

### Option A — Keep Current Architecture

```
Cloudflare Pages → Frontend
Render           → Entire Backend
```

**Pros:** Already working, already deployed, already tested (see this repo's own CI: 5 green jobs including a Docker build smoke-test). Zero migration risk. Simplest possible split for this workload — one place each for "static" and "everything else."
**Cons:** Backend cost is fixed at ~$8.25/month regardless of traffic (Render Starter + disk); no edge distribution for the API itself (single region, Oregon).
**Cost:** ~$8.25/month hosting + vendor-billed AI usage.

### Option B — Move Entire Backend to Cloudflare

**Not technically realistic**, as established above. Workers cannot run PyTorch, ffmpeg, or any subprocess at all; Containers could run the code but not the storage model, unchanged. A "full Cloudflare, Workers-only" backend is not a real option for this application — stated clearly, as the task requires, rather than hedged.

### Option C — Hybrid

```
Cloudflare
├── Pages           → frontend (already in place)
├── Worker          → AI story-generation proxy (OpenAI/Gemini/Anthropic/Ollama passthrough)
└── (optional) R2   → generated-audio archive, only if storage growth ever becomes real

Render
├── Voice cloning (Chatterbox)
├── Default-voice TTS (espeak-ng)
├── FFmpeg (mixing, speed, decode)
├── Book Reader (PDF/HTML extraction, kept alongside narration rather than split)
└── SQLite + persistent voice/generation storage
```

**Pros:** The one piece that's a genuinely easy, low-risk Workers fit (`app/services/ai_providers/` is already a clean, provider-agnostic abstraction with no local compute) moves to the platform best suited for a thin stateless proxy. Everything CPU/memory-heavy stays where it already works.
**Cons:** A third deployed service, a third place to configure environment variables and read logs, and a new dependency (Cloudflare account/token, `wrangler`) with zero current footprint in this repo. The benefit — shaving one network hop off a feature that's already bottlenecked by an LLM's own multi-second response time — is small relative to that cost.
**Cost:** Render unchanged (~$8.25/mo) + Workers Free tier (plausibly $0/month at this app's actual request volume — see [§ Free Tier Analysis](#free-tier-analysis)) or $5/mo if it grows past free-tier limits.
**Recommendation: worth doing only if/when Render's request volume or cost specifically becomes a pain point.** Not recommended as an immediate change — see [§ Recommended Architecture](#recommended-architecture).

### Option D — Cloudflare + Containers

```
Cloudflare Pages → Worker (thin gateway/router, optional) → Cloudflare Container (the whole current backend, unchanged image)
```

**Technically possible**, evaluated in full in [§ Cloudflare Containers](#cloudflare-containers) above. **Not recommended as things stand**, because:

1. Storage is not a redeploy — it's a rewrite of `backend/app/services/storage.py` and every repository/service that touches `storage_dir` onto Durable Objects + R2, to survive the platform's ephemeral container disk.
2. The always-on-vs-sleep-on-idle tradeoff works against a resident-model workload specifically: keeping a Container warm continuously to avoid re-paying model-load cost on every cold start erodes the "active-use billing is cheaper" argument that makes Containers attractive for bursty workloads in the first place.
3. Five months of GA maturity (since April 2026) is real but is meaningfully less field-proven than Render's much longer track record for exactly this kind of Docker-container-plus-persistent-disk workload.

Possible: **yes.** Practical for this app today: **no.** Cheaper: **not once kept warm — likely a wash or worse.** More complex: **yes, materially.**

---

## Decision Matrix

| Capability | Render | Workers | Containers | Hybrid (Option C) |
|---|---:|---:|---:|---:|
| Static frontend | Poor fit | Excellent | Poor fit | Excellent (via Pages, already used) |
| Simple REST API | Good | Excellent | Good | Excellent for the proxy slice |
| AI API proxy | Good | Excellent | Good | **Excellent — the one clean win** |
| Python backend | Excellent | Not viable (Pyodide/WASM, no native libs) | Excellent | Excellent (unchanged, on Render) |
| FFmpeg | Excellent | Not viable (no subprocess, ever) | Good (real container, but re-cold-starts) | Excellent (unchanged, on Render) |
| Local TTS model (Chatterbox/espeak) | Excellent (resident, always warm) | Not viable (128 MB ceiling) | Good, if kept warm; poor if allowed to sleep | Excellent (unchanged, on Render) |
| Voice cloning | Excellent | Not viable | Good, same caveat as above | Excellent (unchanged, on Render) |
| Large PDF processing | Good | Limited — extraction plausible, but disconnected from narration that must follow it elsewhere | Good | Good (unchanged, on Render) |
| Long-running task (minutes) | Good — no timeout enforced, bounded by proxy | Poor — even the 5-min CPU ceiling is irrelevant given the workload can't start | Good, while container stays awake | Good (unchanged, on Render) |
| Free-tier potential | No free tier at production-viable specs (Free plan's 512 MB/0.1 CPU spins down) | High for request volume, **zero for this app's actual CPU-per-request demand** | Generous included compute, consumed fast by a resident model | Realistic $0 for the proxy slice specifically |

---

## Cost Matrix

| Architecture | Hosting Cost | External AI Cost | Complexity | Recommendation |
|---|---:|---:|---|---|
| Current (Option A) | ~$8.25/mo | Vendor-billed, usage-based (unaffected by hosting) | Low | **Keep** |
| Workers only (Option B) | N/A | N/A | N/A | **Not viable — do not pursue** |
| Hybrid (Option C) | ~$8.25/mo (Render) + $0-5/mo (Workers) | Same as current | Medium (3rd service) | Adopt later, only if Render load/cost actually becomes a problem |
| Containers (Option D) | Roughly $5-15/mo depending on keep-warm strategy — not clearly less than Render once warm | Same as current | High (storage rewrite + new toolchain) | Not recommended now |

---

## Recommended Architecture

**Keep Option A (current architecture) for now.** It is already correctly matched to the workload: Cloudflare for what Cloudflare is unambiguously best at (static, globally-distributed frontend delivery, already in place and free), Render for what needs a real, persistent, resident-model Linux process (PyTorch, ffmpeg, espeak-ng, SQLite + disk).

**Cloudflare can still reduce cost/load without touching the backend**, and some of this may already be effectively in place via Cloudflare Pages' own defaults:

- **Frontend hosting**: already free, already done.
- **Caching**: Cloudflare's edge cache in front of the static frontend assets is Pages' default behavior — no extra work.
- **API gateway / lightweight AI routing**: the one concrete, low-risk improvement available (Option C's Worker), worth doing if and when Render's own request volume or cost specifically motivates it — not before, since the benefit today is marginal and the cost is a third deployed service.
- **R2**: available and cheap if generated-audio storage ever outgrows Render's 5 GB disk; premature today at $1.25/month for the current allocation.

---

## Migration Plan

**Not recommended to execute now** — this task is investigation, and the evidence doesn't show a clear benefit for an immediate move. If, in the future, Render's cost or the AI-proxy's latency specifically becomes a real operational problem, the phased path would be:

```
Phase 1
  Move only app/services/ai_providers/ (+ the /api/v1/stories/generate and
  /api/v1/ai/providers routes) to a Cloudflare Worker. No storage, no TTS,
  no ffmpeg touches this slice today -- it is already a clean proxy.

Phase 2
  Keep TTS, voice cloning, FFmpeg, Book Reader and all storage on Render,
  unchanged.

Phase 3
  Measure: does the Worker's added deploy/monitoring overhead actually pay
  for itself in latency or cost at real traffic? If not, revert -- this is
  a small, cheaply-reversible change specifically because it touches no
  storage and no other feature.

Phase 4
  Only if Render's cost specifically becomes the bottleneck (not before):
  evaluate Cloudflare Containers for the heavy backend, starting with a
  storage re-architecture onto Durable Objects/R2 as its own separate,
  fully-tested project -- not bundled with the platform move itself.

Phase 5
  Remove Render only after Phase 4's storage rewrite has run in parallel
  with the existing Render deployment long enough to prove no data loss
  across real restart/sleep cycles -- not on the strength of a successful
  first deploy.
```

No big-bang rewrite at any phase; each phase is independently reversible and independently low-risk.

---

## Risks

Ordered by what would bite first, **if** any migration were pursued (none is recommended now):

1. **The Render Starter RAM figure found during this review (512 MB) is lower than `render.yaml`'s own comment implies is needed to separate it from Free's "512MB RAM is too tight."** Both plans show as 512 MB RAM in current third-party-aggregated pricing (differing mainly in CPU allocation and spin-down behavior) — this could not be cross-checked against Render's own docs directly (blocked from this session's network). If accurate, running Chatterbox Turbo (≈1.4 GB in float32) plus PyTorch overhead on a 512 MB instance is tight enough to be a real, independent risk worth confirming directly in the Render dashboard — **separately from any Cloudflare question.**
2. **Container disk is ephemeral.** The single highest-risk item in any Containers migration: moving unchanged would silently delete user voices and history on the first idle-then-restart cycle. Any Containers work must treat the storage rewrite as a prerequisite, not a follow-up.
3. **Cold-start-on-every-sleep** for a resident-model workload undermines the "Containers are cheaper" argument specifically for this app, once kept warm to avoid it.
4. **Splitting the AI proxy into a separate service (Option C)** adds a second failure domain and a second place to check when something breaks — small but real, and not worth paying before there's a reason to.
5. **Cloudflare/Render docs being unreachable from this development environment** (confirmed both directions) means every pricing/limits figure in this report should be spot-checked against the live dashboards before being used to make a purchasing decision, not treated as final.

---

## Final Recommendation

**Keep Render for the backend.** Cloudflare Workers cannot run this workload under any interpretation of "compatible" — the 128 MB memory ceiling, the complete absence of subprocess execution, and the lack of persistent filesystem are each independently disqualifying for a service that loads a 350M-parameter PyTorch model and shells out to `ffmpeg`/`espeak-ng`. Cloudflare Containers is the honest, technically-real alternative, and this report does not dismiss it on principle — but its ephemeral disk model means adopting it is a genuine storage re-architecture, not a redeploy, and the always-on-vs-cold-start tradeoff cuts against exactly the "load a model once, keep it warm" pattern this app depends on. Neither Cloudflare option makes the backend cheaper once that pattern is respected; Workers can't run it at any price, and Containers lands in the same monthly range as Render once kept warm.

The one real, low-risk win available today — moving the four-provider AI story-generation proxy to a Worker — is genuine but small, and is better left until Render's own cost or load actually motivates the extra deployed service, rather than adopted speculatively.

---

## Final Questions, Answered

```
Why is the backend currently on Render?
It runs a resident PyTorch voice-cloning model (Chatterbox, ~350M params) and
shells out to ffmpeg and espeak-ng as real subprocesses, on a plain Docker
image with a persistent disk for SQLite + user audio. Render is the simplest
host that runs an unmodified Dockerfile with a persistent disk and no GPU
requirement -- verified against render.yaml's own stated reasoning, which
checks out against the code.

Can the existing backend run unchanged on Cloudflare Workers?
NO.
Disqualified independently by: a 128 MB hard memory ceiling (not raisable),
zero subprocess execution at any tier, and no persistent filesystem.

Can part of the backend run on Cloudflare?
YES.
The AI story-generation proxy (app/services/ai_providers/) is a clean,
stateless HTTP-only slice with no local compute -- a genuine Workers fit.
PDF extraction (pypdf specifically) is plausible but unverified for its
lxml-dependent counterpart (trafilatura), and is bottlenecked downstream by
narration anyway, so moving it alone brings little benefit.

Can FFmpeg run there in the same way?
NO on Workers (no subprocess execution, full stop).
YES, unchanged, on Cloudflare Containers (a real Linux environment running
the same Docker image).

Can voice cloning run there?
DEPENDS.
NO on Workers. Technically YES on Containers (same Docker image, adequate
instance sizes exist), but requires solving Containers' ephemeral disk for
the model cache and reference audio first. A different answer exists via
Workers AI's third-party voice-cloning models (MiniMax, ElevenLabs) -- but
that replaces Chatterbox with a paid third-party API, not a migration of
the current pipeline.

Can local TTS (espeak-ng) run there?
NO on Workers (subprocess). YES, unchanged, on Containers.

Can AI provider proxy endpoints run there?
YES. This is the one clean, low-risk Workers fit identified in this review.

Can PDF/Book Reader run there?
PARTIALLY. Extraction logic is a plausible Workers candidate (pypdf verified
pure-Python; trafilatura's lxml dependency unverified either way); the
narration step immediately downstream cannot move, which limits the real
benefit of moving extraction alone.

Would Cloudflare be cheaper?
NO, for the backend, once you account for keeping a resident model warm --
Workers can't run it at any price, and Containers lands in the same monthly
range as Render's current ~$8.25/month once kept warm to avoid repeated
cold-start model loads. The frontend is already free on Cloudflare Pages,
and remains so regardless of any backend decision.

Could the app realistically run entirely free?
NO, not the backend, under any Cloudflare product evaluated -- Workers' free
tier is 10ms CPU/request against a workload that needs seconds to minutes.
The frontend already runs free today on Cloudflare Pages. External AI
provider usage (OpenAI/Anthropic paid, Gemini free-tier-eligible) is
unaffected by any hosting choice in either direction.

Best architecture:
Keep the current split (Cloudflare Pages + Render). Optionally add a
Cloudflare Worker for the AI-provider proxy specifically, later, only if
Render's own load or cost becomes a real problem -- not as a precautionary
change made now.

Keep Render:
YES.

Recommended migration:
None right now. If a migration is ever warranted, Phase 1 only: move the
AI-provider proxy to a Worker, measure, and stop there unless Render's cost
specifically motivates going further -- see the phased plan above.
```
