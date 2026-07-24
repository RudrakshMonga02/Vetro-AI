"""Server-side MP3 text-to-speech for English and Kannada responses."""
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from gtts import gTTS
from pydantic import BaseModel, Field

from api.rate_limiter import limiter as _limiter

router = APIRouter()

# Keeps a single request comfortably below gTTS provider limits and prevents
# unbounded external-network work from a public endpoint.
MAX_TTS_TEXT_LENGTH = 4_000


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_TEXT_LENGTH)
    language: Literal["en", "kn"] = "en"


def _generate_mp3(text: str, language: str) -> BytesIO:
    """Generate an MP3 entirely in memory; gTTS itself is synchronous."""
    audio_buffer = BytesIO()
    gTTS(text=text, lang=language).write_to_fp(audio_buffer)
    audio_buffer.seek(0)
    return audio_buffer


@router.post("/speak")
@_limiter.limit("20/minute")
async def speak_text(request: Request, body: SpeakRequest) -> StreamingResponse:
    try:
        # gTTS calls an external service synchronously. Running it in the
        # threadpool leaves the FastAPI event loop free for other requests.
        audio_buffer = await run_in_threadpool(
            _generate_mp3,
            body.text.strip(),
            body.language,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Text-to-speech generation is currently unavailable.",
        ) from exc

    return StreamingResponse(
        audio_buffer,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline; filename=vetro-response.mp3",
        },
    )
