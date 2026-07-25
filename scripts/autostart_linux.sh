#!/usr/bin/env bash
# AURA V11 - Auto-start com Linux
# Cria arquivo .desktop no autostart do usuario

AURA_DIR="$(dirname "$0")/.."
AURA_DIR="$(cd "$AURA_DIR" && pwd)"

mkdir -p ~/.config/autostart

cat > ~/.config/autostart/aura.desktop << DESKTOPEOF
[Desktop Entry]
Type=Application
Name=AURA V11
Comment=Assistente Virtual Inteligente
Exec=$AURA_DIR/scripts/iniciar.sh
Path=$AURA_DIR
Icon=$AURA_DIR/assets/aura.png
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
DESKTOPEOF

echo "✓ AURA configurada para iniciar com o sistema"
echo "  Arquivo: ~/.config/autostart/aura.desktop"
