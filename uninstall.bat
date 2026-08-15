@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Canceling start-on-boot...
py -3 "desktop_pet.py" --uninstall-autostart
echo.
echo Start-on-boot has been disabled.
echo To fully uninstall: quit the pet from the tray icon, then delete this folder.
echo.
pause
