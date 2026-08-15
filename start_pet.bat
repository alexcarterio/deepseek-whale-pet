@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=
if exist ".venv\Scripts\pythonw.exe" set PY=.venv\Scripts\pythonw.exe
if "%PY%"=="" (
  for /f "delims=" %%i in ('py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do set PY=%%i
)
if "%PY%"=="" set PY=pythonw
start "" "%PY%" "desktop_pet.py"
