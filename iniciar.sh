#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "════════════════════════════════════════════════════════"
echo "   AURA V11 — Assistente Virtual"
echo "════════════════════════════════════════════════════════"
curl -s http://localhost:11434/api/tags >/dev/null 2>&1 || { echo "Iniciando Ollama..."; ollama serve >/dev/null 2>&1 & sleep 3; }
python3 AURA.py || python AURA.py
