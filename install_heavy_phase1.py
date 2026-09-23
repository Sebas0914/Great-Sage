"""Great Sage - modelo de trabajo, FASE 1: instala los archivos nuevos.

Crea (no modifica nada existente):
    great_sage/core/router.py      decide si algo es "simple" (Qwen) o "pesado" (Nemotron)
    great_sage/core/documents.py   convierte Markdown en Word / Excel / PowerPoint reales
    great_sage/core/heavy.py       pide el contenido al modelo pesado y arma el archivo
    heavy_lab.py                   prueba todo desde la terminal, SIN el HUD
    check_router.py                pruebas automaticas (no necesitan Ollama)

No toca server.py, settings.py ni nada de Great Sage: en esta fase el modelo de
trabajo solo se usa desde heavy_lab.py, para ver como escribe Nemotron en tu
maquina antes de conectarlo al HUD.

Uso, desde la raiz del proyecto:
    py install_heavy_phase1.py
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rimse\The-GREAT-SAGE-master"

FILES = [
    ('great_sage/core/router.py', r'''"""Complexity router: who should handle this request?

Great Sage has two models with different jobs:

    simple  -> the voice model (Qwen): conversation, quick answers, and
               anything the tool layer already handles (open an app, the
               time, a web search).
    heavy   -> the work model (Nemotron): writing a document, building a
               spreadsheet or a deck, code, long analysis.

The decision is made by RULES, not by asking a model. Tools.py explains
why: whether a 4B model decides to do something is close to a coin flip,
and the failure is silent. A rule is predictable, instant, and can be
tested (check_router.py). Rules err toward "simple" - a request wrongly
kept simple still gets an answer, while a chat wrongly sent to the heavy
model costs minutes and a loaded 2.8 GB model.

Spanish and English both. Master speaks Spanish; Whisper transcripts
carry accents inconsistently, so everything is matched on accent-stripped
lowercase text.

    classify("hazme un Word sobre energia solar")
    -> Route(level="heavy", kind="docx", reason="crear + documento")
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    level: str            # "simple" | "heavy"
    kind: str = ""        # "docx" | "xlsx" | "pptx" | "general" | "" (simple)
    reason: str = ""

    @property
    def is_heavy(self) -> bool:
        return self.level == "heavy"


SIMPLE = Route("simple", "", "default")


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s).strip()


# ---- what is being asked for -------------------------------------------
# Verbs that MAKE something. "abre word" is not one of these.
_STRONG_VERB = re.compile(
    r"\b(?:crea(?:r|me)?|genera(?:r|me)?|haz(?:me)?|hacer(?:me)?|"
    r"arma(?:r|me)?|prepara(?:r|me)?|elabora(?:r|me)?|"
    r"redacta(?:r|me)?|escribe(?:me)?|escribir(?:me)?|"
    r"disena(?:r|me)?|construye|"
    r"make|create|generate|write|draft|build|prepare|compose)\b")

# "quiero un word...", "dame un Excel": a request. Also what "quiero ver mi
# documento" and "necesito abrir word" look like, so the verb must be
# followed straight away by an ARTICLE and the kind of file (see
# _SOFT_REQUEST, built below once the kind patterns exist).
_SOFT_VERB = r"(?:quiero|necesito|ocupo|dame|damelo|need|want|give me)"

# Opening the application is a job for the tool layer, not for this.
_OPEN_APP = re.compile(
    r"\b(?:abre(?:s|me)?|abrir(?:me)?|lanza(?:r)?|ejecuta(?:r)?|"
    r"open|launch|start)\s+(?:el |la |mi |un |una |the |my )?"
    r"(?:word|excel|powerpoint|power point)\b")

_KIND_XLSX = re.compile(
    r"\b(?:excel|xlsx|hojas? de calculo|planilla|spreadsheet)\b")
_KIND_PPTX = re.compile(
    r"\b(?:powerpoint|power point|pptx|presentacion(?:es)?|diapositivas?|"
    r"slides?|slideshow|deck)\b")
# Nouns that clearly mean "a document"...
_KIND_DOCX_STRONG = re.compile(
    r"\b(?:word|docx|documento|informe|reporte|ensayo|articulo|propuesta|"
    r"report|essay|document|whitepaper)\b")
# ...and nouns that are often just conversation ("dame un resumen"), so
# they only count when a container is named too ("en un archivo").
_KIND_DOCX_WEAK = re.compile(
    r"\b(?:carta|resumen|curriculum|cv|guion|manual|memo|letter|summary|"
    r"texto|poema)\b")
_CONTAINER = re.compile(
    r"\b(?:archivo|fichero|file|documento|word|docx|pdf|en un (?:doc|word))\b")

_KIND_ANY = "(?:" + "|".join(p.pattern for p in (
    _KIND_XLSX, _KIND_PPTX, _KIND_DOCX_STRONG)) + ")"
_SOFT_REQUEST = re.compile(
    r"\b" + _SOFT_VERB + r"\s+(?:un|una|unos|unas|a|an|some)\s+"
    r"(?:\w+\s+){0,2}?" + _KIND_ANY)

# Talking about a file that ALREADY exists ("resume este documento", "mi
# informe de ayer") is not asking for a new one.
_EXISTING = re.compile(
    r"\b(?:este|ese|esta|esa|aquel|del|mi|tu|su|this|that|my|your)\s+"
    r"(?:documento|informe|reporte|articulo|word|excel|presentacion|"
    r"hoja de calculo|planilla|diapositivas?|document|report|article|"
    r"spreadsheet|slides?)\b")

# "redacta" means draft-a-text; by itself it is a request for a document.
_REDACTA = re.compile(r"\bredact(?:a|ar|ame)\b")

