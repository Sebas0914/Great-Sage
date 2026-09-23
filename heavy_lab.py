"""Prueba el modelo de trabajo (Nemotron) SIN tocar Great Sage.

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
