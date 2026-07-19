@echo off
title AURA v3 - Instalacao
echo.
echo  ╔══════════════════════════════════════╗
echo  ║     AURA v3 - Instalando...         ║
echo  ╚══════════════════════════════════════╝
echo.
echo  [1/4] Atualizando pip...
python -m pip install --upgrade pip --quiet

echo  [2/4] Instalando dependencias principais...
pip install PyQt6 requests psutil pyautogui Pillow pyperclip pyttsx3 --quiet

echo  [3/4] Verificando instalacao...
python -c "import PyQt6, requests, psutil, pyautogui, pyperclip, pyttsx3; print('  Dependencias OK!')"

echo  [4/4] Checando Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [AVISO] Ollama nao detectado.
    echo  Instale em: https://ollama.com/download
    echo  Depois execute: ollama pull qwen2.5:3b
) else (
    echo  Ollama: OK
)

echo.
echo  ══════════════════════════════════════
echo  Instalacao concluida!
echo  Execute: iniciar.bat
echo  ══════════════════════════════════════
echo.
pause
