@echo off
chcp 65001 >nul
title Smart Strategy Engine
cd /d "%~dp0"

echo ============================================
echo    Smart Strategy Engine
echo ============================================
echo.

REM --- Verificar que Python este instalado ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python en esta computadora.
    echo.
    echo Instalalo gratis desde:  https://www.python.org/downloads/
    echo IMPORTANTE: al instalar, marca la casilla "Add Python to PATH".
    echo.
    echo Luego vuelve a abrir este archivo.
    echo.
    pause
    exit /b
)

REM --- Primera vez: crear entorno e instalar librerias ---
if not exist ".venv\Scripts\streamlit.exe" (
    echo Primera vez detectada: instalando lo necesario.
    echo Esto puede tardar unos minutos, ten paciencia...
    echo.
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    echo.
    echo Instalacion terminada.
    echo.
)

echo Abriendo la app en tu navegador (http://localhost:8501)...
echo Para cerrarla: cierra esta ventana negra.
echo.
".venv\Scripts\streamlit.exe" run app.py --server.port 8501
pause
