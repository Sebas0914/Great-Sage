"""Great Sage hace lo que se le pide EN ESPANOL, o solo habla de ello?

Gemelo en espanol de check_routing.py, con la misma logica: cada frase esta
emparejada con la herramienta que DEBE ejecutarse, y MUST_NOT lista lo que
NO debe ejecutar nada (preguntas sobre hacer algo, cosas indefinidas...).

    py check_routing_es.py

Tambien corre check_routing.py (ingles) al final: el bloque en espanol no
debe romper nada de lo que ya funcionaba.
"""

import sys

from great_sage.core import tools

# (frase, herramienta esperada, texto que debe aparecer en los argumentos;
#  "=x" significa EXACTAMENTE x)
MUST = [
    # --- abrir aplicaciones ---
    ("abre spotify", "open_application", "spotify"),
    ("Abre Spotify, por favor.", "open_application", "=spotify"),
    ("abre spotify por favor", "open_application", "=spotify"),
    ("¿Puedes abrir Discord?", "open_application", "discord"),
    ("ábreme reaper", "open_application", "reaper"),
    ("lanza discord", "open_application", "discord"),
    ("ejecuta la calculadora", "open_application", "=calculadora"),
    ("abre mi editor de video y luego dime la hora", "open_application",
     "=editor de video"),

    # --- sitios ---
    ("abre youtube", "open_url", "youtube.com"),
    ("abre github", "open_url", "github.com"),
    ("Abre YouTube.", "open_url", "youtube.com"),
    ("abre wikipedia.org", "open_url", "wikipedia.org"),
    ("abre el navegador", "open_url", "google.com"),
    ("¿me abres spotify?", "open_application", "spotify"),
    ("abre google", "open_url", "google.com"),
    ("abre google chrome", "open_application", "=google chrome"),

    # --- carpetas (los nombres reales en disco estan en ingles) ---
    ("abre mi carpeta de descargas", "open_folder", "=downloads"),
    ("abre la carpeta de documentos", "open_folder", "=documents"),
    ("abre el escritorio", "open_folder", "=desktop"),
    ("abre la carpeta de fotos", "open_folder", "=pictures"),

    # --- YouTube ---
    ("busca en youtube lofi beats", "open_youtube", "=lofi beats"),
    ("busca en youtube canciones de rimuru y reproduce el primero",
     "open_youtube", "=canciones de rimuru"),
    ("pon bohemian rhapsody en youtube", "open_youtube",
     "=bohemian rhapsody"),
    ("abre youtube y busca lofi", "open_youtube", "=lofi"),
    ("reproduce openings de anime en youtube", "open_youtube",
     "openings de anime"),

    # --- la web ---
    ("busca en internet las noticias de la RTX 5090", "web_search", "5090"),
    ("busca en la web recetas de ramen", "web_search", "=recetas de ramen"),
    ("investiga quién ganó el mundial de 2022", "web_search", "2022"),
    ("busca en google gatos graciosos", "web_search", "=gatos graciosos"),

    # --- esta maquina, ahora mismo ---
    ("qué hora es", "get_time", ""),
    ("¿qué día es hoy?", "get_time", ""),
    ("dime la hora", "get_time", ""),
    ("mira mi pantalla", "look_at_screen", ""),
    ("¿qué ves?", "look_at_screen", ""),
]

# Pedir "el primero" debe poner first=True; una busqueda normal, no.
FIRST_TRUE = [
    "busca en youtube canciones de rimuru y reproduce el primero",
    "busca en youtube lofi beats y abre el primer video",
]
FIRST_FALSE = [
    "busca en youtube lofi beats",
    "pon bohemian rhapsody en youtube",
]

# Frases que se dejan enteras al modelo.
MUST_NOT = [
    "hola, ¿cómo estás?",
    "¿qué opinas del jazz?",
    "¿cómo puedo abrir un PDF?",              # pregunta SOBRE abrir
    "cómo abrir una cuenta de correo",        # idem
    "necesito un programa para abrir archivos zip",   # 'para abrir': finalidad
    "gracias por abrir eso",                  # nada nombrable
    "tengo que abrir un ticket",              # cosa indefinida
    "busca mi archivo notas en descargas",    # es del buscador de archivos
    "busca la carpeta de fotos",              # idem
    "¿youtube está caído ahora?",             # sobre YouTube, no pide nada
    "ahora te cuento algo",                   # 'ahora' no es 'hora'
    "por qué dijiste eso",
    "abre notas.txt",                         # un archivo no es una web
    "inicia sesión en steam",
    "redacta un correo para mi jefe",         # no hay herramienta: va al modelo
]

