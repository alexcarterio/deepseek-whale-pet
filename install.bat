@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Whale Pet (DSH-integrated edition) install
echo ============================================
echo.
echo [1/3] Installing Python dependencies (PySide6 / requests / psutil / pywin32)...
py -3 -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo Dependency install failed. Check your network or Python environment.
  pause
  exit /b 1
)
echo.
echo [2/3] Enabling start-on-boot (includes auto-launching DSH)...
py -3 "desktop_pet.py" --install-autostart
echo.
echo [3/3] Starting the pet...
start "" "%~dp0start_pet.bat"
echo.
echo Installation complete!
echo   - The pet is now set to start on boot
echo   - After boot it will detect and auto-launch DSH Web (127.0.0.1:3080)
echo   - Right-click the pet or tray icon for: balance / DSH status / open DSH Web / voice toggle, etc.
echo.
pause
