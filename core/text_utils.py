"""
core/text_utils.py - AURA V11
==============================
Utilitarios de texto compartilhados por ai_engine e decision_engine.
Centralizado para evitar duplicacao (V11).
"""
import re
import unicodedata


def normalize(text: str) -> str:
    """Normaliza texto removendo acentos, pontuacao e espacos extras."""
    n = unicodedata.normalize("NFD", text.lower().strip())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = re.sub(r"[^\w\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()
