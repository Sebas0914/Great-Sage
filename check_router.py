"""Pruebas de la fase 1 del modelo de trabajo. No necesitan Ollama.

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
