# Security & Voice-Cloning Safety

Two separate concerns share this document because they share the same threat
model: this application accepts audio of a real person's voice and produces
convincing synthetic speech in it.

---

## Part 1 — Application security

### Upload handling

| Control | Where | What it stops |
|---|---|---|
| Chunked read with an early abort | `api/v1/voices.py::_read_upload` | Memory exhaustion — the body is read in 1 MiB chunks and abandoned the moment it passes the limit, rather than buffered whole and then measured |
| Configurable size cap | `MAX_UPLOAD_BYTES`, default 25 MiB | Disk and memory exhaustion |
| **Magic-byte container sniffing** | `ai/audio_processing.py::sniff_container` | A `.wav` extension on arbitrary bytes. The extension and the browser-reported MIME type are both hints; the first 12 bytes decide |
| Real decode via ffmpeg | `_decode_with_ffmpeg` | Malformed or hostile containers — ffmpeg runs as a subprocess with `-nostdin`, an explicit `-map 0:a:0`, `-vn`, and a 120 s timeout, so a crafted file cannot reach a library parser in-process |
| Duration and level bounds | `preprocess_reference` | Absurdly long inputs (rejected before trimming) and silent recordings |
| NaN/Inf scrubbing | `preprocess_reference` | Malformed float streams poisoning the DSP |

Note the deliberate ordering: **sniff → decode → validate**. Validating duration
before decoding would mean trusting a container header an attacker wrote.

### Path traversal

Three independent layers, because this is the highest-severity class of bug in
a service that stores user files:

1. **Non-guessable IDs.** `secrets.choice` over a 36-character alphabet,
   12 characters, prefixed (`voice_`, `gen_`). Non-sequential so generation URLs
   cannot be enumerated.
2. **Strict ID validation before any path is built.** `is_safe_id()` matches
   `^[a-z]+_[a-z0-9]{12}$`. `../`, null bytes, absolute paths and wrong-length
   IDs are all rejected, and the request 404s before touching the filesystem.
3. **Resolved-path containment.** `resolve_within()` resolves the joined path
   and refuses anything that is not inside the storage root — belt and braces if
   a future caller forgets step 2.

Filenames from clients are sanitised (`sanitize_filename`) and used only for
logging and metadata, never to build a path. Stored files are always named from
the server-generated ID.

Covered by `tests/unit/test_security.py` and by API-level tests that fire
`../../etc/passwd` at every ID-bearing route.

### No static file serving

There is no `StaticFiles` mount. Audio is served by
`GET /voices/{id}/sample` and `GET /generations/{id}/audio`, which re-validate
the ID, resolve within the root, and set `X-Content-Type-Options: nosniff`. The
on-disk layout is never exposed, and per-request authorization has an obvious
home once accounts exist.

### CORS

Explicit origins only, from `CORS_ORIGINS`. Never `*` — uploads are personal
voice data and the API is credentialed-capable.

### Rate limiting

Token buckets keyed on the peer address:

| Scope | Default |
|---|---|
| Global, per IP | 240 requests/minute |
| Voice creation | 20/hour |
| Speech generation | 120/hour |

