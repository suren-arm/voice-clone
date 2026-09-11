# Deployment

## Shape

The frontend is a static-ish Next.js app; the backend needs a GPU (or a lot of
CPU). They deploy separately.

```
   Vercel / Netlify / Cloudflare            GPU host
   ┌──────────────────────────┐        ┌──────────────────────┐
   │  Next.js frontend        │  HTTPS │  FastAPI + PyTorch   │
   │  NEXT_PUBLIC_API_URL ────┼───────▶│  /api/v1             │
   └──────────────────────────┘        │  Chatterbox          │
                                       │  storage/ + SQLite   │
                                       └──────────────────────┘
```

Two things follow from this split and are easy to get wrong:

1. **`NEXT_PUBLIC_API_URL` is inlined at build time**, not read at runtime.
   Changing it means rebuilding the frontend.
2. **`CORS_ORIGINS` on the backend must list the frontend's exact origin**, or
   every request fails in the browser with an opaque CORS error while `curl`
   works fine.

---

## Recommended MVP: one GPU box, both containers

Simplest thing that works, and the cheapest way to have a real deployment:

```bash
git clone <repo> && cd voice-clone
cp .env.example .env
# edit: CORS_ORIGINS, NEXT_PUBLIC_API_URL

docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
python scripts/download_model.py            # optional: pre-fetch weights
```

Put a TLS-terminating reverse proxy in front. **Microphone capture requires a
secure context** — `getUserMedia` is unavailable over plain HTTP except on
`localhost`, so without HTTPS the core feature simply does not work.

Caddy does this in four lines:

```caddyfile
studio.example.com {
    handle /api/* { reverse_proxy api:8000 }
    handle /health { reverse_proxy api:8000 }
    handle        { reverse_proxy frontend:3000 }
}
```

Same-origin like this also sidesteps CORS entirely: set
`NEXT_PUBLIC_API_URL=https://studio.example.com`.

---

## GPU hosting options

Prices move constantly. **Check current rates before committing** — the figures
below are what public comparisons reported around the research date
(11 September 2026) and are indicative only.

| Provider | Model | Reported RTX 4090 rate | Fit |
|---|---|---|---|
| **RunPod** (Community) | Per-second GPU pods | ~$0.34/hr | Best balance of price and ergonomics — recommended for a first deployment |
| RunPod (Secure) | Datacenter pods | ~$0.69/hr | When you need an SLA |
| **Vast.ai** | Marketplace | ~$0.29–0.50/hr | Cheapest; host quality varies, verified hosts cost more |
| Lambda Labs | Dedicated | varies | Simple, reliable, fewer GPU types |
| AWS / GCP / Azure | `g5`/`g4dn`, `L4`, `NCas` | Well above the above | Only if you are already there and need the compliance story |
| **Own hardware** | An RTX 3060+ box | electricity | Cheapest at any real duty cycle |

**Recommendation:** start with a **RunPod Community RTX 4090**, or your own
GPU if you have one. Serverless GPU offerings are attractive for bursty traffic
but pay a cold-start penalty loading a 1 GB model, which is exactly the latency
this app cannot hide.

### RunPod notes

- Use a **network volume** mounted at `/cache/huggingface` so weights survive
  pod restarts. Downloading ~1 GB on every cold start is slow and, on metered
  egress, not free.
- Persist `/app/storage` on the same volume, or user voices vanish on restart.
- Expose port 8000 via the HTTP proxy and set `CORS_ORIGINS` to your frontend.

---

## Frontend hosting

### Vercel (recommended)

```bash
cd frontend && vercel
# Project settings → Environment Variables:
#   NEXT_PUBLIC_API_URL = https://your-gpu-host.example.com
```

Zero-config for Next.js App Router. Remember to **redeploy** after changing the
API URL — it is compiled in.

### Netlify

Works via `@netlify/plugin-nextjs`. Same build-time variable caveat.

### Cloudflare Pages

Needs `@cloudflare/next-on-pages`. This app is a good fit because every route is
statically prerendered and all dynamic behaviour is client-side fetches — but
verify the build, since Workers runtime support for Next features moves quickly.

### Self-hosted

```bash
cd frontend
DOCKER_BUILD=1 NEXT_PUBLIC_API_URL=https://api.example.com npm run build
node .next/standalone/server.js
```

Or use `frontend/Dockerfile`, which does exactly this.

---

## Production checklist

**Before exposing anything:**

- [ ] **Authentication in front of the API.** It is unauthenticated by design in
      the MVP — anyone who can reach it owns every voice on it. Use a VPN, an
      authenticating proxy, or wait for Phase 2. See
      [SECURITY.md](./SECURITY.md#what-is-deliberately-absent).
- [ ] HTTPS everywhere (also a hard requirement for microphone access)
- [ ] `ENVIRONMENT=production` (switches logging to JSON)
- [ ] `CORS_ORIGINS` set to exact origins, never `*`
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] `REQUIRE_CONSENT=true`
- [ ] `PRELOAD_MODEL=true` so the first user is not the one who waits
- [ ] Persistent volumes for `/app/storage` **and** `/cache/huggingface`
- [ ] A backup of `storage/` — it holds user voice recordings
- [ ] `--proxy-headers --forwarded-allow-ips=<proxy>` if behind a proxy, so rate
      limiting sees real client addresses
- [ ] `MAX_TEXT_CHARS` tuned to your measured RTF (see
      [PERFORMANCE.md](./PERFORMANCE.md))

## Health and observability

| Endpoint | Use |
|---|---|
| `GET /health` | Liveness/readiness — reports `engineLoaded` |
| `GET /api/v1/system/info` | Engine, device, VRAM, languages, limits |
| `X-Response-Time-Ms` | On every response |

Both Docker images define `HEALTHCHECK`. The GPU image allows a 180 s start
period, because loading weights on a cold cache genuinely takes that long.

## Scaling

1. **One GPU, more throughput** — nothing to do; the engine serialises access
   because a single GPU cannot usefully run two syntheses at once.
2. **More GPUs** — N single-worker API containers behind a load balancer.
   Requires shared storage and a shared database first: PostgreSQL + S3/MinIO,
   plus Redis-backed rate limiting. All three swaps are localised; see
   [ARCHITECTURE.md](./ARCHITECTURE.md).
3. **Long text** — introduce the job queue *before* adding GPUs. A queue with
   one GPU beats no queue with three.
