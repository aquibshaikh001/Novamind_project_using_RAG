"""
routers/voice.py  -  HTTP endpoints for speech.

    POST /api/voice/speak       {text}  ->  MP3 audio
    POST /api/voice/transcribe  audio   ->  {text}
"""

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from services import voice_service

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str


@router.post("/speak")
async def speak(req: SpeakRequest):
    """Text-to-speech. Needs internet (Edge-TTS)."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Nothing to speak.")
    try:
        audio = await voice_service.synthesize(req.text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Text-to-speech failed: {exc}")
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/transcribe")
def transcribe(file: UploadFile = File(...)):
    """Speech-to-text. Plain `def` because Whisper is CPU-heavy and blocking."""
    try:
        text = voice_service.transcribe(file.file.read())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
    return {"text": text}
