"""
services/voice_service.py  -  speech in (STT) and speech out (TTS).

WHY THIS FILE EXISTS
    Voice is optional and uses heavy libraries, so it lives in its own file
    and every heavy import happens INSIDE the function (lazy import).
    That way the whole app still starts even if voice packages are missing.

    TTS  (text -> mp3)   : Edge-TTS, needs internet, no GPU, no API key.
    STT  (audio -> text) : faster-whisper, runs on your CPU, fully offline.
"""

import tempfile
from pathlib import Path

from config import settings

_whisper_model = None      # loaded once, on first use (loading is slow)


async def synthesize(text: str) -> bytes:
    """Convert text to MP3 audio bytes using Microsoft Edge neural voices."""
    import edge_tts   # lazy import

    # Very long text makes very long audio; 1500 characters is plenty.
    communicate = edge_tts.Communicate(text[:1500], settings.TTS_VOICE)
    audio = bytearray()
    async for part in communicate.stream():
        if part["type"] == "audio":          # other parts are word-timing info
            audio.extend(part["data"])
    return bytes(audio)


def transcribe(audio_bytes: bytes) -> str:
    """Convert recorded audio (webm/wav/mp3 ...) to text with faster-whisper."""
    global _whisper_model
    if not settings.STT_ENABLED:
        raise RuntimeError(
            "Voice input is disabled. Set STT_ENABLED=true in backend/.env and run: "
            "pip install -r requirements-voice.txt"
        )
    try:
        from faster_whisper import WhisperModel   # lazy import
    except ImportError:
        raise RuntimeError("faster-whisper is not installed. Run: pip install -r requirements-voice.txt")

    if _whisper_model is None:
        # int8 = small and fast on a normal CPU
        _whisper_model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")

    # faster-whisper reads from a file, so write the bytes to a temp file first.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)
    try:
        segments, _info = _whisper_model.transcribe(str(tmp_path))
        return " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        tmp_path.unlink(missing_ok=True)       # always clean up the temp file
