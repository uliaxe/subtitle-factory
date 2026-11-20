FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,video

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY app ./app

RUN useradd --create-home appuser && mkdir -p /models /work && chown appuser /models /work
USER appuser

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=15m --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/healthz', timeout=4)"

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
