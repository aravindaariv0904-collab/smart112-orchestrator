import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from multimodal.transcriber import transcribe_audio_file
from ai.extractor import extract_emergency_facts

logger = logging.getLogger("smart112.api.audio")
router = APIRouter()

@router.post("/transcribe")
async def transcribe_emergency_audio(
    file: UploadFile = File(...)
):
    """
    Ingests raw emergency call audio files (.wav, .mp3, .ogg),
    executes speech-to-text with faster-whisper, and runs AI entity extraction.
    """
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No audio file uploaded.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    # 1. Transcribe audio
    transcript, language, confidence = transcribe_audio_file(content, file.filename or "call.wav")
    
    # 2. Extract facts via AI pipeline
    extracted_facts = await extract_emergency_facts(transcript)

    return {
        "transcript": transcript,
        "language": language,
        "stt_confidence": confidence,
        "extracted_facts": extracted_facts
    }
