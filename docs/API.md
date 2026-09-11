# API Reference

Base URL: `http://localhost:8000`  ·  Prefix: `/api/v1`
Interactive docs: `/docs` (Swagger UI) · `/redoc` · `/openapi.json`

All request and response bodies use **camelCase**. Timestamps are RFC 3339 UTC
with a `Z` suffix.

---

## Errors

Every failure uses one envelope:

```json
{
  "error": {
    "code": "consent_required",
    "message": "You must confirm that this is your voice, or that you have the speaker's permission, before a voice profile can be created.",
    "details": { "statement": "I confirm that this is my own voice, ..." }
  }
}
```

Branch on `code`, not on the HTTP status or the message text.

| Code | Status | Meaning |
|---|---|---|
| `validation_error` | 422 | Request body failed schema validation; `details.fields` lists the offenders |
| `invalid_audio` | 422 | Not decodable, too short, too long, or silent |
| `unsupported_language` | 422 | Language code not offered by the loaded engine |
| `consent_required` | 403 | `consent` was not `true` |
| `voice_not_found` | 404 | Unknown or malformed voice ID |
| `generation_not_found` | 404 | Unknown or malformed generation ID |
| `quota_exceeded` | 409 | `MAX_VOICES` reached |
| `payload_too_large` | 413 | Upload over `MAX_UPLOAD_BYTES` |
| `rate_limited` | 429 | Bucket empty; see the `Retry-After` header |
| `synthesis_failed` | 500 | The model ran and failed |
| `engine_unavailable` | 503 | The model could not be loaded or crashed |
| `internal_error` | 500 | Unexpected; details are logged, not returned |

---

## Voices

### `POST /api/v1/voices` — create a voice profile

`multipart/form-data`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | ≤ 80 chars after sanitisation |
| `language` | string | no | Default `en` |
| `consent` | boolean | **yes** | Must be `true` |
| `source` | string | no | `record` or `upload` |
| `audio` | file | yes | WAV, MP3, M4A/MP4, WebM, OGG/Opus, FLAC, AAC |

```bash
curl -X POST http://localhost:8000/api/v1/voices \
  -F "name=My Voice" \
  -F "language=en" \
  -F "consent=true" \
  -F "source=record" \
  -F "audio=@reference.wav"
```

**201**

```json
{
  "id": "voice_k3f9a1b2c4d5",
  "name": "My Voice",
  "language": "en",
  "createdAt": "2026-09-11T12:00:00Z",
  "engine": "chatterbox",
  "engineVariant": "multilingual",
  "referenceDurationSeconds": 14.2,
  "referenceSampleRate": 24000,
  "source": "record",
  "generationCount": 0,
  "lastUsedAt": null,
  "consentGiven": true,
  "hasConditioningCache": true,
  "sampleUrl": "/api/v1/voices/voice_k3f9a1b2c4d5/sample"
}
```

Errors: `403 consent_required` · `413 payload_too_large` · `422 invalid_audio` ·
`409 quota_exceeded` · `429 rate_limited`

### `GET /api/v1/voices` — list

Query: `limit` (1–200, default 50), `offset` (default 0). Newest first.

```json
{ "items": [ /* Voice */ ], "meta": { "total": 3, "limit": 50, "offset": 0 } }
```

### `GET /api/v1/voices/{voiceId}` — one voice

### `GET /api/v1/voices/{voiceId}/sample` — reference audio

Returns `audio/wav`. Served through the API, never as a static file.

### `DELETE /api/v1/voices/{voiceId}` — delete

Removes the voice, its reference audio, its conditioning cache **and every
generation made with it**.

```json
{ "id": "voice_k3f9a1b2c4d5", "deleted": true }
```

---

## Speech

### `POST /api/v1/speech` — generate

```json
{
  "voiceId": "voice_k3f9a1b2c4d5",
  "text": "Hello from my cloned voice.",
  "language": "en",
  "exaggeration": 0.5,
  "cfgWeight": 0.5,
  "temperature": 0.8,
  "seed": 1234
}
```

| Field | Range | Default |
|---|---|---|
| `text` | 1 … `MAX_TEXT_CHARS` (hard ceiling 5000) | — |
| `exaggeration` | 0.0 – 2.0 | 0.5 |
| `cfgWeight` | 0.0 – 1.0 | 0.5 |
| `temperature` | 0.05 – 2.0 | 0.8 |
| `seed` | 0 – 2³¹−1 | random |

Out-of-range values are **rejected**, not clamped.

