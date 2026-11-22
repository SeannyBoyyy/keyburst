# Builds dist\KeyBurst.exe (single file, no console window)
$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --windowed --name KeyBurst --icon assets\icon.ico --add-data "assets\icon.ico;assets" app.py
Get-FileHash dist\KeyBurst.exe -Algorithm SHA256
