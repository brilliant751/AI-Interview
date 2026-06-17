import tempfile
from pathlib import Path

import paddle
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from paddlespeech.cli.tts import TTSExecutor

app = FastAPI(title="PaddleSpeech TTS Service", version="0.1.0")
_tts_executor = None


class TTSRequest(BaseModel):
    text: str


def get_tts_executor() -> TTSExecutor:
    global _tts_executor
    if _tts_executor is None:
        _tts_executor = TTSExecutor()
    return _tts_executor


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts")
def tts(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_path = f.name

    tts_executor = get_tts_executor()
    tts_executor(
        text=text,
        output=output_path,
        am="fastspeech2_csmsc",
        voc="hifigan_csmsc",
        lang="zh",
        device=paddle.get_device(),
    )

    wav_path = Path(output_path)
    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=wav_path.name,
        background=BackgroundTask(lambda: wav_path.unlink(missing_ok=True)),
    )
