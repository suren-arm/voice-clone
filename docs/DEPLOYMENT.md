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

## Cloudflare Pages + Render (the shipped config)

This is the concrete, ready-to-run deployment this repository ships — not just
a recommendation. Cloudflare cannot run the backend at all: Workers has no
PyTorch runtime, so the split is Cloudflare for the frontend and an ordinary
container host for the FastAPI + Chatterbox backend. Of the GPU/CPU hosts
compared below, **Render** is the one used here, because it builds a plain
Dockerfile with zero platform-specific rewrites and bundles a persistent disk
for `storage/` and the model cache into the same service — no separate volume
product to configure.

```
Cloudflare Pages                              Render (Docker web service)
┌────────────────────────────┐         HTTPS  ┌───────────────────────────┐
│  Next.js static export      │  ────────────▶ │  FastAPI + Chatterbox     │
│  frontend/out/               │                │  backend/Dockerfile.render│
│  NEXT_PUBLIC_API_URL ────────┼───────────────▶│  /api/v1                  │
└────────────────────────────┘                │  /app/storage (disk)      │
                                               └───────────────────────────┘
```

**Why this environment could not execute the deploy itself.** This coding
session's outbound network is restricted to package registries and GitHub;
`api.cloudflare.com`, `dash.cloudflare.com`, `render.com` and every other
hosting provider's API are policy-blocked at the network layer (confirmed via
the egress proxy's status endpoint, which logs each as a `403` policy denial —
not a missing-credential or DNS problem). No Cloudflare or Render API token was
supplied either. Both are one-time, few-minutes manual steps in each
provider's own dashboard, from a machine with a normal internet connection —
there is no way to do them from inside this session, and no amount of retrying
changes that. Everything short of clicking "connect repository" is done:
the exact Docker image, the Blueprint, the build mode, and the CI workflow
that deploys automatically once the two secrets below exist.

### What's already in the repository

| File | Purpose |
|---|---|
| `frontend/next.config.ts` | `CLOUDFLARE_BUILD=1` switches to `output: 'export'` (plain static HTML/JS/CSS, no Workers runtime needed) |
| `frontend/public/_headers` | The security headers `next.config.ts`'s `headers()` sets normally — static export has no server to run that function, so Cloudflare Pages' own `_headers` mechanism carries them instead |
| `render.yaml` | Render Blueprint: Docker web service, persistent disk at `/app/storage`, every environment variable the backend needs for production |
| `backend/Dockerfile.render` | Single-stage CPU build. `backend/Dockerfile` is multi-stage (`cpu` then `gpu`); an unqualified build picks the *last* stage (`gpu`, CUDA-based), which is wrong for a CPU-only host. This file removes that ambiguity — it is not a second implementation, just the `cpu` stage isolated so any Docker-based PaaS builds the right thing without needing `--target` support |
| `.github/workflows/deploy-cloudflare-pages.yml` | Builds the static export and publishes it via `cloudflare/pages-action` on every push to `main`, once the secrets below are set. No-ops with a clear warning until then, so merging it does not break CI |

### One-time setup (5-10 minutes, needs a browser and your own accounts)

**1. Deploy the backend to Render**

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → connect this GitHub repository (grant Render read access if asked).
2. Render reads `render.yaml` and proposes one service, `voice-clone-api`. Accept it.
3. It will fail its first health check with no CORS origin set yet — that's expected; continue to step 3 below before worrying about it.
4. Once deployed, copy the assigned URL from the Render dashboard: `https://voice-clone-api.onrender.com`, or `https://voice-clone-api-<random>.onrender.com` if that exact name was already taken by someone else's Render account.

**2. Deploy the frontend to Cloudflare Pages**

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → this repository.
2. Build settings:
   | Field | Value |
   |---|---|
   | Framework preset | None (or Next.js — either works; the build script decides via `CLOUDFLARE_BUILD`) |
   | Build command | `CLOUDFLARE_BUILD=1 npm run build` |
   | Build output directory | `frontend/out` |
   | Root directory | `frontend` |
3. Environment variable (**Settings → Environment variables**, for the **Production** environment): `NEXT_PUBLIC_API_URL` = the Render URL from step 1.4.
4. Deploy. Cloudflare assigns `https://<project-name>.pages.dev` — the exact subdomain depends on the project name you chose when connecting the repo (it's a name you pick during step 1 above, not something this repo can predict, since `*.pages.dev` names are shared across every Cloudflare account on the internet).

**3. Close the loop: tell the backend which frontend origin to trust**

Back in the Render dashboard, on the `voice-clone-api` service → **Environment**:
set `CORS_ORIGINS` to the exact Pages URL from step 2.4 (`https://<project-name>.pages.dev`, no trailing slash; comma-separate if you also have a custom domain). Save — Render redeploys automatically. **The frontend cannot talk to the backend until this is set**: every request will fail in the browser console with a CORS error even though `curl` against the API works fine, because CORS is enforced by the browser reading this header, not by the API refusing the request server-side.

**4. (Optional) Automate future deploys with the included GitHub Actions workflow**

Steps 1-3 above use each provider's own Git integration, which is enough on
its own — Render and Cloudflare Pages both auto-deploy on every push once
connected. `.github/workflows/deploy-cloudflare-pages.yml` is an *alternative*
path to the same result via CI instead of Cloudflare's dashboard integration;
use it if you'd rather manage the deploy from GitHub Actions, or skip it and
rely on Cloudflare's own Git integration from step 2. If you do want it, add
in **Settings → Secrets and variables → Actions**:

| Type | Name | Value |
|---|---|---|
| Secret | `CLOUDFLARE_API_TOKEN` | Cloudflare dashboard → My Profile → API Tokens → Create Token → "Edit Cloudflare Workers" template |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare dashboard → any domain's Overview page, right sidebar |
| Variable | `NEXT_PUBLIC_API_URL` | The Render URL from step 1.4 |
| Variable | `CLOUDFLARE_PAGES_PROJECT` | The Pages project name from step 2.1, if you didn't use the default `ai-voice-studio` |

Don't run both the dashboard Git integration *and* this workflow against the
same Pages project — pick one, or they'll race each other on every push.

### Verifying it worked

```bash
curl -s https://voice-clone-api.onrender.com/health
# {"status":"ok","engineLoaded":false,"version":"0.1.0"}

curl -s https://voice-clone-api.onrender.com/api/v1/system/info | python3 -m json.tool
# engine.device should read "cpu"; engine.variant should read "turbo"
```

Then open the Pages URL in a browser with the developer console open: the
Network tab should show `system/info` succeeding with no CORS error, and
`/` should render the home page with a live "Backend status" card (this is
literally `GET /api/v1/system/info` — if it shows an error instead, CORS or
the API URL is still misconfigured; recheck steps 2.3 and 3 above).

`engineLoaded: false` on a fresh deploy is expected — `PRELOAD_MODEL=false`,
so weights load on the *first* real request (`POST /voices`), which will take
noticeably longer than every request after it.

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

The recommended, shipped path — see
[Cloudflare Pages + Render](#cloudflare-pages--render-the-shipped-config) above
for the full walkthrough. In short: this app needs **no** Workers runtime
adapter (`@cloudflare/next-on-pages` and its compatibility layer are
unnecessary overhead here) because every route is already a fully static,
client-rendered page with no API routes, middleware, or server actions —
verified by `grep`, not assumed. `next build` with `CLOUDFLARE_BUILD=1` (see
`frontend/next.config.ts`) produces a plain static export in `frontend/out/`
that Cloudflare Pages serves directly.

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
