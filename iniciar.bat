@echo off
chcp 65001 >nul
title AURA V11
echo ============================================
echo    AURA V11 - Assistente Virtual
echo ============================================
echo.
cd /d "%~dp0"
REM Tenta Ollama
ollama list >nul 2>&1 || (echo Iniciando Ollama... && start "" /B ollama serve && timeout /t 3 /nobreak >nul)
python AURA.py
if errorlevel 1 (echo ERRO ao iniciar. Verifique: pip install -r requirements.txt && pause)
