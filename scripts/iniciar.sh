#!/usr/bin/env bash
# AURA V12 — scripts/iniciar.sh
set -uo pipefail
cd "$(dirname "$0")/.."

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║         AURA V12 - Iniciando          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
    echo "  [ERRO] python3 não encontrado. Instale com o gerenciador de pacotes da sua distro"
    echo "         (ex.: sudo apt install python3 python3-pip)"
    exit 1
fi

if ! python3 -c "import PyQt6" >/dev/null 2>&1; then
    echo "  [INFO] Instalando dependências..."
    bash "$(dirname "$0")/instalar.sh"
fi

if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  [INFO] Iniciando Ollama..."
    ollama serve >/dev/null 2>&1 &
    sleep 3
fi

echo "  Iniciando AURA V12..."
python3 AURA.py
status=$?

if [ $status -ne 0 ]; then
    echo ""
    echo "  [ERRO] AURA encerrou com erro (código $status). Veja os logs acima."
    if [ $status -eq 134 ]; then
        echo "  [DICA] Código 134 + menção a 'xcb platform plugin' nos logs acima ="
        echo "         faltam libs do sistema pro Qt6. Rode scripts/instalar.sh de novo"
        echo "         (ele instala libxcb-cursor0 e as outras libs xcb necessárias)."
    fi
fi

exit $status
