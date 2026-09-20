"""Local Japanese -> Raphael voice pipeline.

Pipeline:
    Great Sage text -> Piper Plus Japanese TTS -> Applio/RVC Raphael model.

Both stages are local. Piper Plus runs in a dedicated Python 3.11
environment and Applio is an external checkout with its own environment.
Great Sage itself stays on Python 3.14.

This engine deliberately runs RVC on CPU by default because the target
machine has only 4 GB VRAM and Ollama already occupies part of it.
Set RAPHAEL_RVC_CPU = False only if there is enough free VRAM.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Optional

from great_sage.config import settings
from great_sage.voice.base import VoiceError, VoiceOutput
from great_sage.voice.sinks import AudioSink, LocalSpeakerSink

log = logging.getLogger(__name__)


class RaphaelVoiceOutput(VoiceOutput):
    def __init__(
        self,
        sink: Optional[AudioSink] = None,
    ):
        self._sink = sink or LocalSpeakerSink()
        self._stop_requested = False
        self._validate_configuration()

    @property
    def current_sink(self) -> AudioSink:
        return self._sink

    def set_sink(self, sink: AudioSink) -> None:
        self._sink = sink

    def set_fx(self, **kwargs) -> None:
        # Kept for compatibility with the HUD. Raphael output is intentionally
        # already post-processed by RVC; the existing VoiceFX can still be
        # applied by the sink path later if the engine grows that support.
        return None

    def _validate_configuration(self) -> None:
        required = {
            "RAPHAEL_PIPER_PYTHON": settings.RAPHAEL_PIPER_PYTHON,
            "RAPHAEL_PIPER_MODEL": settings.RAPHAEL_PIPER_MODEL,
            "RAPHAEL_APPLIO_DIR": settings.RAPHAEL_APPLIO_DIR,
            "RAPHAEL_APPLIO_PYTHON": settings.RAPHAEL_APPLIO_PYTHON,
            "RAPHAEL_MODEL_PATH": settings.RAPHAEL_MODEL_PATH,
            "RAPHAEL_INDEX_PATH": settings.RAPHAEL_INDEX_PATH,
        }
        missing = [
            f"{name}={value!r}"
            for name, value in required.items()
            if not value
        ]
        if missing:
            raise VoiceError(
                "Raphael voice is not configured. Missing: " + ", ".join(missing)
            )

        if not os.path.isfile(settings.RAPHAEL_PIPER_PYTHON):
            raise VoiceError(
                f"Raphael Piper Python was not found: {settings.RAPHAEL_PIPER_PYTHON}"
            )
        if not os.path.isfile(settings.RAPHAEL_APPLIO_PYTHON):
            raise VoiceError(
                f"Raphael Applio Python was not found: {settings.RAPHAEL_APPLIO_PYTHON}"
            )
        if not os.path.isdir(settings.RAPHAEL_APPLIO_DIR):
            raise VoiceError(
                f"Applio directory was not found: {settings.RAPHAEL_APPLIO_DIR}"
            )
        if not os.path.isfile(settings.RAPHAEL_MODEL_PATH):
            raise VoiceError(
                f"Raphael model was not found: {settings.RAPHAEL_MODEL_PATH}"
            )
        if not os.path.isfile(settings.RAPHAEL_INDEX_PATH):
            raise VoiceError(
                f"Raphael index was not found: {settings.RAPHAEL_INDEX_PATH}"
            )

    def _run(self, command, cwd=None, env=None, label="command") -> None:
        log.debug("Raphael pipeline: %s", " ".join(map(str, command)))
        try:
            result = subprocess.run(
                [str(x) for x in command],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=getattr(settings, "RAPHAEL_COMMAND_TIMEOUT_SECONDS", 180),
            )
        except subprocess.TimeoutExpired as exc:
            raise VoiceError(f"Raphael {label} timed out.") from exc
        except OSError as exc:
            raise VoiceError(f"Could not start Raphael {label}: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if len(detail) > 1600:
                detail = detail[-1600:]
            raise VoiceError(
                f"Raphael {label} failed (exit {result.returncode})."
                + (f"\n{detail}" if detail else "")
            )

    def _synthesize_piper(self, text: str, output_path: str) -> None:
        command = [
            settings.RAPHAEL_PIPER_PYTHON,
            "-m",
            "piper_plus",
            "--model",
            settings.RAPHAEL_PIPER_MODEL,
            "--text",
            text,
            "--output_file",
            output_path,
        ]
        if settings.RAPHAEL_PIPER_SPEAKER is not None:
            command += ["--speaker", str(settings.RAPHAEL_PIPER_SPEAKER)]

        env = os.environ.copy()
        env["PIPER_OFFLINE_MODE"] = "1"
        self._run(command, env=env, label="Japanese TTS")

    def _convert_raphael(self, input_path: str, output_path: str) -> None:
        command = [
            settings.RAPHAEL_APPLIO_PYTHON,
            "core.py",
            "infer",
            "--input-path",
            input_path,
            "--output-path",
            output_path,
            "--pth-path",
            settings.RAPHAEL_MODEL_PATH,
            "--index-path",
            settings.RAPHAEL_INDEX_PATH,
            "--f0-method",
            settings.RAPHAEL_F0_METHOD,
            "--index-rate",
            str(settings.RAPHAEL_INDEX_RATE),
            "--protect",
            str(settings.RAPHAEL_PROTECT),
            "--embedder-model",
            settings.RAPHAEL_EMBEDDER_MODEL,
            "--sid",
            str(settings.RAPHAEL_SPEAKER_ID),
        ]

        env = os.environ.copy()
        if settings.RAPHAEL_RVC_CPU:
            # Keep RVC off the GTX 1650 Ti so Qwen has the VRAM headroom.
            env["CUDA_VISIBLE_DEVICES"] = ""
        self._run(
            command,
            cwd=settings.RAPHAEL_APPLIO_DIR,
            env=env,
            label="Raphael RVC conversion",
        )

    def _play_file(self, path: str, spoken: str) -> None:
        if self._stop_requested:
            return
        setattr(self._sink, "pending_text", spoken)
        try:
            self._sink.play_file(path)
        except Exception as exc:
            raise VoiceError(f"Raphael audio playback failed: {exc}") from exc

    def speak(self, text: str) -> None:
        spoken = " ".join((text or "").split())
        if not spoken:
            return

        self._stop_requested = False
        with tempfile.TemporaryDirectory(prefix="great-sage-raphael-") as tmp:
            base = os.path.join(tmp, "japanese.wav")
            converted = os.path.join(tmp, "raphael.wav")
            self._synthesize_piper(spoken, base)
            if self._stop_requested:
                return
            self._convert_raphael(base, converted)
            if not os.path.isfile(converted):
                raise VoiceError(
                    "Raphael conversion completed but produced no output WAV."
                )
            self._play_file(converted, spoken)

    def stop(self) -> None:
        self._stop_requested = True
        try:
            self._sink.stop()
        except Exception:
            pass
