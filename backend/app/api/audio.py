import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ai.extractor import extract_emergency_facts
from ai.fallback import generate_fallback_assessment
from backend.app.core.config import settings
from multimodal.transcriber import transcribe_audio_file
from multimodal.tts import GUIDANCE_TEMPLATES, synthesize_emergency_guidance

logger = logging.getLogger("smart112.api.audio")
router = APIRouter()

# Container magic numbers accepted for the supported audio formats.
AUDIO_MAGIC_PREFIXES = (
    b"RIFF",  # WAV / AVI container
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
    speech-to-text plus AI fact extraction with safe, non-crashing failure handling.
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
        res = await run_in_threadpool(transcribe_audio_file, content, file.filename)
        if len(res) == 4:
            transcript, language, confidence, stt_status = res
        else:
            transcript, language, confidence = res[:3]
            stt_status = "SUCCESS" if transcript else "NO_SPEECH_DETECTED"
    except Exception as exc:
        logger.error("STT processing failure: %s", exc)
        transcript, language, confidence, stt_status = "", "unknown", 0.0, "STT_ERROR"

    # Safe audio transcription failure handling:
    # If transcription failed or returned no speech, do not throw a 500 server crash!
    # Generate fallback facts and flag for human review so operators can listen manually.
    if stt_status not in ("SUCCESS", "SIMULATED_TEST") or not transcript.strip():
        display_transcript = (
            f"[Automated transcription {stt_status.lower().replace('_', ' ')}. "
            f"Audio preserved for manual operator verification.]"
        )
        extracted_facts = generate_fallback_assessment(
            display_transcript,
            f"AUDIO_STT_{stt_status}",
        )
        uncertainty = list(extracted_facts.get("uncertainty_flags", []))
        flag = f"AUDIO_{stt_status}"
        if flag not in uncertainty:
            uncertainty.append(flag)
        extracted_facts["uncertainty_flags"] = uncertainty
        extracted_facts["requires_human_review"] = True
    else:
        display_transcript = transcript
        extracted_facts = await extract_emergency_facts(transcript)

    return {
        "filename": file.filename,
        "size_bytes": len(content),
        "transcription_status": stt_status,
        "transcript": display_transcript,
        "language": language,
        "stt_confidence": round(confidence, 2),
        "extracted_facts": extracted_facts,
        "requires_human_review": extracted_facts.get("requires_human_review", True),
    }


class GuidanceRequest(BaseModel):
    guidance_type: str = "CPR_ASSIST"
    custom_text: Optional[str] = None
    language: str = "en"


@router.get("/guidance-templates")
def list_guidance_templates():
    """Retrieve standard emergency life-safety voice guidance templates (BUG-08)."""
    return {
        "templates": [
            {"type": k, "advisory": v} for k, v in GUIDANCE_TEMPLATES.items()
        ]
    }


@router.post("/synthesize-guidance")
def synthesize_guidance_audio(payload: GuidanceRequest):
    """
    Synthesize life-safety caller audio guidance (CPR pacing, fire evacuation, bleeding control).
    Returns audio/wav or audio/mpeg stream as base64 payload with safe fallback (BUG-08).
    """
    result = synthesize_emergency_guidance(
        guidance_type=payload.guidance_type,
        custom_text=payload.custom_text or "",
        language=payload.language or "en",
    )
    return result
