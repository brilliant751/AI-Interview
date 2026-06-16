FROM python:3.10-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements-service.txt /workspace/requirements-service.txt
COPY app /workspace/app
COPY funasr_source_code /workspace/funasr_source_code

RUN python -m pip install --upgrade pip \
    && pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install -e /workspace/funasr_source_code \
    && pip install -r /workspace/requirements-service.txt

EXPOSE 10095

ENV MODEL_NAME=paraformer-zh \
    VAD_MODEL=fsmn-vad \
    PUNC_MODEL=ct-punc \
    DEVICE=cpu \
    BATCH_SIZE_S=300

CMD ["python", "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "10095"]
