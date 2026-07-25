#!/usr/bin/env bash
# AURA V12 — scripts/instalar.sh
# Restaurado na revisão V12.1 (Prioridade 3) — a versão anterior só
# instalava libxcb-cursor0, faltando o resto das libs xcb que o Qt6
# realmente precisa (confirmado rodando num ambiente limpo de verdade
# durante a auditoria V11/V12).
set -uo pipefail
cd "$(dirname "$0")/.."

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     AURA V12 - Instalando...          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

echo "  [1/4] Atualizando pip..."
python3 -m pip install --upgrade pip --quiet

echo "  [2/4] Dependências de sistema..."
if command -v apt-get >/dev/null 2>&1; then
    echo "        Detectado apt — pode pedir sua senha (sudo):"
    # python3-tk/python3-dev: exigidos pelo mouseinfo (dependência do
    # pyautogui) no Linux.
    # libxcb-cursor0 e o resto: o Qt6 (>=6.5.0) exige essas libs pra
    # carregar o plugin de plataforma "xcb" -- sem isso o app aborta
    # imediatamente com "Could not load the Qt platform plugin xcb".
    sudo apt-get install -y \
        python3-tk python3-dev scrot xdg-utils \
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 \
        libxcb-xinerama0 libxkbcommon-x11-0
else
    echo "        [AVISO] Gerenciador de pacotes não é apt — instale manualmente:"
    echo "        python3-tk, python3-dev, scrot, xdg-utils"
    echo "        + libxcb-cursor0 e as libs xcb que o Qt6 precisa (nome varia por distro)"
fi

echo "  [3/4] Instalando dependências Python (requirements.txt)..."
pip install --break-system-packages -r requirements.txt --quiet \
    || pip install -r requirements.txt --quiet

echo "  [4/4] Checando Ollama..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  Ollama: OK"
elif command -v ollama >/dev/null 2>&1; then
    echo "  Ollama instalado mas não está rodando — iniciando..."
    ollama serve >/dev/null 2>&1 &
    sleep 2
    echo "  Puxando modelos recomendados (pode demorar na 1ª vez)..."
    ollama pull qwen2.5:3b
    ollama pull qwen3:4b
else
    echo ""
    echo "  [AVISO] Ollama não detectado."
    echo "  Instale com: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Depois execute: ollama pull qwen2.5:3b && ollama pull qwen3:4b"
fi

echo ""
echo "  ══════════════════════════════════════"
echo "  Instalação concluída!"
echo "  Execute: scripts/iniciar.sh"
echo "  ══════════════════════════════════════"
echo ""
