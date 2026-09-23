@echo off
REM TradeCore Terminal — hizli baslatici
REM Once dist\TradeCore.exe varsa onu (ikonlu, konsolsuz) acar.
REM Yoksa desktop.py'yi pythonw ile sessizce calistirir.

cd /d "%~dp0"

set "EXE=%~dp0dist\TradeCore.exe"
set "VENV_PY=%~dp0server\.venv\Scripts\python.exe"
set "VENV_PYW=%~dp0server\.venv\Scripts\pythonw.exe"

if exist "%EXE%" (
  start "" "%EXE%"
  exit /b 0
)

if exist "%VENV_PYW%" (
  start "" "%VENV_PYW%" "%~dp0desktop.py"
  exit /b 0
)

if exist "%VENV_PY%" (
  "%VENV_PY%" "%~dp0desktop.py"
  exit /b 0
)

echo [TradeCore] Ne exe ne de sanal ortam bulundu.
pause
exit /b 1
