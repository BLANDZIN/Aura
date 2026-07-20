"""
AURA — Assistente Virtual Inteligente
Ponto de entrada (legado, delegado para AURA.py).

A partir da V11, use AURA.py como ponto de entrada principal.
Este arquivo existe para compatibilidade com versões anteriores.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from AURA import main
    main()
