@echo off
REM Pharma Bord, par ETDEL -- https://github.com/theptitprince/Pharma-bord
REM Copyright (C) 2026 ETDEL. Licence GPL-3.0-or-later avec conditions additionnelles
REM (article 7) : voir les fichiers LICENSE et NOTICE.
cd /d "%~dp0"
python -c "import sv_ttk, openpyxl" 2>nul || pip install -r requirements.txt
start "" pythonw main.py
