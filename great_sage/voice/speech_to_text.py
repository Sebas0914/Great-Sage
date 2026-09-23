"""
Local speech-to-text via faster-whisper - CPU-only, fully offline, no
cloud API. Used by both push-to-talk and the wake-word listener (see
speech_input.py) to turn recorded microphone audio into text, which then
feeds into the same ChatEngine path a typed message would.

The model loads lazily (first call only) and stays cached for the life of
the process - loading takes a couple seconds, so it happens once, not per
utterance. First run also downloads the model (~145MB for "base.en") to
the Hugging Face cache.
"""

import logging

import numpy as np

log = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        # Keep the Windows build multilingual while taking the Linux build's
        # lazy-loading and diagnostics improvements. base (~145MB) supports
        # English and Spanish without requiring a separate model.
        # int8 compute keeps it fast without a GPU.
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def transcribe(audio: np.ndarray) -> str:
    """audio must be mono float32 samples at 16000 Hz (speech_input.py's
    recorders capture at that rate directly, so no resampling needed)."""
    if audio.size == 0:
        log.warning("Transcription skipped: empty recording")
        return ""
    model = _get_model()
    segments, _ = model.transcribe(audio, language="es", vad_filter=True)
    text = "".join(seg.text for seg in segments).strip()

    # Log the result so push-to-talk failures are visible in packaged builds.
    # In particular, vad_filter depends on faster-whisper's Silero VAD asset;
    # if that asset is missing, the recording can be processed with no text
    # and the caller otherwise has no useful clue what happened.
    seconds = audio.size / 16000.0
    if text:
        log.info("Transcribed %.1fs of audio: %r", seconds, text)
    else:
        log.warning(
            "Transcribed %.1fs of audio but got NO text. Either nothing was "
            "said, or the VAD filter rejected it - check that "
            "faster_whisper/assets/silero_vad_v6.onnx is present.", seconds)
    return text