# A question ABOUT doing something is not an instruction to do it.
_ASKING = re.compile(
    r"^(?:como|por que|que es|que son|cuando|donde|quien|cual|cuanto|"
    r"what|how|why|when|where|who|which|is |are |does |do you)\b")

# ---- heavy work that is not a document ---------------------------------
_CODE = re.compile(
    r"\b(?:escribe|crea|programa|genera|arma|write|create|implement|build)"
    r"(?:me|r)?\b.{0,40}\b(?:script|codigo|funcion|algoritmo|bot|code|"
    r"function|algorithm|api)\b")
_CODE_PROGRAM = re.compile(
    r"\b(?:crea|escribe|programa|genera|haz|arma)(?:me|r)?\s+(?:un|una)\s+"
    r"programa\s+(?:que|en|para|con)\b")
_ANALYSIS = re.compile(
    r"\b(?:analisis|comparacion|comparativa|investigacion|estrategia|"
    r"plan detallado|analysis|comparison|research|strategy|in[- ]depth|"
    r"detailed plan)\b")
# "analiza X a fondo": the verb itself asks for depth.
_DEEP_IMPERATIVE = re.compile(
    r"\b(?:analiza(?:r|me)?|investiga(?:r)?|compara(?:r|me)?|analyze|"
    r"analyse|compare|research)\b.{0,80}\b(?:a fondo|en detalle|detallad[oa]|"
    r"in depth|in detail|thoroughly)\b")

# A pasted wall of text is work, not chat.
_LONG_INPUT_CHARS = 700


def _kind_of(norm: str):
    """The document kind named in the text, earliest mention winning."""
    found = []
    for kind, pat in (("xlsx", _KIND_XLSX), ("pptx", _KIND_PPTX),
                      ("docx", _KIND_DOCX_STRONG)):
        m = pat.search(norm)
        if m:
            found.append((m.start(), kind))
    return min(found)[1] if found else ""


def _classify_sentence(norm: str) -> Route:
    bare = norm.lstrip("¿¡ ")
    # A leading interjection must not hide the question behind it.
    bare = re.sub(r"^(?:hola|oye|ey|hey|dime|por favor|una pregunta|"
                  r"gran sabio|great sage|sabio)[ ,]+", "", bare)
    if _ASKING.match(bare):
        return Route("simple", "", "pregunta")

    strong = _STRONG_VERB.search(norm) is not None
    soft = (_SOFT_REQUEST.search(norm) is not None
            and _OPEN_APP.search(norm) is None)
    makes = strong or soft
    fresh = _EXISTING.sub(" ", norm)        # without "este documento", "mi informe"
    kind = _kind_of(fresh)

    # Excel / PowerPoint / Word named, and something is being made.
    if kind and makes:
        return Route("heavy", kind, "crear + " + {
            "docx": "documento", "xlsx": "hoja de calculo",
            "pptx": "presentacion"}[kind])

    # Nouns that are usually chat, but not when a file is named too.
    if strong and _KIND_DOCX_WEAK.search(fresh) and _CONTAINER.search(fresh):
        return Route("heavy", "docx", "crear + texto en archivo")

    # "redacta X" on its own: draft it as a document.
    if _REDACTA.search(norm):
        return Route("heavy", "docx", "redactar")

    if _CODE.search(norm) or _CODE_PROGRAM.search(norm):
        return Route("heavy", "general", "codigo")

    if (strong and _ANALYSIS.search(norm)) or _DEEP_IMPERATIVE.search(norm):
        return Route("heavy", "general", "analisis")

    return SIMPLE


def classify(text: str) -> Route:
    """The route for one spoken or typed request. Never raises."""
    if not (text or "").strip():
        return SIMPLE
    # Sentence by sentence: the first one that is an instruction decides.
    for sentence in re.split(r"[.!?¿¡\n]+", text):
        norm = _norm(sentence)
        if not norm:
            continue
        route = _classify_sentence(norm)
        if route.is_heavy:
            return route
    if len(_norm(text)) >= _LONG_INPUT_CHARS:
        return Route("heavy", "general", "texto largo")
    return SIMPLE
'''),
    ('great_sage/core/documents.py', r'''"""Turn Markdown into real Word, Excel and PowerPoint files.

WHY MARKDOWN. The work model only has to WRITE - headings, bullets, a
table - and this module builds the file. That split is the safety
property: the model never produces code that runs, and never receives a
path to write to. It hands over text; text is all this module accepts.
It is also far easier for a 4B model to write Markdown correctly than to
emit strict JSON or drive a document library.

    Markdown  -> .docx   headings, paragraphs, bullets, numbered lists,
                         tables, bold/italic, quotes, code blocks
    Markdown  -> .xlsx   each table becomes a sheet (the heading above it
                         names the sheet); "=B2*C2" cells are formulas
    Markdown  -> .pptx   "# " deck title, each "## " a slide, bullets
                         under it (indent = sub-bullet)

Files are ALWAYS new: save_path() never returns a path that exists, so a
document Master already has can never be overwritten by this module.

Needs: python-docx, openpyxl, python-pptx
    py -m pip install python-docx openpyxl python-pptx
"""

import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

EXTENSIONS = {"docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx"}

# Windows-forbidden characters, and the reserved device names.
_BAD_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul",
             *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


class DocumentError(Exception):
    """The file could not be built (missing library, unusable content)."""


# ---------------------------------------------------------------------
# Where files go
# ---------------------------------------------------------------------

