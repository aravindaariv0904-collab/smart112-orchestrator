import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from backend.app.core.config import settings
from multimodal.transcriber import transcribe_audio_file
from ai.extractor import extract_emergency_facts

logger = logging.getLogger("smart112.api.audio")
router = APIRouter()

@router.post("/transcribe")
async def transcribe_emergency_audio(
    file: UploadFile = File(...)
):
    """
    Ingests raw emergency call audio files (.wav, .mp3, .ogg).
    Enforces 15 MB upload size limit and strict MIME type validation.
    Executes speech-to-text with faster-whisper and runs AI entity extraction.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file uploaded or invalid filename."
        )

    # 1. Validate MIME type
    content_type = (file.content_type or "").lower()
    # Normalize potential octet-stream based on file extension
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    valid_exts = {"wav", "mp3", "ogg", "mpeg"}
    
    if content_type not in settings.ALLOWED_AUDIO_MIME_TYPES and ext not in valid_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported media type '{content_type or ext}'. "
                f"Permitted MIME types are: {', '.join(settings.ALLOWED_AUDIO_MIME_TYPES)}"
            )
        )

    # 2. Read content and validate size limit (15 MB)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty (0 bytes)."
        )

    if len(content) > settings.MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum permissible upload size of 15 MB (Received {len(content) / (1024 * 1024):.2f} MB)."
        )

    # 3. Transcribe audio
    try:
        transcript, language, confidence = transcribe_audio_file(content, file.filename)
    except Exception as exc:
        logger.error(f"STT processing failure: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech-to-text transcription engine failed to process audio."
        )
    
    # 4. Extract facts via AI pipeline with deterministic fallback
    extracted_facts = await extract_emergency_facts(transcript)

    return {
        "filename": file.filename,
        "size_bytes": len(content),
        "transcript": transcript,
        "language": language,
        "stt_confidence": confidence,
        "extracted_facts": extracted_facts
    }
