import os
import subprocess
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "cpu"
if mode not in ("cpu", "gpu"):
    print("Uso: python test_infer.py cpu|gpu")
    sys.exit(1)

ROOT = r"C:\Users\rimse\The-GREAT-SAGE-master"
APPLIO = os.path.join(ROOT, "third_party", "Applio")
PY = os.path.join(APPLIO, "env", "python.exe")

INPUT = os.path.join(ROOT, "nanami_test.mp3")
OUTPUT = os.path.join(ROOT, f"raphael_{mode}_test.wav")
MODEL = os.path.join(ROOT, "voice_models", "Raphael_200e_3400s.pth")
INDEX = os.path.join(ROOT, "voice_models", "Raphael.index")

env = os.environ.copy()
env.pop("CUDA_VISIBLE_DEVICES", None)
if mode == "cpu":
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


def vram():
    """Devuelve (usada_MiB, total_MiB) de la GPU, o None si nvidia-smi falla."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().splitlines()[0]
        used, total = (int(x) for x in out.split(","))
        return used, total
    except Exception:
        return None


baseline = vram()
print(f"Modo: {mode.upper()}")
if baseline:
    print(f"VRAM antes (Ollama + sistema): {baseline[0]} / {baseline[1]} MiB")
print("Ejecutando Applio...")

peak = baseline[0] if baseline else 0
start = time.time()
proc = subprocess.Popen(command, cwd=APPLIO, env=env)
while proc.poll() is None:
    v = vram()
    if v:
        peak = max(peak, v[0])
    time.sleep(0.5)
elapsed = round(time.time() - start, 1)

print()
print("exit code :", proc.returncode)
print("tiempo    :", elapsed, "s")
if baseline:
    print(f"VRAM pico : {peak} / {baseline[1]} MiB  (RVC anadio ~{peak - baseline[0]} MiB)")
print("salida    :", OUTPUT, "(existe)" if os.path.exists(OUTPUT) else "(NO existe)")
