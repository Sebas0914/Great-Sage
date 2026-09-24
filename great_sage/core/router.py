"""Complexity router: who should handle this request?

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
    agent: str = "conversation"  # logical specialist
    prefer_online: bool = False  # specialized work uses API first when configured

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
            "pptx": "presentacion"}[kind], "documents", True)

    # Nouns that are usually chat, but not when a file is named too.
    if strong and _KIND_DOCX_WEAK.search(fresh) and _CONTAINER.search(fresh):
        return Route("heavy", "docx", "crear + texto en archivo", "documents", True)

    # "redacta X" on its own: draft it as a document.
    if _REDACTA.search(norm):
        return Route("heavy", "docx", "redactar", "documents", True)

    if _CODE.search(norm) or _CODE_PROGRAM.search(norm):
        return Route("heavy", "coding", "codigo", "coding", True)

    if (strong and _ANALYSIS.search(norm)) or _DEEP_IMPERATIVE.search(norm):
        return Route("heavy", "research", "analisis", "research", True)

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
        return Route("heavy", "research", "texto largo", "research", True)
    return SIMPLE
