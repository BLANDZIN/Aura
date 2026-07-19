@echo off
title AURA v3
echo.
echo  ╔══════════════════════════════════════╗
echo  ║         AURA v3 - Iniciando         ║
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
    call instalar.bat
)

echo  Iniciando AURA v3...
python main.py

if errorlevel 1 (
    echo.
    echo  [ERRO] AURA encerrou com erro. Veja os logs acima.
    pause
)
