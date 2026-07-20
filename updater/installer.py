"""
updater/installer.py
====================
Aplica atualizações com backup e rollback.

NUNCA sobrescreve: config/, models/, database/, profiles/, logs/, cache/,
extensions/, workspace/, themes/, voices/.
"""

import os, sys, shutil, zipfile, json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

from core.logger import setup_logger

logger = setup_logger("updater.installer")

# Pastas/dados que NUNCA são sobrescritos por atualização
PROTECTED_PATHS = {
    "config/", "models/", "database/", "profiles/",
    "logs/", "cache/", "extensions/", "workspace/",
    "themes/", "voices/",
}

PROTECTED_FILES = {
    "config/settings.json", "config/personality.json", "database/aura.db",
}


def _is_protected(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    for p in PROTECTED_PATHS:
        if norm.startswith(p):
            return True
    if norm in PROTECTED_FILES:
        return True
    if norm.startswith("updater/"):
        return True
    return False


def create_backup(root_dir: str, backup_dir: str) -> bool:
    """Cria backup dos arquivos que serão potencialmente alterados."""
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backed_up = 0
        for dirpath, dirnames, filenames in os.walk(root_dir):
            rel_dir = os.path.relpath(dirpath, root_dir)
            if rel_dir == ".":
                rel_dir = ""
            skip = any((rel_dir + "/").startswith(p) for p in PROTECTED_PATHS)
            if skip or ".git" in rel_dir.split(os.sep) or "__pycache__" in rel_dir.split(os.sep):
                continue
            for fname in filenames:
                if fname.endswith((".pyc", ".pyo")):
                    continue
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, root_dir)
                if rel.replace("\\", "/") in PROTECTED_FILES:
                    continue
                dst = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                backed_up += 1
        meta = {"created_at": datetime.now().isoformat(), "root_dir": root_dir, "files_count": backed_up}
        with open(os.path.join(backup_dir, "backup_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        logger.info(f"Backup criado: {backed_up} arquivos em {backup_dir}")
        return True
    except Exception as e:
        logger.error(f"Falha ao criar backup: {e}")
        return False


def apply_zip_update(zip_path: str, root_dir: str, on_progress=None) -> bool:
    """Extrai zip de atualização sobre o projeto, pulando arquivos protegidos."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_files = zf.namelist()
            total = len(all_files)
            extracted = skipped = 0
            for member in all_files:
                if member.endswith("/"):
                    continue
                if _is_protected(member):
                    skipped += 1
                    continue
                dest = os.path.join(root_dir, member)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted += 1
                if on_progress:
                    on_progress(extracted, total)
            logger.info(f"Atualização: {extracted} extraídos, {skipped} protegidos")
            return True
    except zipfile.BadZipFile:
        logger.error(f"ZIP inválido: {zip_path}")
        return False
    except Exception as e:
        logger.error(f"Falha ao aplicar: {e}")
        return False


def rollback(backup_dir: str, root_dir: str) -> bool:
    """Restaura backup para desfazer atualização com falha."""
    try:
        if not os.path.isdir(backup_dir):
            return False
        restored = 0
        for dirpath, _, filenames in os.walk(backup_dir):
            for fname in filenames:
                if fname == "backup_meta.json":
                    continue
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, backup_dir)
                dst = os.path.join(root_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                restored += 1
        logger.info(f"Rollback: {restored} arquivos restaurados")
        return True
    except Exception as e:
        logger.error(f"Falha no rollback: {e}")
        return False


def verify_update_integrity(root_dir: str, modules: List[str]) -> bool:
    """Verifica se os módulos críticos ainda importam após update."""
    sys.path.insert(0, root_dir)
    failed = []
    for mod_name in modules:
        try:
            __import__(mod_name)
        except Exception as e:
            failed.append(f"{mod_name}: {e}")
    if failed:
        logger.error(f"Integridade falhou: {', '.join(failed)}")
        return False
    logger.info(f"Integridade OK: {len(modules)} módulos")
    return True


CRITICAL_MODULES = [
    "core.event_bus", "core.logger", "config.settings",
    "database.db_manager", "ai.ai_provider", "memory.memory_manager",
    "tools.tool_manager",
]
