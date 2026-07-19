#!/usr/bin/env bash
# AURA v3 — instalar.sh (equivalente Linux de instalar.bat)
set -uo pipefail
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     AURA v3 - Instalando...           ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

echo "  [1/5] Atualizando pip..."
python3 -m pip install --upgrade pip --quiet

echo "  [2/5] Dependências de sistema..."
if command -v apt-get >/dev/null 2>&1; then
    echo "        Detectado apt — pode pedir sua senha (sudo):"
    # python3-tk/python3-dev: exigidos pelo mouseinfo (dependência do
    # pyautogui) no Linux.
    # libxcb-cursor0 e o resto: o Qt6 (>=6.5.0) exige essas libs pra
    # carregar o plugin de plataforma "xcb" -- sem isso o app aborta
    # imediatamente com "Could not load the Qt platform plugin xcb"
    # (erro confirmado testando em Linux Mint/Ubuntu real).
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

echo "  [3/5] Instalando dependências Python..."
pip install --break-system-packages PyQt6 requests psutil pyautogui Pillow pyperclip pyttsx3 --quiet \
    || pip install PyQt6 requests psutil pyautogui Pillow pyperclip pyttsx3 --quiet

echo "  [4/5] Verificando instalação..."
python3 -c "import PyQt6, requests, psutil, pyautogui, pyperclip, pyttsx3; print('  Dependências OK!')"

echo "  [5/5] Checando Ollama..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  Ollama: OK"
else
    echo ""
    echo "  [AVISO] Ollama não detectado."
    echo "  Instale com: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Depois execute: ollama pull qwen2.5:3b && ollama pull qwen3:4b"
fi

echo ""
echo "  ══════════════════════════════════════"
echo "  Instalação concluída!"
echo "  Execute: ./iniciar.sh"
echo "  ══════════════════════════════════════"
echo ""
