@echo off
REM Double-click this file to remove VoiceType.
cd /d "%~dp0"
title Uninstalling VoiceType
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall
echo.
echo Press any key to close this window.
pause >nul
