import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from funasr import AutoModel

app = FastAPI(title="FunASR ASR Service", version="1.0.0")


class PathRequest(BaseModel):
    audio_path: str


@lru_cache(maxsize=1)
def get_model() -> AutoModel:
    model_name = os.getenv("MODEL_NAME", "paraformer-zh")
    vad_model = os.getenv("VAD_MODEL", "fsmn-vad")
    punc_model = os.getenv("PUNC_MODEL", "ct-punc")
    device = os.getenv("DEVICE", "cpu")

    return AutoModel(
        model=model_name,
        vad_model=vad_model,
        punc_model=punc_model,
        device=device,
    )


def _extract_text(result: List[Dict[str, Any]]) -> str:
    if not result:
        return ""
    first = result[0]
    if isinstance(first, dict):
        return str(first.get("text", "")).strip()
    return str(first).strip()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/asr/path")
def asr_by_path(payload: PathRequest) -> Dict[str, Any]:
    path = Path(payload.audio_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"audio file not found: {path}")

    model = get_model()
    batch_size_s = int(os.getenv("BATCH_SIZE_S", "300"))
    result = model.generate(input=str(path), batch_size_s=batch_size_s)

    return {
        "text": _extract_text(result),
        "raw": result,
        "audio_path": str(path),
    }


@app.post("/asr/file")
async def asr_by_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    suffix = Path(file.filename or "upload.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = Path(tmp.name)
        tmp.write(await file.read())

    try:
        model = get_model()
        batch_size_s = int(os.getenv("BATCH_SIZE_S", "300"))
        result = model.generate(input=str(temp_path), batch_size_s=batch_size_s)
        return {
            "text": _extract_text(result),
            "raw": result,
            "filename": file.filename,
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()
