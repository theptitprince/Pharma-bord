@echo off
cd /d "%~dp0"
python -c "import sv_ttk, openpyxl" 2>nul || pip install -r requirements.txt
start "" pythonw main.py
