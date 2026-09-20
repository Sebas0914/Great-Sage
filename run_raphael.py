"""Launch Great Sage with the local Japanese Raphael voice pipeline.

This wrapper exists so the original settings.py/main.py stay untouched while
the Raphael experiment is on its own Git branch. It patches only runtime
settings before loading the normal app entry point.
"""

from __future__ import annotations

import os
import runpy

from great_sage.config import settings

ROOT = os.path.dirname(os.path.abspath(__file__))

# Dedicated Python 3.11 environment for Japanese Piper Plus.
settings.RAPHAEL_PIPER_PYTHON = os.path.join(
    ROOT, ".raphael-venv", "Scripts", "python.exe"
)
settings.RAPHAEL_PIPER_MODEL = "tsukuyomi"

# Official Applio Windows installer creates an env Python 3.12 environment.
settings.RAPHAEL_APPLIO_DIR = os.path.join(ROOT, "third_party", "Applio")
settings.RAPHAEL_APPLIO_PYTHON = os.path.join(
    settings.RAPHAEL_APPLIO_DIR, "env", "python.exe"
)

# Raphael RVC v2 model from Hugging Face.
settings.RAPHAEL_MODEL_PATH = os.path.join(
    ROOT, "voice_models", "Raphael_200e_3400s.pth"
)
settings.RAPHAEL_INDEX_PATH = os.path.join(
    ROOT, "voice_models", "Raphael.index"
)

settings.RAPHAEL_F0_METHOD = "rmvpe"
settings.RAPHAEL_INDEX_RATE = 0.8
settings.RAPHAEL_PROTECT = 0.33
settings.RAPHAEL_EMBEDDER_MODEL = "contentvec"
settings.RAPHAEL_SPEAKER_ID = 0

# Preserve VRAM for Qwen 3.5 4B on the GTX 1650 Ti.
settings.RAPHAEL_RVC_CPU = True

# Make Qwen produce the Japanese text that Piper/RVC will actually speak.
settings.SYSTEM_PROMPT = (
    settings.SYSTEM_PROMPT
    + "\n\nLANGUAGE MODE: Respond entirely in natural, spoken Japanese (日本語). "
      "Use normal Japanese punctuation and write Japanese text, not romaji. "
      "Keep the Great Sage / Raphael persona: calm, analytical, concise, "
      "and composed. Do not explain this language instruction.\n"
)

settings.VOICE_ENGINE = "raphael"

# Run the normal application, including the HUD.
runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
