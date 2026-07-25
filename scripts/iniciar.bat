@echo off
chcp 65001 >nul
title AURA V12
cd /d "%~dp0.."
echo.
echo  ╔══════════════════════════════════════╗
echo  ║         AURA V12 - Iniciando          ║
echo  ╚══════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado. Instale em python.org
    pause & exit /b 1
)

python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Instalando dependencias...
    call "%~dp0instalar.bat"
)

ollama list >nul 2>&1 || (echo  [INFO] Iniciando Ollama... && start "" /B ollama serve && timeout /t 3 /nobreak >nul)

echo  Iniciando AURA V12...
python AURA.py

if errorlevel 1 (
    echo.
    echo  [ERRO] AURA encerrou com erro. Verifique: pip install -r requirements.txt
    pause
)