def output_dir(override: Optional[str] = None) -> Path:
    """Documents\\GreatSage under the user's profile, created on demand.

    A folder of its own on purpose: everything Great Sage makes is in one
    place, and nothing it writes can land in (or over) Master's own files.
    """
    base = Path(override) if override else Path.home() / "Documents" / "GreatSage"
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_name(title: str, limit: int = 60) -> str:
    name = _BAD_NAME_CHARS.sub(" ", title or "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    name = name[:limit].strip(" .")
    if not name or name.lower() in _RESERVED:
        name = "documento"
    return name


def save_path(kind: str, title: str, directory: Optional[Path] = None) -> Path:
    """A path in `directory` that does not exist yet. Never overwrites."""
    if kind not in EXTENSIONS:
        raise DocumentError("Tipo de documento desconocido: %r" % kind)
    directory = directory or output_dir()
    stem = safe_name(title)
    candidate = directory / (stem + EXTENSIONS[kind])
    if not candidate.exists():
        return candidate
    stamp = time.strftime("%Y-%m-%d_%H%M")
    candidate = directory / ("%s %s%s" % (stem, stamp, EXTENSIONS[kind]))
    n = 2
    while candidate.exists():
        candidate = directory / ("%s %s (%d)%s"
                                 % (stem, stamp, n, EXTENSIONS[kind]))
        n += 1
    return candidate


# ---------------------------------------------------------------------
# Markdown parsing (shared)
# ---------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+\u2022]\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_RULE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")
_INLINE = re.compile(r"(\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|`[^`\n]+`)")


def _split_row(line: str) -> List[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _clean_inline(text: str) -> str:
    """Text with the Markdown emphasis marks removed (for plain cells)."""
    return _INLINE.sub(lambda m: m.group(0).strip("*_`"), text)


def _blocks(md: str):
    """Yield (type, payload) for each block of the Markdown.

    Types: heading (level, text), bullet (depth, text), numbered
    (depth, text), table (rows), quote (text), code (lines), rule, para.
    """
    lines = (md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i, n = 0, len(lines)
    para: List[str] = []

    def flush():
        if para:
            yield ("para", " ".join(p.strip() for p in para))
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            yield from flush()
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            yield ("code", code)
            continue

        if not stripped:
            yield from flush()
            i += 1
            continue

        if _TABLE_ROW.match(line):
            yield from flush()
            rows = []
            while i < n and _TABLE_ROW.match(lines[i]):
                if not _TABLE_SEP.match(lines[i]):
                    rows.append(_split_row(lines[i]))
                i += 1
            if rows:
                yield ("table", rows)
            continue

        m = _HEADING.match(stripped)
        if m:
            yield from flush()
            yield ("heading", (len(m.group(1)), m.group(2)))
            i += 1
            continue

        if _RULE.match(stripped):
            yield from flush()
            yield ("rule", None)
            i += 1
            continue

        m = _BULLET.match(line)
        if m:
            yield from flush()
            yield ("bullet", (len(m.group(1).expandtabs(2)) // 2, m.group(2)))
            i += 1
            continue

        m = _NUMBERED.match(line)
        if m:
            yield from flush()
            yield ("numbered", (len(m.group(1).expandtabs(2)) // 2, m.group(2)))
            i += 1
            continue

        if stripped.startswith(">"):
            yield from flush()
            yield ("quote", stripped.lstrip("> ").strip())
            i += 1
            continue

        para.append(line)
        i += 1
    yield from flush()


def first_heading(md: str) -> str:
    for kind, payload in _blocks(md):
        if kind == "heading":
            return _clean_inline(payload[1])
    return ""


# ---------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------

def _need(module: str, package: str):
    try:
        return __import__(module)
    except ImportError as exc:
        raise DocumentError(
            "Falta la libreria %s. Instalala con:  py -m pip install %s"
            % (package, package)) from exc


def _add_runs(paragraph, text: str, base_bold: bool = False) -> None:
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith(("**", "__")) and part.endswith(("**", "__")) \
                and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
            run.bold = base_bold or None
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
        else:
            run = paragraph.add_run(part)
            if base_bold:
                run.bold = True


def markdown_to_docx(md: str, path, title: str = "") -> Path:
    _need("docx", "python-docx")
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.core_properties.author = "Great Sage"
    if title:
        doc.core_properties.title = title
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    saw_title = False
    for kind, payload in _blocks(md):
        if kind == "heading":
            level, text = payload
            text = _clean_inline(text)
            if level == 1 and not saw_title:
                doc.add_heading(text, 0)          # the document's Title
                saw_title = True
            else:
                # "##" is a first-level section once a Title exists.
                lvl = level - 1 if saw_title or level > 1 else 1
                doc.add_heading(text, max(1, min(lvl, 4)))
        elif kind == "para":
            _add_runs(doc.add_paragraph(), payload)
        elif kind in ("bullet", "numbered"):
            depth, text = payload
            base = "List Bullet" if kind == "bullet" else "List Number"
            style = base if depth == 0 else "%s %d" % (base, min(depth + 1, 3))
            _add_runs(doc.add_paragraph(style=style), text)
        elif kind == "quote":
            _add_runs(doc.add_paragraph(style="Quote"), payload)
        elif kind == "code":
            for line in payload or [""]:
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.font.name = "Consolas"
                run.font.size = Pt(9.5)
                p.paragraph_format.space_after = Pt(0)
        elif kind == "table":
            _docx_table(doc, payload)
        elif kind == "rule":
            doc.add_paragraph()

    path = Path(path)
    doc.save(str(path))
    return path


def _docx_table(doc, rows: List[List[str]]) -> None:
    width = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    for r, row in enumerate(rows):
        for c in range(width):
            cell = table.cell(r, c)
            cell.text = ""
            text = row[c] if c < len(row) else ""
            _add_runs(cell.paragraphs[0], text, base_bold=(r == 0))
    doc.add_paragraph()


# ---------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_NUMBER_COMMAS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_PERCENT = re.compile(r"^-?\d+(\.\d+)?\s*%$")
_MONEY = re.compile(r"^([$\u20ac\u00a3])\s*(-?\d[\d,]*(\.\d+)?)$")
_SHEET_BAD = re.compile(r"[\[\]:*?/\\]")


def _cell_value(raw: str):
    """(value, number_format). Formulas stay strings starting with '='."""
    text = _clean_inline(raw).strip()
    if text.startswith("="):
        return text, None
    if _NUMBER.match(text):
        return (int(text) if "." not in text else float(text)), None
    if _NUMBER_COMMAS.match(text):
        v = text.replace(",", "")
        return (int(v) if "." not in v else float(v)), "#,##0.##"
    if _PERCENT.match(text):
        return float(text.replace("%", "").strip()) / 100.0, "0.##%"
    m = _MONEY.match(text)
    if m:
        v = m.group(2).replace(",", "")
        return float(v), '"%s"#,##0.00' % m.group(1)
    return text, None


def _sheet_title(name: str, used: set) -> str:
    base = _SHEET_BAD.sub(" ", _clean_inline(name or "")).strip() or "Hoja"
    base = base[:31]
    title, n = base, 2
    while title.lower() in used:
        suffix = " %d" % n
        title = base[:31 - len(suffix)] + suffix
        n += 1
    used.add(title.lower())
    return title


def markdown_to_xlsx(md: str, path, title: str = "") -> Path:
    _need("openpyxl", "openpyxl")
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    sheets: List[Tuple[str, List[List[str]]]] = []
    heading = ""
    loose: List[str] = []
    for kind, payload in _blocks(md):
        if kind == "heading":
            heading = payload[1]
        elif kind == "table":
            sheets.append((heading, payload))
            heading = ""
        elif kind in ("para", "bullet", "numbered", "quote"):
            loose.append(payload if kind in ("para", "quote") else payload[1])

    if not sheets:
        # No table at all: keep the content, one line per row, rather than
        # handing back an empty workbook.
        rows = [[_clean_inline(t)] for t in loose] or [["(vacio)"]]
        sheets.append(("Datos", rows))

    wb = Workbook()
    wb.remove(wb.active)
    used: set = set()
    header_fill = PatternFill("solid", start_color="DDE6F3")

    for index, (name, rows) in enumerate(sheets, 1):
        ws = wb.create_sheet(_sheet_title(name or "Hoja %d" % index, used))
        widths: dict = {}
        for r, row in enumerate(rows, 1):
            for c, raw in enumerate(row, 1):
                value, fmt = _cell_value(raw)
                cell = ws.cell(row=r, column=c, value=value)
                if fmt:
                    cell.number_format = fmt
                if r == 1 and len(rows) > 1:
                    cell.font = Font(bold=True)
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center")
                shown = len(str(value)) if not str(value).startswith("=") else 10
                widths[c] = max(widths.get(c, 0), shown)
        for c, w in widths.items():
            ws.column_dimensions[get_column_letter(c)].width = min(max(w + 3, 10), 60)
        if len(rows) > 1:
            ws.freeze_panes = "A2"

    wb.properties.creator = "Great Sage"
    if title:
        wb.properties.title = title
    path = Path(path)
    wb.save(str(path))
    return path


# ---------------------------------------------------------------------
# PowerPoint
# ---------------------------------------------------------------------

def _slides_from_markdown(md: str):
    """(deck_title, subtitle, [ {title, items:[(depth,text)], notes} ])."""
    deck_title, subtitle = "", ""
    slides: List[dict] = []
    current = None
    for kind, payload in _blocks(md):
        if kind == "heading":
            level, text = payload
            text = _clean_inline(text)
            if level == 1 and not deck_title and not slides:
                deck_title = text
            else:
                current = {"title": text, "items": [], "notes": ""}
                slides.append(current)
        elif current is None:
            # Text before the first slide is the deck's subtitle.
            if kind == "para" and not subtitle:
                subtitle = _clean_inline(payload)
        elif kind in ("bullet", "numbered"):
            current["items"].append((min(payload[0], 2), _clean_inline(payload[1])))
        elif kind == "para":
            text = _clean_inline(payload)
            m = re.match(r"^(?:notas?|notes?)\s*:\s*(.*)$", text, re.I)
            if m:
                current["notes"] = m.group(1)
            else:
                current["items"].append((0, text))
        elif kind == "table":
            for row in payload:
                current["items"].append((0, "  |  ".join(_clean_inline(c) for c in row)))
        elif kind == "quote":
            current["items"].append((0, _clean_inline(payload)))
    if not deck_title and slides:
        deck_title = slides[0]["title"]
    return deck_title, subtitle, slides


def markdown_to_pptx(md: str, path, title: str = "") -> Path:
    _need("pptx", "python-pptx")
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    NAVY = RGBColor(0x1F, 0x38, 0x64)
    ACCENT = RGBColor(0x2E, 0x75, 0xB6)
    INK = RGBColor(0x26, 0x26, 0x26)

    deck_title, subtitle, slides = _slides_from_markdown(md)
    if not slides and not deck_title:
        raise DocumentError("No encontre diapositivas (## Titulo) en el contenido.")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W, H = prs.slide_width, prs.slide_height

    # -- title slide
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = NAVY
    t, sub = s.shapes.title, s.placeholders[1]
    t.left, t.top, t.width, t.height = Inches(0.9), Inches(2.3), W - Inches(1.8), Inches(1.8)
    t.text_frame.text = deck_title or title or "Presentacion"
    t.text_frame.word_wrap = True
    for p in t.text_frame.paragraphs:
        p.alignment = PP_ALIGN.LEFT
        for r in p.runs:
            r.font.size, r.font.bold = Pt(44), True
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    sub.left, sub.top, sub.width, sub.height = Inches(0.9), Inches(4.3), W - Inches(1.8), Inches(1.2)
    sub.text_frame.text = subtitle
    for p in sub.text_frame.paragraphs:
        p.alignment = PP_ALIGN.LEFT
        for r in p.runs:
            r.font.size = Pt(22)
            r.font.color.rgb = RGBColor(0xC9, 0xD6, 0xEA)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(4.15),
                             Inches(1.4), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()

    # -- content slides
    for spec in slides:
        s = prs.slides.add_slide(prs.slide_layouts[1])
        t, body = s.shapes.title, s.placeholders[1]
        t.left, t.top, t.width, t.height = Inches(0.8), Inches(0.45), W - Inches(1.6), Inches(1.1)
        t.text_frame.text = spec["title"]
        t.text_frame.word_wrap = True
        for p in t.text_frame.paragraphs:
            p.alignment = PP_ALIGN.LEFT
            for r in p.runs:
                r.font.size, r.font.bold = Pt(34), True
                r.font.color.rgb = NAVY
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.55),
                                 Inches(1.2), Inches(0.07))
        bar.fill.solid()
        bar.fill.fore_color.rgb = ACCENT
        bar.line.fill.background()

        body.left, body.top = Inches(0.8), Inches(1.95)
        body.width, body.height = W - Inches(1.6), H - Inches(2.6)
        tf = body.text_frame
        tf.word_wrap = True
        items = spec["items"] or [(0, "")]
        longest = max(len(x[1]) for x in items)
        size = 24 if (len(items) <= 5 and longest <= 80) else \
               20 if (len(items) <= 7 and longest <= 110) else 16
        for idx, (depth, text) in enumerate(items):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.text = text
            p.level = depth
            p.space_after = Pt(10)
            for r in p.runs:
                r.font.size = Pt(size - 3 * depth)
                r.font.color.rgb = INK
        if spec["notes"]:
            s.notes_slide.notes_text_frame.text = spec["notes"]

    prs.core_properties.author = "Great Sage"
    prs.core_properties.title = deck_title or title
    path = Path(path)
    prs.save(str(path))
    return path


# ---------------------------------------------------------------------

_BUILDERS = {"docx": markdown_to_docx, "xlsx": markdown_to_xlsx,
             "pptx": markdown_to_pptx}


def build(kind: str, md: str, title: str = "",
          directory: Optional[Path] = None) -> Path:
    """Build the file for `kind` from Markdown and return its new path."""
    if kind not in _BUILDERS:
        raise DocumentError("Tipo de documento desconocido: %r" % kind)
    if not (md or "").strip():
        raise DocumentError("El contenido esta vacio; no hay nada que guardar.")
    heading = first_heading(md)
    name = title or heading or "documento"
    target = save_path(kind, name, directory)
    try:
        return _BUILDERS[kind](md, target, heading or title)
    except DocumentError:
        raise
    except Exception as exc:
        # Never leave a half-written file behind.
        try:
            if target.exists():
                os.remove(target)
        except OSError:
            pass
        raise DocumentError("No pude crear el archivo %s: %s" % (kind, exc)) from exc
'''),
    ('great_sage/core/heavy.py', r'''"""The work model: writes the content, documents.py builds the file.

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
'''),
    ('heavy_lab.py', r'''"""Prueba el modelo de trabajo (Nemotron) SIN tocar Great Sage.

Sirve para ver, antes de integrarlo, tres cosas en TU maquina:
  - que decide el enrutador para una frase
  - cuanto tarda el modelo pesado y como escribe en espanol
  - como queda el archivo que se genera

Ejemplos:
    py heavy_lab.py "hazme un Word sobre las ventajas de la energia solar"
    py heavy_lab.py "crea una hoja de calculo con mis gastos del mes"
    py heavy_lab.py "hazme una presentacion de 6 diapositivas sobre Roma"
    py heavy_lab.py --think "hazme un Word sobre la fotosintesis"
    py heavy_lab.py --route-only "abre Spotify"

Opciones:
    --think        que el modelo razone primero (mejor, pero mas lento)
    --model X      otro modelo de Ollama (por defecto nemotron-3-nano:4b)
    --kind K       fuerza el tipo (docx, xlsx, pptx, general) sin enrutador
    --route-only   solo muestra la decision del enrutador, sin llamar al modelo
    --no-open      no abrir el archivo al terminar

Los archivos se guardan en Documents\\GreatSage (nunca sobrescribe).
"""

import argparse
import os
import sys
import time

from great_sage.core import documents, heavy, router

_CHATTY_STARTS = ("okay", "ok,", "let me", "let's", "we need", "the user",
                  "first,", "hmm", "vale,", "bien,", "necesito", "voy a")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("request", nargs="+", help="lo que le pedirias a Great Sage")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--kind", choices=["docx", "xlsx", "pptx", "general"])
    ap.add_argument("--route-only", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    text = " ".join(args.request)
    route = router.classify(text)
    print("Peticion  :", text)
    print("Enrutador :", "PESADO (%s) - %s" % (route.kind, route.reason)
          if route.is_heavy else "simple - la atenderia Qwen")
    if args.route_only:
        return 0

    kind = args.kind or (route.kind if route.is_heavy else "")
    if not kind:
        print("\nEsto no es trabajo pesado. Para forzarlo: --kind docx|xlsx|pptx|general")
        return 0

    provider = heavy.build_provider()
    if args.model:
        provider.model = args.model
    if args.think:
        provider.think = True
    print("Modelo    :", provider.model, "| razonar:", "si" if provider.think else "no")

    # ¿Esta el modelo descargado?
    try:
        have = provider.get_available_models()
        if provider.model not in have:
            print("\nEl modelo %r no aparece en Ollama. Descargalo con:\n"
                  "    ollama pull %s\nModelos instalados: %s"
                  % (provider.model, provider.model, ", ".join(have) or "(ninguno)"))
            return 1
    except Exception as exc:
        print("\nNo pude hablar con Ollama:", exc)
        return 1

    print("\nTrabajando... (con 4 GB de VRAM puede tardar varios minutos; "
          "no lo cierres)")
    started = time.monotonic()
    try:
        result = heavy.run_job(text, kind, provider=provider,
                               progress=lambda m: print("  ·", m))
    except (heavy.HeavyError, documents.DocumentError) as exc:
        print("\nFALLO tras %.0f s: %s" % (time.monotonic() - started, exc))
        return 1

    print("\n--- Resultado -------------------------------------------")
    print("Tiempo total   : %.0f s" % result.seconds)
    print("Texto generado : %d caracteres" % len(result.text))
    print("Razonamiento   : %d caracteres" % result.thinking_chars)
    head = result.text.lstrip().lower()
    if not result.thinking_chars and head.startswith(_CHATTY_STARTS):
        print("AVISO: la respuesta empieza como razonamiento, no como documento.\n"
              "       El modelo pudo pensar DENTRO de la respuesta. Prueba --think.")
    print("\nVista previa:\n" + "\n".join(result.text.splitlines()[:14]))
    if result.path:
        print("\nArchivo creado:", result.path)
        if not args.no_open:
            try:
                os.startfile(str(result.path))       # solo Windows
            except (AttributeError, OSError):
                print("(abrelo tu mismo desde esa carpeta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''),
    ('check_router.py', r'''"""Pruebas de la fase 1 del modelo de trabajo. No necesitan Ollama.

    py check_router.py

Cubre tres cosas:
  1. El enrutador: que cada frase vaya al modelo correcto (Qwen o Nemotron).
     Igual que check_routing.py, MUST_BE_SIMPLE importa tanto como el
     resto: mandar una charla al modelo pesado cuesta minutos.
  2. El generador de documentos: crea un .docx, .xlsx y .pptx de verdad
     y los vuelve a ABRIR para comprobar el contenido.
  3. El trabajador (heavy.py) con un modelo simulado: limpia etiquetas de
     razonamiento y bloques de codigo, y nunca sobrescribe un archivo.
"""

import os
import sys
import tempfile
from pathlib import Path

from great_sage.core import documents, heavy, router

# (frase, tipo esperado)
MUST_BE_HEAVY = [
    # Word
    ("hazme un Word sobre las ventajas de la energía solar", "docx"),
    ("crea un documento con el plan de trabajo de la semana", "docx"),
    ("redacta una carta para mi jefe pidiendo vacaciones", "docx"),
    ("redacta un informe sobre las ventas del mes", "docx"),
    ("escribe un informe de dos páginas sobre el sistema solar", "docx"),
    ("necesito un documento sobre normas de seguridad", "docx"),
    ("quiero un word con el resumen de la reunión", "docx"),
    ("escribe una carta en un archivo Word para mi casero", "docx"),
    ("¿puedes crear un Word con mi lista de compras?", "docx"),
    ("abre Word y hazme una carta para el banco", "docx"),
    ("write a report about renewable energy", "docx"),
    ("escribe un artículo sobre la energía solar", "docx"),
    ("hazme el informe de ventas", "docx"),
    ("dame un Excel", "xlsx"),
    # Excel
    ("crea una hoja de cálculo con mis gastos del mes", "xlsx"),
    ("hazme un Excel de presupuesto para un viaje", "xlsx"),
    ("genera una planilla con diez productos, precio y cantidad", "xlsx"),
    ("make a spreadsheet of monthly expenses", "xlsx"),
    # PowerPoint
    ("hazme una presentación sobre inteligencia artificial", "pptx"),
    ("crea un PowerPoint de ocho diapositivas sobre Roma", "pptx"),
    ("prepara unas diapositivas para mi clase de historia", "pptx"),
    ("create a slide deck about climate change", "pptx"),
    # Trabajo pesado que no es un documento
    ("escribe un script en python que renombre archivos", "general"),
    ("programa una función que ordene una lista", "general"),
    ("crea un programa que sume dos números", "general"),
    ("haz un análisis detallado de las ventajas y desventajas de Linux",
     "general"),
    ("analiza este código a fondo", "general"),
    ("hola " + "y estas son mis notas de la reunion de hoy " * 20, "general"),
]

MUST_BE_SIMPLE = [
    "hola, ¿cómo estás?",
    "gracias, ya quedó",
    "qué hora es",
    "cuál es la capital de Japón",
    "cuéntame un chiste",
    "pon música relajante",
    # Abrir la aplicacion es cosa de las herramientas, no de este modelo
    "abre Word",
    "abre Excel por favor",
    "necesito abrir Word",
    "abre youtube y busca lofi",
    "busca en internet las noticias de la RTX 5090",
    # Preguntas SOBRE hacer algo no son ordenes
    "¿qué es Excel?",
    "¿cómo hago un Excel con fórmulas?",
    "oye, ¿cómo puedo crear un Word con índice?",
    "qué es una presentación",
    # Sustantivos que suelen ser charla
    "dame un resumen de la película",
    "escribe un poema corto",
    # Hablar de un archivo que YA existe no es pedir uno nuevo
    "quiero ver mi documento",
    "muéstrame mi informe de ayer",
    "hazme un resumen de este artículo",
    "hazme un resumen de este documento",
    "haz un programa de televisión",
    "explícame paso a paso cómo funciona un motor",
]


def check_router():
    fails = []
    for phrase, want in MUST_BE_HEAVY:
        r = router.classify(phrase)
        if not (r.is_heavy and r.kind == want):
            fails.append("%-52s esperaba heavy/%s, obtuvo %s/%s (%s)"
                         % (phrase[:52], want, r.level, r.kind or "-", r.reason))
    for phrase in MUST_BE_SIMPLE:
        r = router.classify(phrase)
        if r.is_heavy:
            fails.append("%-52s debia ser simple, obtuvo heavy/%s (%s)"
                         % (phrase[:52], r.kind, r.reason))
    if router.classify("").is_heavy or router.classify(None).is_heavy:
        fails.append("texto vacio debia ser simple")
    return fails, len(MUST_BE_HEAVY) + len(MUST_BE_SIMPLE) + 1


DOCX_MD = """# Energía solar: ventajas

La energía solar es **renovable** y cada vez más *barata*.

## Ventajas
- Reduce la factura eléctrica
- No emite CO2 al producir
  - Ni ruido ni humo

## Pasos para instalarla
1. Medir el consumo
2. Elegir los paneles

## Comparación
| Fuente | Costo | Emisiones |
|---|---|---|
| Solar | Bajo | Ninguna |
| Carbón | Medio | Altas |

> La mejor energía es la que no se desperdicia.

```
kWh = potencia * horas
```
"""

XLSX_MD = """## Gastos
| Concepto | Precio | Cantidad | Total |
|---|---|---|---|
| Pan | 1.5 | 4 | =B2*C2 |
| Leche | 2 | 3 | =B3*C3 |
| Total |  |  | =SUM(D2:D3) |

## Resumen
| Mes | Ahorro |
|---|---|
| Enero | 15% |
| Febrero | $1,200.50 |
"""

PPTX_MD = """# Inteligencia artificial

Una introducción para principiantes

## Qué es
- Sistemas que aprenden de datos
- No razonan como una persona
  - Detectan patrones

## Usos hoy
- Traducción
- Diagnóstico médico
Notas: mencionar un ejemplo cercano

## Conclusión
- Útil, con límites
"""


def check_documents(tmp: Path):
    fails = []
    try:
        import docx, openpyxl, pptx  # noqa: F401
    except ImportError as exc:
        return ["faltan librerias (%s). Ejecuta: py -m pip install "
                "python-docx openpyxl python-pptx" % exc], 1

    # --- Word
    p = documents.build("docx", DOCX_MD, directory=tmp)
    d = docx.Document(str(p))
    texts = [x.text for x in d.paragraphs]
    styles = [x.style.name for x in d.paragraphs]
    if "Energía solar: ventajas" not in texts or "Title" not in styles:
        fails.append("docx: falta el titulo")
    if not any(t == "Ventajas" for t in texts):
        fails.append("docx: falta la seccion 'Ventajas'")
    if "List Bullet" not in styles or "List Number" not in styles:
        fails.append("docx: faltan las listas")
    if "List Bullet 2" not in styles:
        fails.append("docx: falta la sub-lista")
    if len(d.tables) != 1 or d.tables[0].cell(2, 0).text != "Carbón":
        fails.append("docx: la tabla no quedo bien")
    if not any(r.bold for x in d.paragraphs for r in x.runs):
        fails.append("docx: no hay texto en negrita")

    # --- Excel
    p = documents.build("xlsx", XLSX_MD, directory=tmp)
    wb = openpyxl.load_workbook(str(p))
    if wb.sheetnames != ["Gastos", "Resumen"]:
        fails.append("xlsx: hojas %s" % wb.sheetnames)
    ws = wb["Gastos"]
    if ws["B2"].value != 1.5 or ws["C2"].value != 4:
        fails.append("xlsx: los numeros no son numeros (%r, %r)"
                     % (ws["B2"].value, ws["C2"].value))
    if ws["D2"].value != "=B2*C2" or ws["D4"].value != "=SUM(D2:D3)":
        fails.append("xlsx: las formulas no se conservaron")
    if not ws["A1"].font.bold:
        fails.append("xlsx: la cabecera no esta en negrita")
    r = wb["Resumen"]
    if abs(r["B2"].value - 0.15) > 1e-9 or r["B3"].value != 1200.5:
        fails.append("xlsx: porcentaje/moneda mal (%r, %r)"
                     % (r["B2"].value, r["B3"].value))

    # --- PowerPoint
    p = documents.build("pptx", PPTX_MD, directory=tmp)
    prs = pptx.Presentation(str(p))
    slides = list(prs.slides)
    if len(slides) != 4:
        fails.append("pptx: esperaba 4 diapositivas, hay %d" % len(slides))
    else:
        if slides[0].shapes.title.text_frame.text != "Inteligencia artificial":
            fails.append("pptx: titulo de portada incorrecto")
        if slides[1].shapes.title.text_frame.text != "Qué es":
            fails.append("pptx: titulo de la diapositiva 2 incorrecto")
        body = slides[2].placeholders[1].text_frame.text
        if "Traducción" not in body or "Notas" in body:
            fails.append("pptx: contenido o notas mal repartidos")
        if "ejemplo cercano" not in slides[2].notes_slide.notes_text_frame.text:
            fails.append("pptx: faltan las notas del orador")

    # --- No sobrescribir jamas
    a = documents.save_path("docx", "Mi informe", tmp)
    a.write_text("original")
    b = documents.save_path("docx", "Mi informe", tmp)
    if a == b or not str(b).endswith(".docx"):
        fails.append("save_path devolvio una ruta que ya existe")
    if a.read_text() != "original":
        fails.append("save_path toco un archivo existente")

    # --- Nombres peligrosos
    for bad in ('con', 'a<b>:c"d/e\\f|g?h*', "", "   ...   "):
        name = documents.safe_name(bad)
        if any(ch in name for ch in '<>:"/\\|?*') or not name:
            fails.append("safe_name(%r) -> %r" % (bad, name))
    return fails, 22


class _FakeProvider:
    """Un modelo simulado: devuelve lo que se le diga, como chat_raw."""
    model = "modelo-simulado"

    def __init__(self, content, thinking=""):
        self._msg = {"content": content, "thinking": thinking}
        self.seen = None

    def chat_raw(self, messages, tools=None):
        self.seen = messages
        return self._msg


def check_heavy(tmp: Path):
    fails = []
    try:
        import docx  # noqa: F401
    except ImportError:
        return ["(se omite: falta python-docx)"], 1

    # El modelo se pone a pensar en voz alta, envuelve todo en ``` y saluda.
    noisy = ("<think>Voy a planear el documento...</think>\n"
             "Claro, aqui tienes:\n```markdown\n" + DOCX_MD + "\n```")
    fake = _FakeProvider(noisy, thinking="razonamiento largo " * 10)
    res = heavy.run_job("hazme un Word sobre energia solar", "docx",
                        provider=fake, directory=tmp)
    if res.path is None or not res.path.exists():
        fails.append("run_job no creo el archivo")
    # (el bloque de codigo INTERNO del ejemplo es contenido legitimo y se queda)
    if ("<think>" in res.text or "```markdown" in res.text
            or "Claro" in res.text or not res.text.startswith("# ")):
        fails.append("run_job no limpio la respuesta: %r" % res.text[:80])
    if res.title != "Energía solar: ventajas":
        fails.append("titulo inesperado: %r" % res.title)
    sys_prompt = fake.seen[0]["content"]
    if "SAME LANGUAGE" not in sys_prompt or fake.seen[1]["content"] != \
            "hazme un Word sobre energia solar":
        fails.append("el mensaje al modelo no lleva el idioma/peticion")
    if res.thinking_chars == 0:
        fails.append("no se contabilizo el razonamiento")

    # Saludo + bloque ```markdown cerrado justo despues del contenido.
    res1b = heavy.run_job("x", "docx", directory=tmp, provider=_FakeProvider(
        "Claro:\n```markdown\n# Titulo\n\nTexto.\n```"))
    if res1b.text != "# Titulo\n\nTexto.":
        fails.append("no quito la cerca de codigo envolvente: %r" % res1b.text)
    # Y la cerca de un bloque de codigo INTERNO no se toca.
    if res.text.count("```") != 2:
        fails.append("las cercas del contenido quedaron desbalanceadas (%d)"
                     % res.text.count("```"))

    # El razonamiento sin etiqueta de apertura (solo cierra con </think>)
    res2 = heavy.run_job("x", "docx", directory=tmp,
                         provider=_FakeProvider("pensando...</think>\n# Hola\n\nTexto."))
    if res2.text.split("\n")[0] != "# Hola":
        fails.append("no limpio un </think> huerfano: %r" % res2.text[:40])

    # Sin contenido: error claro, no un archivo vacio.
    try:
        heavy.run_job("x", "docx", provider=_FakeProvider("", "solo pienso"),
                      directory=tmp)
        fails.append("una respuesta vacia debia lanzar HeavyError")
    except heavy.HeavyError:
        pass

    # 'general' devuelve texto y NO crea archivo.
    res3 = heavy.run_job("escribe un script", "general",
                         provider=_FakeProvider("```python\nprint(1)\n```"),
                         directory=tmp)
    if res3.path is not None:
        fails.append("'general' no debia crear archivo")
    if not res3.text.startswith("```python"):
        fails.append("'general' debe CONSERVAR el bloque de codigo: %r" % res3.text)
    return fails, 9


def run():
    failures, total = [], 0
    with tempfile.TemporaryDirectory(prefix="gs-check-") as t:
        tmp = Path(t)
        for name, fn in (("enrutador", lambda: check_router()),
                         ("documentos", lambda: check_documents(tmp)),
                         ("trabajador", lambda: check_heavy(tmp))):
            f, n = fn()
            total += n
            failures += ["[%s] %s" % (name, x) for x in f]
    if failures:
        print("FALLO - %d problema(s)" % len(failures))
        for f in failures:
            print("   " + f)
        return 1
    print("OK - %d comprobaciones (enrutador, documentos, trabajador)" % total)
    return 0


if __name__ == "__main__":
    sys.exit(run())
'''),
]

if not os.path.isdir(os.path.join(ROOT, "great_sage", "core")):
    print("No encuentro great_sage/core en:", ROOT)
    print("Ejecuta este archivo desde la raiz del proyecto.")
    sys.exit(1)

for rel, content in FILES:
    path = os.path.join(ROOT, *rel.split("/"))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", newline="") as f:
            same = f.read() == content
        if same:
            print("  igual, se omite:", rel)
            continue
        backup = path + ".before_heavy"
        if not os.path.exists(backup):
            os.replace(path, backup)
            print("  copia de seguridad:", rel + ".before_heavy")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print("  escrito:", rel)

print()
missing = []
for mod, pkg in (("docx", "python-docx"), ("openpyxl", "openpyxl"), ("pptx", "python-pptx")):
    try:
        __import__(mod)
    except ImportError:
        missing.append(pkg)
if missing:
    print("FALTAN librerias para crear los archivos. Instalalas con:")
    print("    py -m pip install " + " ".join(missing))
else:
    print("Las librerias de Word/Excel/PowerPoint ya estan instaladas.")
print()
print("Siguiente:  py check_router.py")