`X-Forwarded-For` is **not** trusted — it is client-controlled unless a known
proxy sets it, and trusting it blindly disables the limiter. Behind a proxy, run
uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>`.

In-process only; see [ARCHITECTURE.md](./ARCHITECTURE.md#in-process-rate-limiting)
for the Redis swap.

### Input limits

- Voice name: 80 characters, control characters stripped, whitespace collapsed
- Text: `MAX_TEXT_CHARS` (default 2000), with a hard schema ceiling of 5000 that
  no configuration mistake can raise
- Generation controls (`exaggeration`, `cfgWeight`, `temperature`, `seed`) are
  range-checked and **rejected** rather than clamped, so a client learns it sent
  something wrong
- Voice count: `MAX_VOICES` (default 100)

### Errors and logging

A uniform envelope, `{"error": {"code", "message", "details"}}`, with stable
machine-readable codes. Unhandled exceptions are logged with a stack trace
server-side and returned as a bare `internal_error` — no tracebacks, no
filesystem paths, no SQL reaches the client.

### Temporary files

Preprocessing uses `tempfile.TemporaryDirectory`, so scratch files are removed
even on an exception. `storage/tmp/` is swept at startup to recover from a crash
mid-request.

### Container hardening

Both images run as a non-root user (uid 10001 / 1001) and carry healthchecks.
The frontend ships as a Next.js standalone bundle containing only the modules
the server actually imports.

### What is deliberately absent

**Authentication.** The MVP is single-tenant and self-hosted: whoever can reach
the API owns every voice on it. Stated plainly rather than papered over with a
shared secret that would imply more safety than it delivers.

> **Do not expose this API to the public internet as-is.** Run it on a private
> network, behind a VPN, or behind an authenticating reverse proxy until Phase 2
> lands accounts.

---

## Part 2 — Voice-cloning safety

Voice cloning enables impersonation: fraud, fabricated evidence, harassment.
These are the safeguards actually implemented, not aspirations.

### Consent is enforced, not requested

Creating a voice **requires** an explicit assertion:

> ☑ I confirm that this is my voice, or I have permission from the speaker to
> clone it.

- The UI disables the submit button until it is checked.
- The API rejects `consent=false` with **403 `consent_required`**, independently
  of the UI. A scripted client cannot skip it.
- The exact statement text is persisted on the voice row (`consent_statement`,
  `consent_at`) — the record shows what was agreed to, not just that a box was
  ticked.
- `REQUIRE_CONSENT=false` exists for automated testing. Do not set it in
  production.

A checkbox does not verify anything, and pretending otherwise would be dishonest.
Its value is that it makes the obligation explicit and creates a record. Stronger
verification — a spoken challenge phrase matched against the reference — is on
the roadmap.

### Deletion is complete

Deleting a voice removes, in one transaction plus its filesystem cascade:

- the voice row
- the reference audio
- the speaker conditioning cache (`conds.pt`)
- `metadata.json`
- **every generation made with that voice, rows and audio files both**

The audit trail survives, because "this voice existed and was deleted" is
exactly the fact an investigation needs. This is verified by
`test_deleting_a_voice_cascades_to_its_generations` and by the e2e suite.

### Provenance: watermarking

Every Chatterbox generation carries a **Resemble PerTh** neural watermark —
inaudible, and designed to survive MP3 compression and common editing. This is
not taken on trust: `tests/ai/test_chatterbox_engine.py::test_watermark_is_detectable`
generates audio and asserts the watermark reads back.

The watermark status is surfaced honestly rather than assumed:
`GET /system/info` reports `engine.watermarked`, every generation row records
`watermarked`, and the UI shows a "Watermarked" or "No watermark" badge. The
mock engine reports `false`, because it does not watermark.

Verify any file:

```python
import librosa, perth

audio, sr = librosa.load("generation.wav", sr=None)
print(perth.PerthImplicitWatermarker().get_watermark(audio, sample_rate=sr))
# 1.0 = watermarked, 0.0 = not
```

### Audit trail

Append-only `audit_events`, recording `voice.created`, `speech.generated`,
`voice.deleted` and `speech.deleted` with a timestamp, the subject ID and a
structured detail blob (language, duration, character count, RTF, consent).

The actor is stored as a **salted SHA-256 prefix of the client address**, not in
the clear: the trail needs to link events from the same origin, not to identify
a person. Audit rows carry no foreign key and are never cascaded, so they
outlive the voices they describe.

### Experimental output is labelled

The Armenian bridge produces an approximation, and says so at every step — in
the API (`native: false`, `experimental: true`, a `notice` on the response), in
the UI (a warning before generating and a banner on the result), and on the
stored row. Users should know when they are hearing an approximation.

### Not built, on purpose

This project does not, and will not, include:

- real-time voice conversion tuned for live impersonation
- bulk or batch cloning of many voices from scraped audio
- watermark removal or evasion
- any feature whose primary use is passing synthetic speech off as a real
  recording of a specific person

### Roadmap

| Safeguard | Status |
|---|---|
| Consent assertion, enforced server-side | Shipped |
| Complete deletion incl. generations | Shipped |
| Neural watermarking + verification test | Shipped |
| Audit trail with hashed actor | Shipped |
| Rate limiting | Shipped |
| Experimental-output labelling | Shipped |
| Spoken challenge-phrase verification | Phase 2 |
| Per-user accounts and ownership | Phase 2 |
| In-app abuse reporting | Phase 2 |
| Provenance metadata embedded in the WAV (C2PA-style) | Phase 3 |

### Reporting abuse or a vulnerability

Open a private security advisory on the repository. Do not open a public issue
for a vulnerability. For misuse of a deployment, contact whoever operates it —
this is self-hosted software, so there is no central operator.
