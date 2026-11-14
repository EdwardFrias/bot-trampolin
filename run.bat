@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .env copy .env.example .env
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
if not exist .venv (
  "%PY%" -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
python bot.py
pause