# Ademas de enrutar, el filtro debe DEJAR pasar estas frases: si no, no se
# adjuntan las herramientas al modelo.
GATE_MUST_PASS = [p for p, _, _ in MUST]


def _args_text(args):
    # Los booleanos (first=True/False) no son texto buscado: fuera.
    return " ".join(str(v) for v in args.values()
                    if not isinstance(v, bool)).lower()


def run():
    failures = []

    for phrase, want_tool, want_arg in MUST:
        if not tools.might_need_tools(phrase):
            failures.append("%-46s el filtro NO deja pasar la frase"
                            % phrase[:46])
        routed = tools.preroute(phrase)
        names = [n for n, _ in routed]
        if want_tool not in names:
            failures.append("%-46s esperaba %s, obtuvo %s"
                            % (phrase[:46], want_tool, names or "nada"))
            continue
        if want_arg:
            args = next(a for n, a in routed if n == want_tool)
            exact = want_arg.startswith("=")
            probe = want_arg[1:] if exact else want_arg
            hit = (_args_text(args) == probe.lower() if exact
                   else probe.lower() in _args_text(args))
            if not hit:
                failures.append("%-46s %s corrio con el argumento "
                                "equivocado (queria %r, obtuvo %s)"
                                % (phrase[:46], want_tool, probe, args))

    # Una frase = una accion: "abre youtube y busca lofi" no debe abrir
    # tambien la portada de youtube.
    multi = tools.preroute("abre youtube y busca lofi")
    if [n for n, _ in multi] != ["open_youtube"]:
        failures.append("%-46s debia ser SOLO open_youtube, obtuvo %s"
                        % ("abre youtube y busca lofi",
                           [n for n, _ in multi]))
    # "abre google chrome" solo abre la app; no busca "chrome" en la web.
    chrome = tools.preroute("abre google chrome")
    if [n for n, _ in chrome] != ["open_application"]:
        failures.append("%-46s debia ser SOLO open_application, obtuvo %s"
                        % ("abre google chrome", [n for n, _ in chrome]))
    gsearch = tools.preroute("abre google y busca gatos")
    if [a for n, a in gsearch if n == "web_search"] != [{"query": "gatos"}]:
        failures.append("%-46s la busqueda debia ser exactamente 'gatos', "
                        "obtuvo %s" % ("abre google y busca gatos", gsearch))
    dup = tools.preroute("busca en google gatos graciosos")
    if len(dup) != 1:
        failures.append("%-46s se ejecuto %d veces, debia ser 1"
                        % ("busca en google gatos graciosos", len(dup)))

    for phrase, want in ([(p, True) for p in FIRST_TRUE]
                         + [(p, False) for p in FIRST_FALSE]):
        routed = tools.preroute(phrase)
        args = next((a for n, a in routed if n == "open_youtube"), None)
        if args is None:
            failures.append("%-46s no enruto a open_youtube" % phrase[:46])
        elif bool(args.get("first")) != want:
            failures.append("%-46s first=%s, queria %s"
                            % (phrase[:46], args.get("first"), want))

    for phrase in MUST_NOT:
        routed = tools.preroute(phrase)
        if routed:
            failures.append("%-46s NO debia enrutar, pero ejecuto %s"
                            % (phrase[:46], [n for n, _ in routed]))

    total = len(MUST) + len(MUST_NOT) + len(FIRST_TRUE) + len(FIRST_FALSE) + 4
    if failures:
        print("FALLO - %d de %d" % (len(failures), total))
        for f in failures:
            print("   " + f)
        return 1
    print("OK - %d casos en espanol (%d deben actuar, %d no)"
          % (total, len(MUST), len(MUST_NOT)))
    return 0


if __name__ == "__main__":
    rc = run()
    # Regresion: el ingles tiene que seguir funcionando igual.
    try:
        import check_routing
        rc_en = check_routing.run()
    except ImportError:
        print("(check_routing.py no esta en esta carpeta; se omite la "
              "regresion en ingles)")
        rc_en = 0
    sys.exit(rc or rc_en)
