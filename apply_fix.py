import os
import sys

ROOT = r"C:\Users\rimse\The-GREAT-SAGE-master"
PATH = os.path.join(ROOT, "great_sage", "voice", "raphael_rvc_engine.py")

OLD = 'env["CUDA_VISIBLE_DEVICES"] = ""'
NEW = 'env["CUDA_VISIBLE_DEVICES"] = "-1"'

# newline="" conserva los saltos de linea originales (CRLF/LF) sin tocarlos
with open(PATH, "r", encoding="utf-8", newline="") as f:
    content = f.read()

count = content.count(OLD)

if count == 0:
    if NEW in content:
        print("Ya estaba aplicado: el archivo ya usa \"-1\". No se cambio nada.")
    else:
        print("No encontre la linea esperada. No se cambio nada.")
    sys.exit(0)

if count > 1:
    print(f"Encontre {count} coincidencias, esperaba 1. No se cambio nada.")
    sys.exit(1)

with open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(content.replace(OLD, NEW))

print("Listo: cambiada 1 linea en raphael_rvc_engine.py")
print('  antes  :', OLD)
print('  despues:', NEW)
