# =============================================================================
# AI Voice Studio - backend image
#
# Two stages so that CPU and GPU deployments share one Dockerfile:
#
#   docker build --target cpu -t voice-studio-api:cpu backend/
#   docker build --target gpu -t voice-studio-api:gpu backend/
#
# Model weights are NEVER baked in. They land in the Hugging Face cache, which
# docker-compose mounts as a named volume -- so an image rebuild does not
# re-download several gigabytes.
# =============================================================================

# -----------------------------------------------------------------------------
# Base: shared application layer, CPU-only torch.
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS cpu

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/cache/huggingface

# ffmpeg decodes what browsers actually record (WebM/Opus, MP4/AAC);
# libsndfile1 backs soundfile; espeak-ng powers the Armenian G2P diagnostics.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        espeak-ng \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the CPU torch wheels explicitly, before the requirements file pulls
# chatterbox-tts: the default PyPI wheel for torch drags in the full CUDA stack
# (~2.5 GB) even on a CPU-only image.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.6.0 torchaudio==2.6.0

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

COPY ai/        /app/ai/
COPY backend/   /app/backend/
COPY scripts/   /app/scripts/

# Run as a non-root user; give it the storage tree and the weight cache.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage/voices /app/storage/generated /app/storage/tmp /cache/huggingface \
    && chown -R appuser:appuser /app /cache
USER appuser

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# One worker on purpose: the model is loaded per process, and a second worker
# would double VRAM for no throughput gain on a single GPU.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# -----------------------------------------------------------------------------
# GPU: same application, CUDA-enabled torch.
# Needs the NVIDIA Container Toolkit on the host.
# -----------------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS gpu

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/cache/huggingface \
    DEVICE=cuda

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip \
        ffmpeg libsndfile1 espeak-ng curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3

WORKDIR /app

RUN python -m pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cu124 \
        torch==2.6.0 torchaudio==2.6.0

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

COPY ai/        /app/ai/
COPY backend/   /app/backend/
COPY scripts/   /app/scripts/

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage/voices /app/storage/generated /app/storage/tmp /cache/huggingface \
    && chown -R appuser:appuser /app /cache
USER appuser

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
