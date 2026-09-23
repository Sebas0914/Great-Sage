from pathlib import Path

p = Path("great_sage/config/settings.py")
text = p.read_text(encoding="utf-8")

anchor = 'RAPHAEL_TTS_VOICE = "ja-JP-NanamiNeural"'

insert = '''RAPHAEL_TTS_PYTHON = os.path.join(".raphael-venv", "Scripts", "python.exe")
RAPHAEL_APPLIO_DIR = os.path.join("third_party", "Applio")
RAPHAEL_APPLIO_PYTHON = os.path.join("third_party", "Applio", "env", "python.exe")
RAPHAEL_MODEL_PATH = os.path.join("voice_models", "Raphael_200e_3400s.pth")
RAPHAEL_INDEX_PATH = os.path.join("voice_models", "Raphael.index")
RAPHAEL_F0_METHOD = "rmvpe"
RAPHAEL_COMMAND_TIMEOUT_SECONDS = 180
'''

if "RAPHAEL_TTS_PYTHON =" not in text:
    if anchor not in text:
        raise SystemExit("Raphael config anchor not found.")
    text = text.replace(anchor, anchor + "\n" + insert, 1)
    p.write_text(text, encoding="utf-8")
    print("Raphael configuration added.")
else:
    print("Raphael configuration already exists; no changes made.")
