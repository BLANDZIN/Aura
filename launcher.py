#!/usr/bin/env python3
"""AURA V12 — Atalho para AURA.py (compatibilidade). Use AURA.py diretamente."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__":
    from AURA import main; main()
