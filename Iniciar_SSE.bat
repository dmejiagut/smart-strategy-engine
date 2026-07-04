@echo off
title Smart Strategy Engine - puerto 8501
cd /d "%~dp0"
echo Iniciando Smart Strategy Engine en http://localhost:8501 ...
".venv\Scripts\streamlit.exe" run app.py --server.port 8501
pause
