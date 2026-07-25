@echo off
chcp 65001 >nul
:: AURA V11 - Auto-start com Windows
:: Copia um atalho para a pasta Startup do usuario
:: Execute uma vez como administrador OU coloque na Startup manualmente

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set AURA_DIR=%~dp0..

:: Cria VBS script para iniciar silenciosamente
echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP%\AURA_Start.vbs"
echo WshShell.Run """%AURA_DIR%\scripts\iniciar.bat""", 0, False >> "%STARTUP%\AURA_Start.vbs"

echo ✓ AURA configurada para iniciar com o Windows
echo   (silenciosamente, sem janela de terminal)
pause
