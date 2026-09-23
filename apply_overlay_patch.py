"""Great Sage: arrancar solo como overlay (el nucleo transparente) arriba a la izquierda.

Cambia dos archivos, con copia de seguridad (*.before_overlay):
  - run_hud.py         -> al cargar el HUD, pasa solo a modo overlay
  - overlay_window.py  -> el overlay se coloca arriba a la IZQUIERDA (antes: derecha)

No toca el modelo, Applio, el servidor ni la ventana grande (sigue existiendo,
oculta; al cerrar el overlay vuelve a aparecer).

Uso:  .\\.raphael-venv\\Scripts\\python.exe apply_overlay_patch.py
"""
import os
import shutil
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rimse\The-GREAT-SAGE-master"

RUN_HUD_EDITS = [
    (
        "    def _centre_window():\n"
        "        hwnd = api._hwnd()\n",
        "    _overlay_started = [False]\n"
        "\n"
        "    def _centre_window():\n"
        "        hwnd = api._hwnd()\n",
    ),
    (
        "            api.set_resizable(True)\n"
        "        api.fix_host_background()\n",
        "            api.set_resizable(True)\n"
        "        api.fix_host_background()\n"
        "        # Arrancar como el overlay pequeno (solo el nucleo, arriba a la\n"
        "        # izquierda) en vez de la ventana grande. UNA sola vez: `loaded`\n"
        "        # puede dispararse otra vez y volveria a ocultar la ventana si el\n"
        "        # usuario ya cambio a la grande. Desactivar con\n"
        "        # START_IN_OVERLAY = False en settings.py.\n"
        "        if (getattr(settings, \"START_IN_OVERLAY\", True)\n"
        "                and not _overlay_started[0]):\n"
        "            _overlay_started[0] = True\n"
        "            api.set_overlay(True)\n",
    ),
]

OVERLAY_EDITS = [
    (
        "    win.move(area.right() - size - MARGIN + 1, area.top() + MARGIN)",
        "    # Arriba a la IZQUIERDA, a peticion (el nombre de la funcion es historico).\n"
        "    win.move(area.left() + MARGIN, area.top() + MARGIN)",
    ),
]


def patch(path, edits):
    print(f"\n{os.path.basename(path)}")
    if not os.path.isfile(path):
        print("  NO existe:", path)
        return False
    with open(path, "r", encoding="utf-8", newline="") as f:
        content = f.read()
    new_content = content
    changed = False
    for old, new in edits:
        if new in new_content:
            print("  ya aplicado, se omite un cambio")
            continue
        variants = [(old, new)]
        if "\r\n" in new_content:
            variants.append((old.replace("\n", "\r\n"), new.replace("\n", "\r\n")))
        for o, n in variants:
            if new_content.count(o) == 1:
                new_content = new_content.replace(o, n)
                changed = True
                print("  cambio aplicado")
                break
        else:
            print("  NO encontre el bloque esperado. No se modifica este archivo.")
            return False
    if not changed:
        print("  nada que cambiar")
        return True
    # Comprobar que sigue siendo Python valido ANTES de escribir nada.
    try:
        compile(new_content.lstrip("\ufeff"), path, "exec")
    except SyntaxError as exc:
        print("  el resultado NO compila (%s). No se modifica este archivo." % exc)
        return False
    backup = path + ".before_overlay"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print("  copia de seguridad:", os.path.basename(backup))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)
    print("  guardado")
    return True


ok1 = patch(os.path.join(ROOT, "overlay_window.py"), OVERLAY_EDITS)
ok2 = patch(os.path.join(ROOT, "run_hud.py"), RUN_HUD_EDITS)

venv = os.path.join(ROOT, ".overlay-venv", "Scripts", "python.exe")
print()
if os.path.isfile(venv):
    print("OK: existe .overlay-venv (Python 3.11 con PySide6), el overlay puede arrancar.")
else:
    print("AVISO: no existe .overlay-venv. El overlay necesita PySide6; sin el, el")
    print("       overlay se cierra al instante y Great Sage vuelve a mostrar la")
    print("       ventana grande (no se rompe nada, pero no veras el overlay).")

print()
print("RESULTADO:", "todo aplicado" if (ok1 and ok2) else "hubo problemas, revisa los mensajes de arriba")
