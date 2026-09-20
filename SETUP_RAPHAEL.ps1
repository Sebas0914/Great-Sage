# Great Sage - Raphael local voice setup
# Run this from the Great-Sage repository root in PowerShell.
# This does NOT modify the main Python 3.14 environment.

$ErrorActionPreference = "Stop"

Write-Host "== 1. Creating Raphael/Piper Python 3.11 environment =="
if (-not (Test-Path ".raphael-venv\Scripts\python.exe")) {
    py -3.11 -m venv .raphael-venv
}
.\.raphael-venv\Scripts\python.exe -m pip install --upgrade pip
.\.raphael-venv\Scripts\python.exe -m pip install piper-plus
.\.raphael-venv\Scripts\python.exe -m piper_plus --download-model tsukuyomi

Write-Host "== 2. Downloading Raphael RVC model =="
New-Item -ItemType Directory -Force -Path "voice_models" | Out-Null
Invoke-WebRequest -Uri "https://huggingface.co/zidanaetrna/wisdom-king-raphael/resolve/main/Raphael_200e_3400s.pth?download=true" -OutFile "voice_models\Raphael_200e_3400s.pth"
Invoke-WebRequest -Uri "https://huggingface.co/zidanaetrna/wisdom-king-raphael/resolve/main/Raphael.index?download=true" -OutFile "voice_models\Raphael.index"

Write-Host ""
Write-Host "== 3. Applio =="
Write-Host "Applio is intentionally kept outside the Great Sage Python environment."
Write-Host "If it is not already installed, download Applio 3.6.4 and run run-install.bat"
Write-Host "inside: third_party\Applio"
Write-Host ""
Write-Host "Expected interpreter after installation:"
Write-Host "  third_party\Applio\env\python.exe"
Write-Host ""
Write-Host "After Applio is installed, start Great Sage with:"
Write-Host "  python run_raphael.py"
Write-Host ""
Write-Host "The RVC stage is CPU-only by default to preserve the GTX 1650 Ti VRAM."
