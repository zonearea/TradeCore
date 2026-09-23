@echo off
REM TradeCore.exe yeniden derleme (ikon + PyInstaller)
REM Proje kokunden calistirin.

cd /d "%~dp0"
set "PY=%~dp0server\.venv\Scripts\python.exe"
set "PI=%~dp0server\.venv\Scripts\pyinstaller.exe"

"%PY%" tools\create_app_icon.py
"%PI%" --noconfirm --noconsole --onefile --icon=app.ico -n TradeCore --hidden-import=webview --hidden-import=clr --collect-all=webview desktop.py

echo.
echo Cikti: dist\TradeCore.exe
echo Masaustu icin baslat.vbs veya TradeCore.bat kullanin.
pause
