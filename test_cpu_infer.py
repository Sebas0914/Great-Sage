import os
import subprocess
import time

ROOT = r"C:\Users\rimse\The-GREAT-SAGE-master"
APPLIO = os.path.join(ROOT, "third_party", "Applio")
PY = os.path.join(APPLIO, "env", "python.exe")

INPUT = os.path.join(ROOT, "nanami_test.mp3")
OUTPUT = os.path.join(ROOT, "raphael_cpu_test.wav")
MODEL = os.path.join(ROOT, "voice_models", "Raphael_200e_3400s.pth")
INDEX = os.path.join(ROOT, "voice_models", "Raphael.index")

env = os.environ.copy()
env["CUDA_VISIBLE_DEVICES"] = "-1"

command = [
    PY,
    os.path.join(APPLIO, "core.py"),
    "infer",
    "--input-path", INPUT,
    "--output-path", OUTPUT,
    "--pth-path", MODEL,
    "--index-path", INDEX,
    "--pitch", "-2",
    "--f0-method", "rmvpe",
    "--index-rate", "0.6",
    "--protect", "0.33",
    "--embedder-model", "contentvec",
    "--sid", "0",
]

print("Ejecutando Applio en modo CPU (CUDA_VISIBLE_DEVICES=-1)...")
start = time.time()
result = subprocess.run(command, cwd=APPLIO, env=env)
elapsed = round(time.time() - start, 1)

print()
print("exit code :", result.returncode)
print("tiempo    :", elapsed, "s")
print("salida    :", OUTPUT, "(existe)" if os.path.exists(OUTPUT) else "(NO existe)")
