import logging
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from multimodal.vision import analyze_emergency_image, validate_image_bytes

logger = logging.getLogger("smart112.api.vision")
router = APIRouter()

MAX_IMAGE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB limit


@router.post("/analyze")
async def analyze_scene_image(file: UploadFile = File(...)):
    """
    Ingest and inspect an emergency scene photograph (JPEG, PNG, WebP) for tactical hazards.
    Applies Gemini Vision VLM with deterministic offline fallback (BUG-09).
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image uploaded or missing filename.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty (0 bytes).",
        )

    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds maximum permissible upload size of 15 MB.",
        )

    is_valid, mime_type = validate_image_bytes(content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported or corrupted image container ({mime_type}). Only JPEG, PNG, and WebP are supported.",
        )

    try:
        analysis = await analyze_emergency_image(content, file.filename)
    except Exception as exc:
        logger.error("Vision inspection exception: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scene inspection processing failed: {str(exc)}",
        )

    return {
        "filename": file.filename,
        "mime_type": mime_type,
        "size_bytes": len(content),
        "visual_assessment": analysis,
        "requires_human_verification": True,
    }
