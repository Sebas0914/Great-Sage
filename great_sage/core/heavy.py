"""The work model: writes the content, documents.py builds the file.

    request text -> router says "heavy, docx" -> THIS MODULE:
        1. ask the work model (Nemotron) for the content as Markdown
        2. clean what came back (reasoning tags, code fences, chit-chat)
        3. hand the Markdown to documents.py, which builds the real file

The model never sees a path and never runs anything. It returns text.

The work model is a second OllamaProvider - the same class the voice
model uses, pointed at a different model with different settings - so
nothing about the provider seam changes.

Settings (all optional, read with getattr so settings.py needs no edit
to try this out):

    HEAVY_MODEL              "nemotron-3-nano:4b"
    HEAVY_THINK              False   True = the model reasons first: better
                                     on hard tasks, much slower
    HEAVY_TIMEOUT_SECONDS    900     generation runs on a 4 GB GPU + CPU
    HEAVY_KEEP_ALIVE_SECONDS 0       unload right after: the 4 GB card has
                                     to give the memory back to the voice
                                     model
    DOCUMENTS_DIR            None    default: Documents\\GreatSage
"""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from great_sage.core import documents

log = logging.getLogger(__name__)

DEFAULT_MODEL = "nemotron-3-nano:4b"


class HeavyError(Exception):
    """The work model failed or returned nothing usable."""


@dataclass
class JobResult:
    path: Optional[Path]      # the file, or None for kind="general"
    title: str
    kind: str
    text: str                 # the Markdown the model wrote
    seconds: float
    model: str
    thinking_chars: int = 0


# ---------------------------------------------------------------------
# Prompts. English on purpose - small models follow English structure
# instructions more reliably - with the OUTPUT language pinned to the
# request's own.
# ---------------------------------------------------------------------

_COMMON = (
    "Write in the SAME LANGUAGE as the user's request. Output ONLY the "
    "content itself in Markdown: no introduction, no closing remarks, no "
    "'Here is...', and do not wrap the answer in a code fence. Do not "
    "invent facts, names, figures or sources; if something is unknown, "
    "leave a clearly marked placeholder such as [dato pendiente]."
)

PROMPTS = {
    "docx": (
        "You are a professional document writer. Produce a complete, "
        "well-organised Word document.\n"
        "Format: one '# ' title, then '## ' section headings (and '### ' "
        "where needed), normal paragraphs, '- ' bullet lists, '1. ' "
        "numbered lists, and '| a | b |' tables when data is tabular. Use "
        "**bold** sparingly for key terms.\n"
        "Length: as long as the task needs - a letter is short, a report "
        "has several sections with real substance in each.\n" + _COMMON),
    "xlsx": (
        "You are a spreadsheet builder. Produce the data as Markdown "
        "tables; each table becomes one sheet.\n"
        "Format: put a '## ' heading BEFORE each table (it names the "
        "sheet), then the table: a header row, the separator row, then "
        "the data rows. Never put text between rows.\n"
        "Cells: plain numbers only - use a dot for decimals, NO thousands "
        "separators, NO currency symbols or units inside numeric cells "
        "(put them in the header, e.g. 'Precio (USD)'). Where a value is "
        "computed, write a spreadsheet formula starting with '=' using "
        "correct cell references (row 1 is the header row, so the first "
        "data row is row 2), e.g. =B2*C2, and a total row using =SUM(D2:D9) "
        "with the right range.\n" + _COMMON),
    "pptx": (
        "You are a presentation designer. Produce a slide deck.\n"
        "Format: one '# ' line with the deck title, ONE short paragraph "
        "under it as the subtitle, then each slide as a '## ' heading "
        "followed by 3 to 5 short bullets starting with '- ' (maximum "
        "12 words each; indent two spaces for a sub-bullet). No long "
        "paragraphs on slides. Use 6 to 10 slides unless the request "
        "says otherwise: opening, the substance, a closing/summary slide. "
        "Optionally add a line 'Notas: ...' under a slide for what the "
        "speaker should say.\n" + _COMMON),
    "general": (
        "You are a careful expert assistant. Do the task thoroughly and "
        "accurately. Use Markdown headings and lists where they help; put "
        "code in fenced blocks with the language named.\n"
        "Do not invent facts or sources.\n"
        "Write in the SAME LANGUAGE as the user's request."),
}


# ---------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------

