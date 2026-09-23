"""Great Sage: entender espanol al pedir acciones ("abre spotify", "busca en youtube ...").

Anade al FINAL de great_sage/core/tools.py un bloque en espanol que amplia el
filtro de herramientas (_TRIGGERS) y el pre-enrutador (_PREROUTE). No edita
nada de lo que ya existe. Es idempotente (si ya esta aplicado, no hace nada),
guarda copia en tools.py.before_spanish y comprueba que el resultado compila
ANTES de escribir.

Uso, desde la raiz del proyecto:
    py apply_spanish_routing.py
    py check_routing_es.py          (y tambien: py check_routing.py)
"""
import os
import shutil
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rimse\The-GREAT-SAGE-master"
PATH = os.path.join(ROOT, "great_sage", "core", "tools.py")
MARKER = "GS_SPANISH_ROUTING"

BLOCK = r'''

# =====================================================================
# GS_SPANISH_ROUTING - Spanish support for the tool gate and the
# pre-router.
#
# WHY THIS EXISTS. Everything above was written and tested in English:
# _TRIGGERS, _PREROUTE and the YouTube verb lists are all English words.
# Master speaks Spanish, so "abre spotify" contained no trigger at all -
# might_need_tools() said False, the tool schema was never attached, and
# the model answered "claro, lo hare" with nothing behind it. Exactly the
# failure described in NOTES.md ("when a tool never fires, check the
# prompt before checking the tool") - only the cause is the LANGUAGE of
# the gate, not the prompt.
#
# HOW. Purely additive. Nothing above is edited: this block extends the
# same module-level names (_TRIGGERS, _PREROUTE, _YT_*) that the existing
# functions already read at call time, the same way every section above
# already does with `_TRIGGERS = _TRIGGERS + (...)`.
#
# Same rule as the English table: narrow on purpose. A tool run on a
# guess is worse than one not run, so questions ABOUT doing something,
# purpose clauses ("para abrir X") and indefinite things ("un ticket")
# are left to the model. Cases live in check_routing_es.py.
# =====================================================================

import unicodedata as _ud


def _es_norm(s):
    """Lowercase, accents removed: 'Descargas', 'ábreme' -> 'descargas', 'abreme'."""
    s = _ud.normalize("NFKD", s or "")
    return "".join(c for c in s if not _ud.combining(c)).lower()


# ---- the gate --------------------------------------------------------
# Accented and unaccented spellings both, because the gate is a plain
# substring test. "hora" alone is NOT here: it is inside "ahora".
_TRIGGERS = _TRIGGERS + (
    "abre", "abrir", "ábreme", "abreme", "lanza", "ejecuta",
    "reproduce", "ponme", "pon ",
    "busca", "buscar", "búscame", "buscame", "encuentra", "investiga",
    "muéstrame", "muestrame", "googlea",
    "qué hora", "que hora", "la hora", "qué día", "que dia", "fecha",
    "carpeta", "archivo", "descargas", "escritorio", "documentos",
    "navegador", "página", "pagina", "programa", "aplicación", "aplicacion",
    "pantalla", "internet", "noticias", "qué ves", "que ves",
    "recuérdame", "recuerdame", "recordatorio", "avísame", "avisame",
)


# ---- YouTube: verbs, leftovers, trailing instructions ----------------
# Without these, "abre youtube" searched YouTube for the word "abre".
_YT_VERBS = ("busca en", "buscar en", "búscame en", "buscame en",
             "búscame", "buscame", "busca", "buscar", "reproduce",
             "reproducir", "ponme", "pon", "ábreme", "abreme", "abre",
             "abrir", "encuentra") + _YT_VERBS
_YT_LEAD = _YT_LEAD + ("para mí", "para mi", "el video", "el vídeo",
                       "un video", "un vídeo", "y", "por favor", "porfa")
_YT_TRAIL = _YT_TRAIL + ("en", "y", "el", "la", "un", "una", "vídeo",
                         "por favor", "porfa")
_YT_NOT_A_REQUEST = _YT_NOT_A_REQUEST + (
    "youtube está caído", "youtube esta caido", "qué es youtube",
    "que es youtube", "quién es dueño de youtube", "cómo funciona youtube",
    "como funciona youtube")
_YT_TAIL_CLAUSE = _re.compile(
    _YT_TAIL_CLAUSE.pattern + r"|"
    r"\s+(?:y|luego|despu[eé]s|tambi[eé]n|por\s+favor|porfa)\s+"
    r"(?:(?:le\s+)?da(?:le)?\s+(?:clic|click)|haz(?:le)?\s+(?:clic|click)|"
    r"reproduce|abre|pon|selecciona|elige|presiona|pulsa)\b",
    _re.I)
_YT_FIRST = _re.compile(
    _YT_FIRST.pattern + r"|"
    r"\bprimer[oa]?\s+(?:video|v[ií]deo|resultado|enlace|link|opci[oó]n)\b|"
    r"\b(?:haz(?:le)?\s+(?:clic|click)|reproduce|abre|elige|selecciona)\b"
    r"[^.]{0,24}\bprimero\b",
    _re.I)


# ---- opening things --------------------------------------------------
_ES_OPEN_VERB = (r"(?:[aá]bre(?:s|me)?|abrir(?:me)?|lanza(?:r)?(?:me)?|"
                 r"ejecuta(?:r)?(?:me)?)")

_ES_OPEN = _re.compile(
    r"\b" + _ES_OPEN_VERB + r"\b\s+(?:me\s+)?(?:por\s+favor\s+)?"
    r"(?:(?:el|la|los|las|mi|mis|tu)\s+)?"
    r"(?P<t>(?:[^\n,.;:!?¿¡]|\.(?=\w)){2,60})",
    _re.I)

# Questions ABOUT doing something are not instructions to do it.
# "puedes abrir..." is deliberately NOT here: that is a request.
_ES_ASKING = ("como ", "por que", "que ", "cuando", "donde", "quien",
              "cual", "puedo ", "debo ", "deberia ", "hay ")

# The word just before the verb says it is not an order: "para abrir X"
# (purpose), "gracias por abrir" (thanks), "lo que busca" (relative).
_ES_NOT_AN_ORDER_BEFORE = frozenset(
    ("para", "por", "de", "al", "sin", "como", "que", "gracias"))

# Nothing nameable follows: "gracias por abrir eso".
_ES_EMPTY_OBJECTS = frozenset(
    ("eso", "esto", "ese", "esa", "algo", "lo", "ello", "todo", "nada"))

# Spoken names for "the browser". open_application("navegador") can match
# nothing on a machine where the browser is not called that.
_ES_BROWSER_WORDS = frozenset(("navegador", "el navegador", "internet",
                               "el internet", "el explorador"))

# A file name is not a website: "notas.txt" has a dot and no spaces, which
# is what the domain test below looks for. Left to the model instead.
_ES_FILE_EXTS = frozenset(("txt", "pdf", "doc", "docx", "xls", "xlsx", "ppt",
                           "pptx", "png", "jpg", "jpeg", "gif", "mp3", "mp4",
                           "wav", "zip", "rar", "py", "md", "csv", "json",
                           "exe", "log"))

_ES_CUT = _re.compile(
    r"\s+(?:y|e|luego|despu[eé]s|por\s+favor|porfa|gracias|para|que|ahora)\b.*$",
    _re.I)

# The folders on disk keep their ENGLISH names even on a Spanish Windows
# ("Descargas" is only a display name), and open_folder resolves a name
# against the home directory - so the Spanish word maps to the real one.
_ES_FOLDERS = {
    "descargas": "Downloads", "escritorio": "Desktop",
    "documentos": "Documents", "imagenes": "Pictures", "fotos": "Pictures",
    "videos": "Videos", "musica": "Music",
}


def _es_not_an_order(m):
    """True when the matched verb is inside a question, purpose clause, etc."""
    whole = _es_norm((m.string or "").strip()).lstrip("¿¡ ")
    if any(whole.startswith(w) for w in _ES_ASKING):
        return True
    before = _es_norm(m.string[:m.start()]).split()
    return bool(before) and before[-1] in _ES_NOT_AN_ORDER_BEFORE


def _es_open_args(m):
    text = m.string or ""
    low = text.lower()
    if _es_not_an_order(m):
        return None
    # "abre youtube y busca X" belongs to the YouTube route; opening the
    # bare site as well would open it twice.
    if "youtube" in low and _youtube_query(text):
        return None
    t = _ES_CUT.sub("", (m.group("t") or "")).strip().strip("?.!,'\"")
    if len(t) < 2:
        return None
    norm = _es_norm(t)
    if norm in _ES_BROWSER_WORDS:
        return {"__tool": "open_url", "url": "https://www.google.com"}
    # An indefinite thing ("un ticket") is described, not named.
    if norm.startswith(("un ", "una ", "unos ", "unas ", "algun")):
        return None
    if norm in _ES_EMPTY_OBJECTS:
        return None
    if "carpeta" in norm or norm in _ES_FOLDERS:
        for word, real in _ES_FOLDERS.items():
            if word in norm:
                return {"__tool": "open_folder", "path": real}
        import re as _r2
        name = _r2.sub(r"^(?:la\s+)?carpeta(?:\s+de(?:l)?)?\s+", "", t,
                       flags=_r2.I).strip()
        return {"__tool": "open_folder", "path": name or t}
    if "." in norm and " " not in norm:            # a domain, or a file name
        if norm.rsplit(".", 1)[-1] in _ES_FILE_EXTS:
            return None
        return {"__tool": "open_url", "url": t}
    if norm in _KNOWN_SITES:
        return {"__tool": "open_url", "url": _KNOWN_SITES[norm]}
    return {"__tool": "open_application", "name": t}


# ---- searching the web -----------------------------------------------
_ES_SEARCH = _re.compile(
    r"\b(?:busca(?:me)?|b[uú]scame|buscar|investiga|googlea|averigua)\s+"
    r"(?:en\s+(?:la\s+)?(?:web|internet|l[ií]nea)\s+)?"
    r"(?:(?:sobre|acerca\s+de|por)\s+)?"
    r"(?P<q>.{2,200})",
    _re.I)

_ES_LOCAL_NOT_WEB = ("archivo", "carpeta", "descargas", "escritorio",
                     "documentos", "en mi pc", "en mi computadora",
                     "en mi compu", "mi disco", "mi equipo")


def _es_search_args(m):
    text = m.string or ""
    if _es_not_an_order(m):
        return None
    # "busca en youtube X" is the YouTube route's, not a web search.
    if "youtube" in text.lower():
        return None
    q = (m.group("q") or "").strip().strip("?.!,")
    q = _re.sub(r"^(?:en\s+)?google\s+", "", q, flags=_re.I)
    q = _re.sub(r"\s+en\s+google$", "", q, flags=_re.I)
    q = _re.sub(r"\s+(?:por\s+favor|porfa)$", "", q, flags=_re.I).strip()
    if len(q) < 2:
        return None
    norm = _es_norm(q)
    if any(w in norm for w in _ES_LOCAL_NOT_WEB):
        return None
    return {"query": q}


_PREROUTE = _PREROUTE + (
    (_ES_OPEN, "__open_something", lambda m: _es_open_args(m)),
    (_ES_SEARCH, "web_search", lambda m: _es_search_args(m)),
    # "que hora es", "que dia es hoy", "dime la fecha"
    (_re.compile(r"\bqu[eé]\s+(?:hora|d[ií]a|fecha)\b|\bhora\s+es\b|"
                 r"\bla\s+(?:hora|fecha)\b", _re.I),
     "get_time", {}),
    (_re.compile(r"\b(?:mira|revisa|lee|ve)\s+(?:mi\s+|la\s+)?pantalla\b|"
                 r"\bqu[eé]\s+(?:hay\s+en\s+(?:mi\s+)?pantalla|ves)\b",
                 _re.I),
     "look_at_screen", {}),
)


# ---- no duplicates ---------------------------------------------------
# Two patterns can legitimately read the same sentence ("busca en google
# gatos" is understood by the English google pattern AND the Spanish one).
# Running the same tool with the same arguments twice is never wanted.
_preroute_before_spanish = preroute


def preroute(text: str):
    routed = _preroute_before_spanish(text)
    t = text or ""
    # The English google/look-up pattern also fires on Spanish sentences
    # that merely MENTION Google: "abre google chrome" would search the web
    # for "chrome", and "abre google y busca gatos" for "y busca gatos".
    # When the sentence is Spanish, the Spanish reading of the search (or
    # the absence of one) decides.
    es_search = _ES_SEARCH.search(t)
    if es_search is not None:
        sq = _es_search_args(es_search)
        if sq is not None:
            routed = [(n, a) for n, a in routed
                      if n != "web_search" or a == sq]
    elif _ES_OPEN.search(t) is not None:
        routed = [(n, a) for n, a in routed if n != "web_search"]
    seen, out = set(), []
    for name, args in routed:
        key = (name, tuple(sorted((k, str(v)) for k, v in args.items())))
        if key in seen:
            continue
        seen.add(key)
        out.append((name, args))
    return out
'''

