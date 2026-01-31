@echo off
setlocal

REM === Forzar Python local del instrumento ===
set PYTHONHOME=%~dp0python
set PATH=%PYTHONHOME%;%PATH%

REM === Ejecutar OCT ===
venv\Scripts\python.exe main.py

pause