**201**

```json
{
  "id": "gen_m4n5p6q7r8s9",
  "voiceId": "voice_k3f9a1b2c4d5",
  "text": "Hello from my cloned voice.",
  "language": "en",
  "createdAt": "2026-09-11T12:05:00Z",
  "audioUrl": "/api/v1/generations/gen_m4n5p6q7r8s9/audio",
  "durationSeconds": 2.4,
  "sampleRate": 24000,
  "sizeBytes": 115244,
  "generationSeconds": 0.71,
  "realTimeFactor": 0.296,
  "engine": "chatterbox:multilingual",
  "watermarked": true,
  "experimental": false,
  "notice": null
}
```

Synchronous: the response arrives once the WAV exists. See
[ARCHITECTURE.md](./ARCHITECTURE.md#synchronous-generation-no-queue) for when
that should become a job queue.

**Experimental Armenian.** With `"language": "hy"`, the response carries
`experimental: true` and a `notice` explaining the transliteration. `text`
echoes the original Armenian.

---

## Generations

### `GET /api/v1/generations` — list

Query: `voiceId` (optional filter), `limit`, `offset`.

### `GET /api/v1/generations/{id}` — one generation

### `GET /api/v1/generations/{id}/audio` — stream or download

| Query | Effect |
|---|---|
| *(none)* | `Content-Disposition: inline` — for `<audio>` |
| `?download=true` | `Content-Disposition: attachment` |

Supports HTTP byte ranges (`206 Partial Content`, `416` past the end), so media
elements can seek and `AVPlayer`/`ExoPlayer` behave.

```bash
curl -H "Range: bytes=0-1023" \
  http://localhost:8000/api/v1/generations/gen_m4n5p6q7r8s9/audio -i
```

### `DELETE /api/v1/generations/{id}` — delete

---

## System

### `GET /api/v1/system/info` — capabilities

The frontend hardcodes no language list, size limit or character limit; it reads
them from here. Mobile clients should do the same, so a new engine or a new
language needs no client release.

```json
{
  "appName": "AI Voice Studio",
  "version": "0.1.0",
  "environment": "production",
  "engine": {
    "name": "chatterbox",
    "variant": "multilingual",
    "device": "cuda",
    "sampleRate": 24000,
    "loaded": true,
    "supportsStreaming": false,
    "supportsCachedConditioning": true,
    "watermarked": true,
    "license": "MIT (code and weights)",
    "notes": "Chatterbox multilingual (0.5B), 24 kHz output, PerTh watermark applied to every generation."
  },
  "deviceDetails": {
    "device": "cuda",
    "torch_version": "2.6.0",
    "gpu_name": "NVIDIA GeForce RTX 4090",
    "vram_total_mb": 24564,
    "vram_allocated_mb": 2104,
    "cuda_version": "12.4",
    "ffmpeg": true
  },
  "languages": [
    { "code": "en", "name": "English", "native": true, "experimental": false, "note": null },
    { "code": "hy", "name": "Armenian (experimental)", "native": false, "experimental": true,
      "note": "Armenian is not natively supported by this model. ..." }
  ],
  "limits": {
    "maxUploadBytes": 26214400,
    "minReferenceSeconds": 3.0,
    "maxReferenceSeconds": 120.0,
    "maxTextChars": 2000,
    "maxVoices": 100,
    "requireConsent": true
  },
  "acceptedAudioFormats": ["aac", "flac", "m4a", "mp3", "mp4", "ogg", "opus", "wav", "webm"]
}
```

### `GET /health` — liveness

```json
{ "status": "ok", "engineLoaded": true, "version": "0.1.0" }
```

---

## Rate limits

| Scope | Default |
|---|---|
| All `/api/v1` requests | 240/minute per client |
| `POST /voices` | 20/hour |
| `POST /speech` | 120/hour |

A `429` carries `Retry-After` in seconds.

---

## Notes for future mobile clients

- camelCase decodes directly into Kotlin `data class` and Swift `Codable`.
- Upload whatever the platform recorder produces (`.m4a`, `.caf`, `.3gp`) — the
  server sniffs the container and decodes with ffmpeg. No client-side transcode.
- `audioUrl` is relative; resolve it against your API base. It is range-capable,
  so hand it straight to `ExoPlayer` or `AVPlayer`.
- Read limits and languages from `/system/info` at launch rather than shipping
  a hardcoded copy.
- `/api/v1` is versioned; a future `/api/v2` will not break shipped apps.