if not os.path.isfile(PATH):
    print("No existe:", PATH)
    sys.exit(1)

with open(PATH, "r", encoding="utf-8", newline="") as f:
    content = f.read()

if MARKER in content:
    print("Ya estaba aplicado (%s). No se cambio nada." % MARKER)
    sys.exit(0)

if "_TRIGGERS = _TRIGGERS + (" not in content or "_PREROUTE = (" not in content:
    print("tools.py no tiene la estructura esperada (_TRIGGERS / _PREROUTE).")
    print("No se cambio nada.")
    sys.exit(1)

# Conservar el estilo de saltos de linea del archivo.
block = BLOCK.replace("\r\n", "\n")
if "\r\n" in content:
    block = block.replace("\n", "\r\n")
new_content = content.rstrip("\r\n") + "\n" + block
if "\r\n" in content:
    new_content = content.rstrip("\r\n") + "\r\n" + block

try:
    compile(new_content, PATH, "exec")
except SyntaxError as exc:
    print("El resultado NO compila (%s). No se cambio nada." % exc)
    sys.exit(1)

backup = PATH + ".before_spanish"
if not os.path.exists(backup):
    shutil.copy2(PATH, backup)
    print("Copia de seguridad:", os.path.basename(backup))

with open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(new_content)
print("Listo: bloque en espanol anadido al final de great_sage/core/tools.py")
print("Ahora corre:  py check_routing_es.py")