def build_provider():
    """The work model's provider, from settings (see module docstring)."""
    from great_sage.config import settings
    from great_sage.models.ollama_provider import OllamaProvider

    provider = OllamaProvider(
        settings.OLLAMA_HOST,
        getattr(settings, "HEAVY_MODEL", DEFAULT_MODEL),
        timeout=getattr(settings, "HEAVY_TIMEOUT_SECONDS", 900),
        think=getattr(settings, "HEAVY_THINK", False),
    )
    # The voice model's keep-alive (2 min) would leave this one resident
    # while the voice model tries to reload into the same 4 GB.
    provider.keep_alive = getattr(settings, "HEAVY_KEEP_ALIVE_SECONDS", 0)
    # Long outputs: leave room for the whole document.
    provider.base_num_ctx = 12288
    return provider


# ---------------------------------------------------------------------
# Cleaning what the model returns
# ---------------------------------------------------------------------

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)
_THINK_OPEN = re.compile(r"^.*?</think>", re.S | re.I)   # opening tag eaten
_OPEN_FENCE = re.compile(r"^\s*```(?:markdown|md)?\s*$", re.I)


def clean_markdown(text: str, unwrap_fences: bool = True) -> str:
    """The model's answer, without what a person would not have written.

    Removes reasoning tags, a code fence wrapped around the WHOLE answer
    ("```markdown ... ```"), and a line or two of chit-chat before it
    ("Claro, aqui tienes:"). unwrap_fences=False keeps fences: a code
    answer ("general") IS a fenced block and unwrapping would destroy it.
    """
    out = (text or "").replace("\r\n", "\n")
    out = _THINK_BLOCK.sub("", out)
    if "</think>" in out.lower():
        out = _THINK_OPEN.sub("", out)
    out = out.strip()

    if unwrap_fences:
        lines = out.split("\n")
        # The opening fence may follow a short greeting.
        for i, line in enumerate(lines[:4]):
            if _OPEN_FENCE.match(line):
                if sum(len(x) for x in lines[:i]) < 200:
                    body = lines[i + 1:]
                    while body and not body[-1].strip():
                        body.pop()
                    if body and body[-1].strip() == "```":
                        body.pop()          # the matching close
                    lines = body
                break
        out = "\n".join(lines).strip()

    # Chit-chat before the first heading ("Claro, aqui tienes...").
    lines = out.split("\n")
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            if 0 < i <= 3 and sum(len(x) for x in lines[:i]) < 200:
                out = "\n".join(lines[i:]).strip()
            break
    return out


# ---------------------------------------------------------------------

def run_job(request: str, kind: str, provider=None,
            directory: Optional[Path] = None,
            progress: Optional[Callable[[str], None]] = None) -> JobResult:
    """Do one heavy request. Blocks until the work model has finished.

    kind: "docx" | "xlsx" | "pptx" | "general". For the first three the
    result carries the new file's path; "general" returns the text only.
    """
    say = progress or (lambda _msg: None)
    if kind not in PROMPTS:
        raise HeavyError("Tipo de trabajo desconocido: %r" % kind)
    provider = provider or build_provider()
    model = getattr(provider, "model", "?")

    messages = [{"role": "system", "content": PROMPTS[kind]},
                {"role": "user", "content": request}]
    say("Consultando a %s..." % model)
    started = time.monotonic()
    try:
        message = provider.chat_raw(messages)
    except Exception as exc:
        raise HeavyError("El modelo de trabajo fallo: %s" % exc) from exc

    raw = message.get("content") or ""
    thinking = message.get("thinking") or ""
    text = clean_markdown(raw, unwrap_fences=(kind != "general"))
    if not text:
        raise HeavyError(
            "El modelo de trabajo no devolvio contenido (%d caracteres de "
            "razonamiento, 0 de respuesta)." % len(thinking))
    log.info("Heavy job (%s, %s): %d chars in %.0fs (thinking %d chars)",
             kind, model, len(text), time.monotonic() - started, len(thinking))

    title = documents.first_heading(text) or request.strip()[:60]
    path = None
    if kind in documents.EXTENSIONS:
        say("Creando el archivo...")
        path = documents.build(kind, text, title=title, directory=directory)
    return JobResult(path=path, title=title, kind=kind, text=text,
                     seconds=time.monotonic() - started, model=model,
                     thinking_chars=len(thinking))
