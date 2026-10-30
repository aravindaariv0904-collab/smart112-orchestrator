import base64
import io
import logging
import math
import struct
import wave
from typing import Any, Dict

logger = logging.getLogger("smart112.multimodal.tts")

GUIDANCE_TEMPLATES = {
    "CPR_ASSIST": (
        "SMART 112 Medical Advisory: Place the heel of one hand in the center of the chest. "
        "Interlock your other hand on top. Push down hard and fast, at least two inches deep, "
        "at a rhythm of 100 to 120 beats per minute. Do not stop until the emergency crew arrives."
    ),
    "FIRE_EVAC": (
        "SMART 112 Fire Safety Advisory: Evacuate the structure immediately. "
        "Stay low beneath the smoke layer. Close doors behind you to slow flame spread. "
        "Do not use elevators. Assemble at least fifty meters away from the building."
    ),
    "HEMORRHAGE_CONTROL": (
        "SMART 112 Trauma Advisory: Apply immediate, firm, direct pressure over the bleeding site "
        "using a clean cloth or sterile dressing. Maintain continuous pressure without lifting the cloth. "
        "If blood soaks through, add another layer on top and keep pressing firmly."
    ),
    "CHOKING_ADULT": (
        "SMART 112 Respiratory Advisory: Stand behind the person, wrap your arms around their waist. "
        "Make a fist above the navel, grasp your fist with your other hand, and give quick inward and upward thrusts."
    ),
}


def _generate_synthetic_tone_wav(duration_seconds: float = 3.0, freq_hz: float = 440.0) -> bytes:
    """
    Generates a deterministic PCM WAV audio stream using Python's standard library.
    Guarantees zero external dependency failure for life-safety audio playback.
    """
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            # Generate dual-frequency acoustic chime with soft decay
            envelope = math.exp(-2.0 * (t % 0.8))
            value = int(
                16000 * envelope * (
                    0.6 * math.sin(2.0 * math.pi * freq_hz * t)
                    + 0.4 * math.sin(2.0 * math.pi * (freq_hz * 1.5) * t)
                )
            )
            value = max(-32768, min(32767, value))
            samples.append(struct.pack("<h", value))

        wav_file.writeframes(b"".join(samples))

    buffer.seek(0)
    return buffer.read()


def synthesize_emergency_guidance(
    guidance_type: str = "CPR_ASSIST",
    custom_text: str = "",
    language: str = "en",
) -> Dict[str, Any]:
    """
    Synthesize life-safety audio instructions with safe fallback.
    Returns:
        {
            "guidance_type": str,
            "text": str,
            "audio_base64": str,
            "mime_type": "audio/wav",
            "duration_seconds": float,
            "synthesis_engine": str,
        }
    """
    guidance_key = guidance_type.upper()
    text = custom_text or GUIDANCE_TEMPLATES.get(
        guidance_key,
        "SMART 112 Emergency Dispatch. Emergency units have been dispatched. Stay on the line."
    )

    audio_bytes = None
    engine_name = "SYNTHETIC_ACOUSTIC_CHIME"

    # Try optional TTS engines if installed
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=language if language in ("en", "hi", "te") else "en", slow=False)
        out_buf = io.BytesIO()
        tts.write_to_fp(out_buf)
        out_buf.seek(0)
        audio_bytes = out_buf.read()
        mime_type = "audio/mpeg"
        engine_name = "GTTS_CLOUD_STREAM"
    except Exception as e:
        logger.info("Optional gTTS engine not loaded (%s); using pure standard library PCM synthesizer.", e)
        audio_bytes = _generate_synthetic_tone_wav(duration_seconds=3.5, freq_hz=520.0)
        mime_type = "audio/wav"

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    duration = max(2.5, round(len(text.split()) * 0.35, 1))

    return {
        "guidance_type": guidance_key,
        "text": text,
        "language": language,
        "audio_base64": audio_b64,
        "mime_type": mime_type,
        "duration_seconds": duration,
        "synthesis_engine": engine_name,
        "size_bytes": len(audio_bytes),
    }
