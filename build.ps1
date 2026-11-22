# Builds dist\KeyBurst.exe (single file, no console window)
$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt pyinstaller
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
python -m PyInstaller --clean --noconfirm --onefile --windowed --name KeyBurst --icon assets\icon.ico --add-data "assets\icon.ico;assets" app.py
if (Test-Path dist\KeyBurst.exe) {
    Get-FileHash dist\KeyBurst.exe -Algorithm SHA256
} else {
    Write-Host "dist\KeyBurst.exe is missing. Windows Security may have removed it: check Protection history."
}
