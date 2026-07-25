@echo off
chcp 65001 >nul
title AURA V12 - Instalacao
cd /d "%~dp0.."
echo.
echo  ╔══════════════════════════════════════╗
echo  ║     AURA V12 - Instalando...          ║
echo  ╚══════════════════════════════════════╝
echo.

echo  [1/3] Atualizando pip...
python -m pip install --upgrade pip --quiet

echo  [2/3] Instalando dependencias (requirements.txt)...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo  [ERRO] Falha ao instalar dependencias. Veja o erro acima.
    pause
    exit /b 1
)

echo  [3/3] Checando Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    ollama --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [AVISO] Ollama nao detectado.
        echo  Instale em: https://ollama.com/download
        echo  Depois execute: ollama pull qwen2.5:3b ^&^& ollama pull qwen3:4b
    ) else (
        echo  Ollama instalado, iniciando servidor...
        start /min ollama serve
        timeout /t 2 >nul
        echo  Puxando modelos recomendados ^(pode demorar na 1a vez^)...
        ollama pull qwen2.5:3b
        ollama pull qwen3:4b
    )
) else (
    echo  Ollama: OK
)

echo.
echo  ══════════════════════════════════════
echo  Instalacao concluida!
echo  Execute: scripts\iniciar.bat
echo  ══════════════════════════════════════
echo.
pause
