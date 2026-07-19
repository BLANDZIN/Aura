"""
core/fuzzy_search.py — AURA v3
Busca fuzzy para arquivos, pastas e programas.

Resolve o problema de "abobrinha" vs "abobr inha" vs "abobrinha2":
  - Similaridade por sequência (SequenceMatcher)
  - Distância de Levenshtein leve
  - Busca por subcadeia (mais tolerante)
  - Busca por iniciais (ex: "vsc" → "Visual Studio Code")

Não requer nenhuma biblioteca externa — tudo com stdlib Python.
"""

import os
import re
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Tuple, Optional
from core.logger import setup_logger

logger = setup_logger("fuzzy")


def _normalize(s: str) -> str:
    """Remove acentos, espaços extras e coloca em minúsculas."""
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[\s_\-]+", " ", s)
    return s.strip()


def similarity(a: str, b: str) -> float:
    """
    Retorna similaridade entre 0.0 e 1.0.
    Combina SequenceMatcher + bônus de subcadeia + bônus de iniciais.
    """
    na = _normalize(a)
    nb = _normalize(b)

    if na == nb:
        return 1.0

    # Similaridade base
    base = SequenceMatcher(None, na, nb).ratio()

    # Bônus: uma é subcadeia da outra
    if na in nb or nb in na:
        base = max(base, 0.75)

    # Bônus: começa com a query
    if nb.startswith(na) or na.startswith(nb):
        base = max(base, 0.80)

    # Bônus: iniciais coincidem (ex: "vsc" → "visual studio code")
    initials = "".join(w[0] for w in nb.split() if w)
    if na == initials:
        base = max(base, 0.70)

    return base


def find_best_folder(query: str, search_roots: List[str] = None,
                     threshold: float = 0.45) -> Optional[str]:
    """
    Busca a pasta que melhor corresponde ao query.

    Args:
        query:        Nome aproximado da pasta a encontrar.
        search_roots: Lista de diretórios onde buscar. Default: HOME.
        threshold:    Similaridade mínima (0-1) para aceitar.

    Returns:
        Caminho absoluto da melhor pasta encontrada, ou None.
    """
    if not query or not query.strip():
        return None

    home = Path.home()
    if search_roots is None:
        # Busca em locais comuns — sem descer recursivamente fundo
        search_roots = [
            str(home),
            str(home / "Desktop"),
            str(home / "Downloads"),
            str(home / "Documents"),
            str(home / "Pictures"),
            "C:/",
            "D:/",
        ]

    candidates: List[Tuple[float, str]] = []

    for root in search_roots:
        if not os.path.exists(root):
            continue
        try:
            for entry in os.scandir(root):
                if entry.is_dir(follow_symlinks=False):
                    score = similarity(query, entry.name)
                    if score >= threshold:
                        candidates.append((score, entry.path))
            # Um nível mais fundo nos locais principais
            if root in (str(home), str(home / "Desktop")):
                for entry in os.scandir(root):
                    if entry.is_dir(follow_symlinks=False):
                        try:
                            for sub in os.scandir(entry.path):
                                if sub.is_dir(follow_symlinks=False):
                                    score = similarity(query, sub.name)
                                    if score >= threshold:
                                        candidates.append((score, sub.path))
                        except PermissionError:
                            pass
        except PermissionError:
            continue

    if not candidates:
        logger.debug(f"Fuzzy folder: nenhum resultado para '{query}'")
        return None

    # Retorna o de maior score
    best_score, best_path = max(candidates, key=lambda x: x[0])
    logger.info(f"Fuzzy folder: '{query}' → '{best_path}' (score={best_score:.2f})")
    return best_path


def find_best_file(query: str, search_dirs: List[str] = None,
                   extensions: List[str] = None,
                   threshold: float = 0.45) -> Optional[str]:
    """
    Busca o arquivo que melhor corresponde ao query.

    Args:
        query:       Nome aproximado do arquivo.
        search_dirs: Diretórios onde buscar.
        extensions:  Filtro de extensões (ex: ['.pdf', '.docx']).
        threshold:   Similaridade mínima.

    Returns:
        Caminho absoluto do melhor arquivo, ou None.
    """
    home = Path.home()
    if search_dirs is None:
        search_dirs = [
            str(home / "Desktop"),
            str(home / "Downloads"),
            str(home / "Documents"),
        ]

    candidates: List[Tuple[float, str]] = []
    # Remove extensão do query para comparar só o nome
    query_stem = Path(query).stem

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            for entry in os.scandir(d):
                if not entry.is_file():
                    continue
                if extensions and not any(entry.name.lower().endswith(e) for e in extensions):
                    continue
                # Compara nome sem extensão e com extensão
                stem  = Path(entry.name).stem
                score = max(similarity(query_stem, stem),
                            similarity(query,      entry.name))
                if score >= threshold:
                    candidates.append((score, entry.path))
        except PermissionError:
            continue

    if not candidates:
        return None

    best_score, best_path = max(candidates, key=lambda x: x[0])
    logger.info(f"Fuzzy file: '{query}' → '{best_path}' (score={best_score:.2f})")
    return best_path


def find_best_program(query: str, threshold: float = 0.45) -> Optional[str]:
    """
    Busca executável por nome aproximado nas pastas de instalação comuns.
    Retorna caminho ou nome do .exe, ou None se não encontrado.
    """
    import shutil

    # 1. Busca no PATH direto
    exe = query if query.endswith(".exe") else f"{query}.exe"
    if shutil.which(exe):
        return exe
    if shutil.which(query):
        return query

    # 2. Busca fuzzy em pastas de instalação
    search_dirs = [
        os.environ.get("PROGRAMFILES",     "C:/Program Files"),
        os.environ.get("PROGRAMFILES(X86)","C:/Program Files (x86)"),
        os.environ.get("LOCALAPPDATA",     str(Path.home() / "AppData/Local")),
        os.environ.get("APPDATA",          str(Path.home() / "AppData/Roaming")),
        str(Path.home() / "AppData/Local/Programs"),
    ]

    candidates: List[Tuple[float, str]] = []
    query_stem = Path(query).stem

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            for root, dirs, files in os.walk(d):
                # Limita profundidade a 3 níveis para não demorar
                depth = root.replace(d, "").count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                for fname in files:
                    if not fname.lower().endswith(".exe"):
                        continue
                    stem  = Path(fname).stem
                    score = max(similarity(query_stem, stem),
                                similarity(query,      fname))
                    if score >= threshold:
                        candidates.append((score, os.path.join(root, fname)))
        except (PermissionError, OSError):
            continue

    if not candidates:
        return None

    best_score, best_path = max(candidates, key=lambda x: x[0])
    logger.info(f"Fuzzy program: '{query}' → '{best_path}' (score={best_score:.2f})")
    return best_path


def fuzzy_match_list(query: str, items: List[str],
                     threshold: float = 0.45) -> List[Tuple[float, str]]:
    """
    Busca fuzzy em uma lista de strings.
    Retorna lista ordenada de (score, item) acima do threshold.
    """
    results = [(similarity(query, item), item) for item in items]
    results = [(s, i) for s, i in results if s >= threshold]
    return sorted(results, reverse=True)
