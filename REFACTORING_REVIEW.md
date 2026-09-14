# Senior Review — Architecture, Dead Code, Performance, and Kid-Friendly UI/UX

A review of Voice Story Studio as it stood at commit `b8b8ef6`, and a record of
what changed as a result.

The brief was explicit that not everything should be rewritten: *"Do not blindly
refactor everything. Every change must solve a real problem."* This document is
therefore as much about what was **left alone**, and why, as about what moved.
Seven things changed. Everything else was examined and deliberately kept.

---

## Contents

1. [Architecture map](#1-architecture-map)
2. [Dead code](#2-dead-code)
3. [Dependencies](#3-dependencies)
4. [Duplication](#4-duplication)
5. [Performance](#5-performance)
6. [Error handling](#6-error-handling)
7. [AI integration](#7-ai-integration)
8. [Frontend and UI/UX](#8-frontend-and-uiux)
9. [Accessibility](#9-accessibility)
10. [Overengineering and underengineering](#10-overengineering-and-underengineering)
11. [Before / after](#11-before--after)
12. [Verification](#12-verification)
13. [Senior grading](#13-senior-grading)
14. [Remaining technical debt](#14-remaining-technical-debt)

---

## 1. Architecture map

```
                         BROWSER (Cloudflare Pages, static export)
                                        │
                    src/services/*  ── the only code that knows HTTP exists
                                        │  fetch → NEXT_PUBLIC_API_URL
                                        ▼
                         FASTAPI (Render, Docker web service)
                                        │
   app/api/v1/*  ─── request/response shape only; no business rules
        │  Depends()
        ▼
   app/services/*  ─── all business rules live here
        │
        ├── voice_service ──┐
        ├── speech_service ─┼──► ai/registry ──► VoiceCloningEngine
        │                   │                      ├── chatterbox_engine (real)
        │                   │                      ├── espeak_engine (defaults)
        │                   │                      └── mock_engine (tests/CI)
        │                   └──► ai/audio_mix (ffmpeg: ambience, speed)
        │
        ├── story_service ──► ai_providers/registry ──► AiTextProvider
        │                          openai · gemini · anthropic · ollama
        │
        └── documents/
              DocumentService ──► PdfDocumentExtractor  (pypdf)
                    │             WebDocumentExtractor  (trafilatura)
                    │             security.fetch_url_safely  (SSRF gate)
                    ▼
              Document / DocumentSection ──► ReadingService ──► speech_service
        │
        ▼
   app/repositories/*  ─── the only code that knows SQLAlchemy exists
        │
        ▼
   SQLite on Render's persistent disk (/app/storage)
```

**The layering holds.** Spot-checking every router confirmed no API module
imports a repository or a model directly, and no service imports FastAPI. `ai/`
genuinely has no web dependency — it can be lifted into a standalone GPU worker
without dragging FastAPI along, which is what its separation was for.

**Three boundaries are doing real work, not ceremony:**

| Boundary | What it buys | Evidence it earns its keep |
|---|---|---|
| `VoiceCloningEngine` ABC | CI runs the whole API suite with no torch and no weights | `requirements-ci.txt` installs no torch; 274 tests pass in ~30 s |
| `AiTextProvider` ABC | Four vendors behind one call, and `"auto"` degrades in priority order | Story generation works with zero, one, or four keys configured |
| `DocumentExtractor` ABC | PDF and HTML converge on one `Document` before any TTS logic runs | `ReadingService` has no idea which extractor produced its sections |

**One boundary was questioned and kept.** The repository layer over SQLAlchemy
looks like indirection over an ORM that is already an indirection. It stays
because `document_repo` and `generation_repo` own cascade-delete ordering and
storage-file cleanup that would otherwise be copy-pasted into every router that
deletes something — a correctness concern, not a purity one.

---

## 2. Dead code

The brief warned against the obvious trap: *"Do not delete something merely
because static analysis says it is unused."* Static analysis was the starting
point, never the verdict. Every candidate was grepped across app code, tests,
docs, workflow YAML and deploy config before being classified.

`vulture --min-confidence 60` reported **41 candidates**. Three were real.

### SAFE TO REMOVE — removed

| Item | Why it was dead | Why it mattered |
|---|---|---|
| `Settings.generation_timeout_seconds` + `GENERATION_TIMEOUT_SECONDS` in `.env.example` | Declared, documented, read by nothing | **Actively misleading.** It told an operator that generation is capped at 300 s. Nothing enforces a cap. Removing the knob is honest; see [§14](#14-remaining-technical-debt) for the real gap it was papering over. |
| `FieldError` (`utils/validation.ts`) | No validator returns it, no caller consumes it | Described a validation shape the codebase does not use — every validator returns `string \| null` |
| `formatDateTime` (`utils/format.ts`) | Superseded by `formatRelative`, which is what the UI calls | Untested, undocumented, unreferenced |

### KEEP — flagged, but correct as-is

| Item | Flagged by | Why it stays |
|---|---|---|
| `armenian_ipa` (`ai/armenian.py`) | vulture | A deliberate G2P diagnostic. Its own docstring and `docs/ARMENIAN.md` both explain why nothing calls it: Chatterbox consumes graphemes, and this is what a fine-tuning pipeline would use. Deleting it would delete the documented Armenian roadmap's starting point. |
| 24 route handlers (`api/v1/*`) | vulture | Registered by `@router.*` decorator; every one is exercised by an API test |
| Pydantic fields, SQLAlchemy columns, `cls` in validators | vulture | Metaclass-consumed. Pure false positives. |
| `eslint-config-next` | depcheck | Reached via `compat.extends('next/core-web-vitals')`, which depcheck cannot statically see |
| 10 CSS classes (`tile--grape`, `background-*`, …) | grep | Composed at runtime from template strings (`` `tile ${tile.hue}` ``). The exact false-positive class the brief warns about. |
| `getVoice`, `listBookSections` (`services/`) | ts-prune | Three-line, correct bindings for live, tested backend endpoints. The service layer is a deliberate 1:1 mirror of the API surface; churning it to chase a coverage number is not a real problem being solved. |

### NEEDS VERIFICATION — resolved during review

`ai/audio_mix.available_backgrounds`, `espeak_engine.default_voice_by_id`, and
`default_voices_for_language` were flagged as unused by app code. They are all
covered by unit tests and are the public surface those modules are tested
through. Kept.

---

## 3. Dependencies

`depcheck` on the frontend: **zero unused runtime dependencies**, one
false-positive dev dependency (above). `pip` side: every entry in
`requirements.txt` traces to an import.

The one dependency finding worth recording is the **inverse** problem, fixed
earlier in this work: `requirements-ci.txt` was *missing* five packages that
`app.main` imports unconditionally at module load (`anthropic`, `openai`,
`google-genai`, `pypdf`, `trafilatura`, later `fpdf2`). CI installs only that
file, so a clean CI venv could not import the app. The lesson is recorded here
because it recurs: **a "CI-equivalent" check must install `requirements-ci.txt`
and nothing else.** Installing it alongside `requirements-dev.txt` (which pulls
the full `requirements.txt`) masks exactly the gap it is meant to catch, and did
so once during this work.

No dependency was added by this review. `Dropzone` is 100 lines of plain React
rather than a drag-and-drop library, because the requirement is "accept one
file", not "reorderable multi-zone".

---

## 4. Duplication

One genuine duplication, one deliberate near-duplication left alone.

**Fixed — the file picker.** `AudioDropzone` had a real drop target with
keyboard support, drag-over feedback and a hidden input. The Book Reader's PDF
picker — the newest feature — was a bare `<input type="file" class="input">`. So
the app had two different answers to "give me one file", the newer one worse,
and dropping a PDF onto the page did nothing.

The interaction moved into `components/Dropzone.tsx`. Validation and previews
stayed with each caller, because that is the part that genuinely differs: audio
needs duration probing and an inline player, PDFs need neither.

**Not fixed — the two narration forms.** `GenerateForm` and the Book Reader's
narration step both collect a voice, a background and a volume. That is already
factored into `VoiceAndBackgroundFields`; what remains duplicated is the
`useState` block and the `try/catch/finally` around the call. Merging those
would need a hook parameterised over two different request shapes, two different
validation rules and two different success messages — more indirection than the
~15 lines it saves. Left alone under §49.

---

## 5. Performance

The brief said *"do not optimize blindly"*, so each candidate was measured
before being accepted or rejected.

| Candidate | Measurement | Verdict |
|---|---|---|
| Cache AI SDK clients instead of constructing per request | Construction: **50.01 / 49.25 / 54.19 ms**. The LLM call it precedes: **2–10 s**. Saving is **under 2%** of the request. | **Rejected.** Global mutable state and test-ordering fragility for ~1%. The measurement is the reason, not a hunch. |
| Chunked TTS for long books | Already implemented in `text_chunking` + `ReadingService` | Correct as-is |
| Duration read-back after `apply_speed` | `apply_speed` rewrites the file, so the pre-speed duration was wrong | Fixed earlier: duration now comes from `sf.info()` on the final file |
| Conditioning cache for cloned voices | Already implemented (`hasConditioningCache`) | Correct as-is |

### The one that mattered: 74s of dead time before the server answered anything

Verifying the deployed app (§12) sent me looking at startup, and measurement
found the real performance bug — not in a request path, but before any request
could be served at all.

`lifespan` called `get_engine(...)`. That does not load model weights
(`PRELOAD_MODEL=false` on Render), but `ChatterboxEngine.__init__` calls
`resolve_device()`, which does `import torch`. Uvicorn accepts no connection
until lifespan returns, so the whole server was held hostage to that import.

Measured, same machine, identical cold page cache — the state a freshly
deployed container is always in:

| | Cold boot → first healthy `/health` |
|---|---|
| Before | **74.1 s** |
| After | **4.7 s** |

(Warm-cache boot was always ~3 s, which is why this never showed up in local
development or in CI. Only a cold container pays it — and a cold container is
exactly what a deploy health check probes.)

The fix is three lines and removes an inconsistency rather than adding a
mechanism: `api/deps.py` already builds the same singleton on first request,
and `/health` already reported `engineLoaded: false` until weights load. Two
comments in this repo already promised this behaviour and were silently wrong —
`ai/registry.py`'s "process start-up stays fast", and `render.yaml`'s note that
loading at boot "would push Render's deploy health check past its timeout".
Now both are true.

`/health` also moved from reading `app.state.engine` to asking the registry, so
it stays accurate when a request, not startup, created the engine. Two
regression tests lock both halves in.

The honest summary: **the codebase had no problem in any request path** — the
one real performance defect was in the boot path, it was invisible to every
warm-cache measurement, and only verifying production actually surfaced it.

---

## 6. Error handling

The brief's rule — *"do not use retries to hide architectural problems"* — is
already respected: there is no retry loop anywhere in the request path. Failures
surface.

What was checked and found sound:

- `ProviderError` carries a `user_message` that is safe to render, separate from
  the internal detail that goes to logs. A provider outage never leaks a key,
  an endpoint or a stack frame to the browser.
- `fetch_url_safely` raises distinct, typed errors per failure mode (blocked
  host, redirect to a blocked host, too large, timeout) rather than one generic
  fetch error.
- `ScannedDocumentError` exists specifically so a scanned PDF cannot silently
  become an empty narration — the brief's "never silently return empty".
- The frontend's `ApiError` preserves the backend's `error.code` and `message`,
  and every form renders it in a `Callout` rather than a toast that scrolls away.

No change made. This was the strongest area of the codebase before the review.

---

## 7. AI integration

`AiProviderRegistry.resolve()` has one property worth calling out because it is
easy to get wrong and this code gets it right: **an explicitly requested
provider is never silently substituted.** Ask for `anthropic` with no Anthropic
key and you get an error naming the missing configuration; only `"auto"` walks
the priority list (openai → gemini → anthropic → ollama). A user who picks a
model gets that model or a clear refusal, never a quiet downgrade.

Also verified: no provider key is ever serialised into a response.
`GET /api/v1/ai/providers` returns a boolean `available` per provider and
nothing else. Confirmed by reading the schema, not by calling the endpoint with
a live key.

One UI change followed from this (see §8): the provider picker moved behind
"Advanced settings" with the plain-language name "Story Helper" and a
"Pick for me (recommended)" default. The capability is unchanged; it is simply
no longer the second decision a seven-year-old has to make.

---

## 8. Frontend and UI/UX

### The bug the redesign found

`AppShell`'s nav did not link to the Book Reader at all. The feature was
reachable only from the home page, so from any other screen it was invisible.
That is a navigation defect, not a styling preference, and it was the single
highest-value change in this section.

### What was wrong with the front door

The home page opened onto a **status dashboard**: model name, device, sample
rate, watermark flag, licence string. Six pieces of engineering telemetry, and
below them the things you could actually do. For the stated audience — children,
with adults nearby — the first screen answered a question nobody asked.

The redesign inverts it: four coloured tiles naming the four things you can do,
each with an icon, a one-line description in plain language, and its own hue so
the app reads as *pick an adventure* rather than *choose a menu item*. Engine
detail moved into a collapsed `Studio status` disclosure at the bottom. Nothing
was deleted; it was reordered to match who is looking.

### Copy

Labels were written by the person who built the app, for themselves:

| Before | After |
|---|---|
| AI Provider | Story Helper *(behind Advanced settings)* |
| Characters | Who is in your story? |
| Story Idea | What happens? |
| Age Group | Who is it for? |
| Length | How long? |
| Tone | What kind of story? |
| Generate Story | ✨ Create My Story |
| Mystical / Calm / Forest | 🔮 Magical / 🌊 Calm / 🌳 Forest |
| None *(background)* | 🔇 Just the voice |

Background sounds gained icons because a row of adjectives tells a child nothing
about what they will hear.

### Technical noise (§45)

Three places showed engineering data to a child. All three now hide it one click
away rather than deleting it, because it is genuinely useful when tuning the
engine:

- Home page → `Studio status` disclosure
- Result screen → `Technical details` disclosure (render time, RTF, file size,
  engine, sample rate). The card hint became "4.2s of audio — press play."
- Story form → `Advanced settings` disclosure

### Design system

`globals.css` gained a token layer rather than per-component colours: a
`--joy-*` hue set (grape / sky / sun / mint / coral, each with a `-soft`
variant), one hue per feature so a colour consistently means a place in the app.
`--radius-lg: 22px` and `--radius-pill` soften the geometry; base type went to
16px/1.6 for readability; the font stack now includes `Noto Sans Armenian` so
Հայերեն renders in the same family rather than falling back mid-sentence.

**Kid-friendly is not visually noisy (§21).** There is one static aurora
gradient on `body::before` and one scale transform on drag-over. No animated
backgrounds, no bouncing, no autoplay, no sound effects. Contrast is unchanged
from the previous palette, which met AA.

---

## 9. Accessibility

| Concern | Status |
|---|---|
| Tap targets | `--tap: 44px` token, applied to buttons, nav links and segmented options (WCAG 2.5.5) |
| Reduced motion | Global `prefers-reduced-motion: reduce` block; the drag-over transform opts out explicitly |
| Colour scheme | `prefers-color-scheme` honoured; every token has a dark value |
| Keyboard | `Dropzone` is `role="button"` + `tabIndex` + Enter/Space, so the drop target is not mouse-only |
| Decorative icons | Every emoji is `aria-hidden="true"` with a real text label beside it — a screen reader hears "Read a Book", not "open book Read a Book" |
| Icon-only controls | `AudioPlayer`'s play/pause carries `aria-label`; the scrubber has `aria-label="Seek"` |
| Disabled state | `Dropzone` uses `aria-disabled` and drops out of the tab order rather than just dimming |
| Mobile | Verified at 390 px by an e2e test asserting zero horizontal overflow, on every run |

---

## 10. Overengineering and underengineering

### Overengineered — and left that way, deliberately

`fetch_url_safely` is ~120 lines to make one HTTP request: scheme allowlist,
`getaddrinfo` + `ipaddress` validation of every resolved address, a manual
redirect loop that re-validates each hop, separate connect and read timeouts, a
streamed byte cap, and an injectable transport for tests. For a "fetch a URL"
helper that is enormous.

It is correct. This is the one place in the app where a user-supplied string
becomes a server-side network request, and every one of those layers closes a
real SSRF path. Simplifying it would be the most expensive kind of cleanup.

### Underengineered

- **No generation timeout.** Removing the dead `GENERATION_TIMEOUT_SECONDS`
  setting made this visible rather than creating it: a wedged TTS call is bounded
  only by Render's proxy timeout. Adding one is a behaviour change beyond this
  review's brief; it is logged in §14 with the place to put it.
- **In-process rate limiting.** A token bucket in memory is per-instance, so
  scaling Render past one instance silently multiplies every limit. Correct for
  today's single instance; the config comment already says "swap for Redis at
  scale".
- **SQLite on a single persistent disk.** Same shape of constraint: right for
  now, a ceiling later. Both are documented in the README's Known limitations,
  which is the honest handling.

### Neither

The `ai/` split, the extractor ABC, and the provider registry all looked like
candidates for "is this too much structure for a hobby-scale app?" and all three
survived on evidence: each one is what makes a specific, real thing possible
(CI without torch; PDF and HTML sharing one reading pipeline; four vendors with
zero-to-four keys configured).

---

## 11. Before / after

### The file picker

```tsx
// Before — book-reader/SourceForm.tsx: no drop target, no keyboard affordance,
// nothing in common with the audio picker three screens away.
<Field label="Choose your book" hint="Pick a PDF from this device.">
  {(props) => (
    <input {...props} type="file" className="input" accept="application/pdf,.pdf"
      onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
  )}
</Field>
```

```tsx
// After — the same component both screens use, plus a chosen-file state.
<Dropzone
  accept="application/pdf,.pdf"
  icon="📄"
  title="Drop your book here, or click to choose one"
  hint="A PDF from this device."
  inputLabel="PDF file"
  onFile={setFile}
  disabled={loading}
/>
```

### The front door

```tsx
// Before — the first thing on the page.
<div className="stat-grid" data-testid="system-status">
  <div><div className="stat__label">Model</div>…</div>
  <div><div className="stat__label">Device</div>…</div>
  <div><div className="stat__label">Watermark</div>…</div>
  <div><div className="stat__label">Licence</div>…</div>
</div>
```

```tsx
// After — the four things you can do, in their own colours; the grid above
// still exists, inside <details><summary>Studio status</summary>.
{MODE_TILES.map((tile) => (
  <Link key={tile.href} href={tile.href} className={`tile tile--primary ${tile.hue}`}>
    <span className="tile__icon" aria-hidden="true">{tile.icon}</span>
    <span className="tile__title">{tile.title}</span>
    <span className="tile__desc">{tile.description}</span>
    <span className="tile__cta" aria-hidden="true">{tile.cta}</span>
  </Link>
))}
```

### A configuration knob that lied

```diff
- MAX_VOICES=100
- GENERATION_TIMEOUT_SECONDS=300      # read by nothing; enforced nowhere
- REQUIRE_CONSENT=true
+ MAX_VOICES=100
+ REQUIRE_CONSENT=true
```

---

## 12. Verification

Every check below was run, not assumed.

| Check | Result |
|---|---|
| `ruff check .` | PASS — all checks passed |
| `ruff format --check .` | PASS — 111 files already formatted |
| Backend `pytest` | PASS — 274 passed, 7 deselected |
| Frontend `tsc --noEmit` | PASS |
| Frontend `eslint src e2e` | PASS |
| Frontend `vitest run` | PASS — 71 passed |
| Playwright e2e | PASS — 16 passed (chromium + mobile-chrome) |

**Production, at the time of writing, is half down — and not because of this
work.** The Cloudflare Pages frontend is live and serving this app's build
(`ai-voice-studio-660.pages.dev`, HTTP 200, verified). The Render backend is
not: DNS resolves, TCP connects in 5 ms and TLS completes in 26 ms, and then
`https://voice-clone.onrender.com/health` returns **zero bytes for 240 s**. A
healthy network path followed by silence means Render's router is waiting on an
origin that never answers. None of the changes in this review are deployed —
they sit on a branch, and the deploy workflow runs on `master` only — so this is
the pre-existing state of production, not a regression introduced here.
**Then measuring the boot path found a cause.** Uvicorn accepts no connection
until `lifespan` returns, and `lifespan` was importing torch — 74 s on a cold
page cache, which is the only kind a freshly deployed container has. "TLS
completes, then silence" is precisely what a router shows while waiting on a
server that has not finished starting, and `Dockerfile.render`'s container
health check allowed a 90 s start period, so a boot that overran it would be
killed and restarted — never finishing. That is a coherent explanation for a
permanently silent origin, and §5 documents the fix that takes boot to 4.7 s.

It is an explanation, not a confirmed diagnosis: proving it is what happened to
this particular instance needs Render's own deploy and runtime logs, which
neither this sandbox nor CI can reach. The fix is worth shipping either way —
the 74 s boot was real, measured, and wrong on its own terms.

Six e2e assertions were updated, all of them for deliberate renames from the
redesign ("Book Reader" → "Read a Book", "Create Voice" → "Make My Own Voice",
"History" → "My Recordings", and `system-status` now needing its disclosure
opened). One new test was added for behaviour that did not exist before: a PDF
dropped onto the dropzone is accepted, not only one picked through the dialog.

---

## 13. Senior grading

| Dimension | Grade | Note |
|---|---|---|
| Architecture | **GOOD** | Layering holds under inspection; every abstraction pays for itself with a concrete capability |
| Code quality | **GOOD** | Consistent idiom, comments explain *why*; ruff and eslint clean |
| Dead code | **GOOD** | Three real removals out of 41 static-analysis candidates — the ratio is the point |
| Dependency hygiene | **GOOD** | Zero unused runtime deps; the CI-manifest gap that caused three separate red builds is closed |
| Performance | **GOOD** | The one optimisation on the table was measured and correctly declined |
| Error handling | **GOOD** | Typed errors, safe user messages, no retry-as-bandaid, no silent empties |
| AI integration | **GOOD** | Explicit provider never silently substituted; no key reaches a response |
| Security | **GOOD** | SSRF defence is thorough and its residual DNS-rebinding window is documented rather than hidden |
| Frontend UX | **GOOD** | Was **NEEDS WORK** — a status dashboard as the front door and a feature missing from the nav |
| Accessibility | **GOOD** | 44px targets, reduced motion, labelled icon controls, keyboard-reachable dropzone |
| Testing | **GOOD** | 361 tests across four layers; e2e covers desktop and mobile; remote HTTP is mocked, never live |

No dimension grades below GOOD after this pass. The two that were weakest going
in — frontend UX and dependency hygiene — were the two that got real work.

---

## 14. Remaining technical debt

Ordered by what would bite first.

1. **Cold-start cost is still ~5 s, and unmeasured in CI.** Boot no longer
   imports torch, but nothing stops the next module-level import from
   regressing it. The two new tests in `tests/api/test_system_api.py` assert
   the engine is not constructed at boot, which is the half that mattered; a
   guard on total import time would be the next step if this recurs.
2. **No generation timeout.** A wedged synthesis call is bounded only by
   Render's proxy. The place to add one is `speech_service._generate`, around
   the engine call, surfaced as a `503` with a retry hint. Deliberately not
   done here: it changes runtime behaviour, which is outside a review's remit.
3. **Rate limiting is per-instance.** Scaling Render beyond one instance
   multiplies every limit by the instance count. Needs Redis before that
   happens; the config already says so.
4. **SQLite on one persistent disk.** Ties the backend to a single instance for
   the same reason. Documented in the README's Known limitations.
5. **DNS rebinding.** `fetch_url_safely` validates every resolved address but
   cannot close the window between resolution and connection. Documented in the
   security section rather than silently accepted; closing it needs a pinned
   resolver.
6. **The two narration forms** still share a state-and-try/catch shape. Worth
   revisiting only if a third narration surface appears — two is not yet a
   pattern.
