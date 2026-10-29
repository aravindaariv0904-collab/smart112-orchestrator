import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from ai.extractor import extract_emergency_facts
from backend.app.core.config import settings
from multimodal.transcriber import transcribe_audio_file

logger = logging.getLogger("smart112.api.audio")
router = APIRouter()

# Container magic numbers accepted for the supported audio formats.
AUDIO_MAGIC_PREFIXES = (
    b"RIFF",  # WAV / AVI container (WAV verified below by extension+mime)
    b"ID3",  # MP3 with ID3 tag
    b"OggS",  # OGG / Opus
    b"fLaC",  # FLAC
    b"\xff\xfb",  # MPEG-1 Layer III frame
    b"\xff\xf3",  # MPEG-2 Layer III frame
    b"\xff\xf2",  # MPEG-2 Layer III frame (CRC)
    b"\xff\xf1",  # AAC ADTS
    b"\xff\xf9",  # AAC ADTS (MPEG-4)
)

READ_CHUNK_BYTES = 1024 * 1024


def _looks_like_audio(content: bytes) -> bool:
    """Reject payloads that claim an audio MIME type but carry binary/noise headers."""
    if not content:
        return False
    return any(content.startswith(magic) for magic in AUDIO_MAGIC_PREFIXES)


async def _read_limited(file: UploadFile, limit_bytes: int) -> bytes:
    """Stream the upload in chunks and abort as soon as the size ceiling is crossed."""
    buffer = bytearray()
    while True:
        chunk = await file.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > limit_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "File exceeds maximum permissible upload size of "
                    f"{limit_bytes // (1024 * 1024)} MB."
                ),
            )
    return bytes(buffer)


@router.post("/transcribe")
async def transcribe_emergency_audio(file: UploadFile = File(...)):
    """
    Ingest raw emergency call audio (.wav, .mp3, .ogg).

    Enforces the 15 MB upload ceiling and strict MIME/container validation, then runs
    speech-to-text plus AI fact extraction.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file uploaded or invalid filename.",
        )

    content_type = (file.content_type or "").lower()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    valid_exts = {"wav", "mp3", "ogg", "mpeg"}

    if content_type not in settings.ALLOWED_AUDIO_MIME_TYPES and ext not in valid_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported media type '{content_type or ext}'. "
                f"Permitted MIME types are: {', '.join(settings.ALLOWED_AUDIO_MIME_TYPES)}"
            ),
        )

    content = await _read_limited(file, settings.MAX_AUDIO_UPLOAD_BYTES)
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty (0 bytes).",
        )

    if not _looks_like_audio(content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload is not a recognized audio container (WAV, MP3, OGG or FLAC).",
        )

    # Transcription is CPU-bound: keep the event loop free for live dispatch traffic.
    try:
        transcript, language, confidence = await run_in_threadpool(
            transcribe_audio_file, content, file.filename
        )
    except Exception as exc:
        logger.error("STT processing failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech-to-text transcription engine failed to process audio.",
        )

    extracted_facts = await extract_emergency_facts(transcript)

    return {
        "filename": file.filename,
        "size_bytes": len(content),
        "transcript": transcript,
        "language": language,
        "stt_confidence": confidence,
        "extracted_facts": extracted_facts,
    }
