import os
import subprocess
import tempfile

ROOT = r"C:\Users\rimse\The-GREAT-SAGE-master"
APPLIO = os.path.join(ROOT, "third_party", "Applio")
PY = os.path.join(APPLIO, "env", "python.exe")

PROBE = '''
import os, torch
print("  CVD       =", repr(os.environ.get("CUDA_VISIBLE_DEVICES")))
print("  available =", torch.cuda.is_available())
print("  count     =", torch.cuda.device_count())
try:
    print("  name      =", torch.cuda.get_device_name())
except Exception as e:
    print("  name      = ERROR:", type(e).__name__, e)
'''

probe_path = os.path.join(tempfile.gettempdir(), "probe_cuda.py")
with open(probe_path, "w") as f:
    f.write(PROBE)

variants = [
    ("A: sin tocar (como el comando manual)", None),
    ('B: "" (lo que hace ahora Great Sage)', ""),
    ('C: "-1"', "-1"),
]

for label, value in variants:
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    if value is not None:
        env["CUDA_VISIBLE_DEVICES"] = value
    print(label)
    r = subprocess.run(
        [PY, probe_path],
        cwd=APPLIO,
        env=env,
        capture_output=True,
        text=True,
    )
    print(r.stdout or r.stderr)

print("Variables de entorno heredadas:")
for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONIOENCODING"):
    print(" ", k, "=", repr(os.environ.get(k)))
