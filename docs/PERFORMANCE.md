# Performance & Hardware

## Measure, do not guess

Every number a vendor publishes was measured on hardware you do not have. The
repository ships a benchmark that measures the four things that actually decide
your deployment:

```bash
python scripts/benchmark.py --engine chatterbox --variant multilingual --json bench.json
```

It reports:

| Metric | Why it matters |
|---|---|
| Model load time | How long a cold container takes to serve its first request |
| Voice conditioning time | Latency of "Create voice" |
| Generation latency | Latency of "Generate speech" |
| **Real-Time Factor (RTF)** | Whether synchronous generation is viable at all |
| Peak VRAM | Which GPU you need |

## Real-Time Factor

```
RTF = generation wall time ÷ duration of generated audio
```

```
3 s of compute ÷ 10 s of audio  =  RTF 0.3     ← 3× faster than real time
30 s of compute ÷ 10 s of audio =  RTF 3.0     ← 3× slower than real time
```

RTF < 1.0 means faster than real time. It is the number that decides
synchronous versus queued generation:

| RTF | 2000-char request (~2.5 min of speech) | Verdict |
|---|---|---|
| 0.1 | ~15 s | Synchronous, comfortably |
| 0.3 | ~45 s | Synchronous, but watch proxy timeouts |
| 1.0 | ~2.5 min | Borderline — cap the text length |
| 3.0 | ~7.5 min | Queue required |

`scripts/benchmark.py` prints this verdict for you.

## What the vendors report

**Verified as claims, not as measurements on my hardware:**

- Chatterbox-Nano (110M): "3× faster than realtime on 8 CPU cores" — Resemble AI
- F5-TTS Base + Vocos: ~0.04 RTF on an L20 GPU at 16 NFE steps — the F5-TTS repo
- CosyVoice 2: 150 ms first-packet latency in streaming mode — CosyVoice repo

Do not put these in a capacity plan without reproducing them.

## Rough expectations by hardware

**Engineering recommendation**, derived from model size and the vendor figures
above — not measured here. Treat as a starting point for your own benchmark run.

| Hardware | Variant | Expected RTF | Notes |
|---|---|---|---|
| RTX 4090 / A10G / L4 | Multilingual 0.5B | well under 1.0 | The comfortable target |
| RTX 3060 12 GB | Multilingual 0.5B | under 1.0 | Fine for personal use |
| Apple M-series (MPS) | Multilingual 0.5B | around 1.0 | Good for development |
| 8-core CPU | **Nano 110M** | ~0.33 (vendor) | The CPU-viable path |
| 8-core CPU | Multilingual 0.5B | well above 1.0 | Development only — expect minutes |

The `CHATTERBOX_VARIANT` setting exists precisely for this: `docker-compose.yml`
defaults the CPU stack to `nano`, and the GPU overlay switches to
`multilingual`.

## Hardware recommendations

### Development

```
CPU:      4+ cores (8 recommended for the Nano CPU path)
RAM:      16 GB
GPU:      optional — CPU + Nano, or the mock engine, is enough for the whole app
VRAM:     n/a on CPU
Storage:  20 GB (model weights ~2–3 GB, plus PyTorch and CUDA wheels)
```

With `VOICE_ENGINE=mock` the entire frontend, API, storage and test suite run on
any laptop in seconds, with no weights at all. That is the recommended setup for
frontend and API work.

### Small production deployment (single GPU, a handful of users)

```
CPU:      4–8 vCPU
RAM:      16 GB
GPU:      1× NVIDIA with 12+ GB VRAM (RTX 4090, A10G, L4)
VRAM:     8 GB minimum, 12 GB comfortable
Storage:  50 GB SSD (weights + user audio + database)
```

One API container, one worker, one GPU. `PRELOAD_MODEL=true` so the first user
request does not pay the load cost.

### CPU-only production (low volume, cost-sensitive)

```
CPU:      8+ cores
RAM:      16 GB
GPU:      none
Variant:  nano  (CHATTERBOX_VARIANT=nano)
```

English only, and lower quality than the 0.5B model — but it works, and it costs
a fraction of a GPU instance.

## Where the time goes

| Phase | When | Cost |
|---|---|---|
| Model load | Once per process | Seconds to tens of seconds; amortised by `PRELOAD_MODEL=true` |
| Voice conditioning | Once per voice | Speaker encoder + tokenizer + S3Gen reference embed |
| **Conditioning cache load** | Every generation | A `torch.load` of a small tensor bundle — this is the win |
| Synthesis | Every generation | Dominated by T3 autoregressive decoding, scales with text length |
| WAV write | Every generation | Negligible |

Persisting `Conditionals` is the single biggest architectural performance
decision in the app: without it, every generation would re-run the speaker
encoder and speech tokenizer over the reference clip. The integration test
`test_conditioning_cache_is_reused_across_generations` proves it works by
deleting the reference audio between two generations and asserting the second
still succeeds.

## Tuning

| Lever | Effect |
|---|---|
| `CHATTERBOX_VARIANT=nano` / `turbo` | Much faster, English only. Turbo's decoder is distilled to a single step |
| `PRELOAD_MODEL=true` | Moves the load cost from the first request to container start |
| `MAX_TEXT_CHARS` | Directly caps worst-case request latency |
| fp16 on GPU | Roughly halves VRAM; quality impact is model-dependent — measure |
| Shorter reference audio | No effect. Chatterbox uses only the first ~10 s regardless |

## Monitoring

Every generation persists its own telemetry, so you can answer "is it getting
slower?" without adding an APM:

```sql
SELECT
  engine,
  COUNT(*)                    AS n,
  ROUND(AVG(real_time_factor), 3)   AS avg_rtf,
  ROUND(MAX(real_time_factor), 3)   AS worst_rtf,
  ROUND(AVG(generation_seconds), 2) AS avg_seconds
FROM generations
GROUP BY engine;
```

`GET /api/v1/system/info` reports live device details including
`vram_allocated_mb`, and every API response carries an `X-Response-Time-Ms`
header.
