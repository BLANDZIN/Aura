"""
updater/checker.py
==================
Verifica atualizações comparando versão local com GitHub Releases.

API:
  check_for_updates() → List[UpdateInfo]
  get_latest_release() → dict (dados do release mais recente)
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import requests

from core.logger import setup_logger

logger = setup_logger("updater.checker")

GITHUB_REPO = "BLANDZIN/Aura"
GITHUB_API  = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
USER_AGENT  = "AURA-V11-Updater/1.0"


@dataclass
class UpdateInfo:
    """Informação sobre uma atualização disponível."""
    module_id:   str          # ex: "core", "ui"
    module_name: str          # ex: "Core AURA"
    current_version: str      # ex: "11.0.0"
    latest_version: str       # ex: "11.1.0"
    release_url:  str         # URL do release no GitHub
    download_url: str         # URL do arquivo zip do release
    changelog:    str = ""    # notas da versão
    size_mb:      float = 0.0 # tamanho estimado
    published_at: str = ""    # data de publicação

    @property
    def is_update_available(self) -> bool:
        return _compare_versions(self.latest_version, self.current_version) > 0

    @property
    def is_major_update(self) -> bool:
        """Atualização de versão principal (X.0.0 → Y.0.0)."""
        cur_major = int(self.current_version.split(".")[0])
        new_major = int(self.latest_version.split(".")[0])
        return new_major > cur_major


def _compare_versions(a: str, b: str) -> int:
    """
    Compara versões semânticas.
    Retorna: >0 se a > b, 0 se igual, <0 se a < b.
    """
    try:
        pa = [int(x) for x in a.split(".")]
        pb = [int(x) for x in b.split(".")]
        # Preenche com zeros: "1.0" → [1, 0, 0]
        while len(pa) < 3: pa.append(0)
        while len(pb) < 3: pb.append(0)
        for xa, xb in zip(pa, pb):
            if xa != xb:
                return xa - xb
        return 0
    except (ValueError, IndexError):
        return 0


def _parse_version_from_tag(tag: str) -> Optional[str]:
    """Extrai versão de uma tag: 'v11.0.0' → '11.0.0'."""
    m = re.search(r'(\d+\.\d+\.\d+)', tag)
    return m.group(1) if m else None


def fetch_releases() -> List[Dict]:
    """
    Busca todos os releases do GitHub.
    Retorna lista de dicts com dados do release.
    """
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
        }
        resp = requests.get(GITHUB_API, headers=headers, timeout=15)
        resp.raise_for_status()
        releases = resp.json()
        logger.info(f"Encontrados {len(releases)} releases no GitHub")
        return releases
    except requests.exceptions.ConnectionError:
        logger.warning("Sem conexão com GitHub — verificação offline")
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar releases: {e}")
        return []


def get_latest_release() -> Optional[Dict]:
    """Retorna o release mais recente ou None."""
    releases = fetch_releases()
    if not releases:
        return None
    # GitHub já retorna ordenado por data
    return releases[0]


def check_for_updates(
    local_modules: Optional[Dict[str, Dict]] = None,
) -> List[UpdateInfo]:
    """
    Compara versões locais com as do GitHub.

    Args:
        local_modules: dict com {module_id: {version, name, path}}.
                      Se None, usa o manifesto de updater/__init__.py.

    Returns:
        Lista de UpdateInfo para módulos com atualização disponível.
    """
    if local_modules is None:
        from updater import MODULES as local_modules

    releases = fetch_releases()
    updates: List[UpdateInfo] = []

    # Se não há releases (offline), retorna vazio
    if not releases:
        return updates

    # O release mais recente contém o zip com todos os módulos
    latest = releases[0]
    latest_tag = latest.get("tag_name", "")
    latest_version = _parse_version_from_tag(latest_tag)

    if not latest_version:
        logger.warning(f"Não foi possível extrair versão da tag '{latest_tag}'")
        return updates

    # Pega URL de download (zipball)
    download_url = latest.get("zipball_url", "")
    release_url  = latest.get("html_url", "")
    published_at = latest.get("published_at", "")
    changelog    = latest.get("body", "")

    # Tamanho do zip (aproximado)
    assets = latest.get("assets", [])
    size_mb = 0.0
    if assets:
        size_bytes = assets[0].get("size", 0)
        size_mb = size_bytes / (1024 * 1024)

    # Compara cada módulo local com a versão do release
    for mod_id, mod_info in local_modules.items():
        current = mod_info.get("version", "0.0.0")

        # Se a versão do release é maior que a local
        if _compare_versions(latest_version, current) > 0:
            updates.append(UpdateInfo(
                module_id=mod_id,
                module_name=mod_info.get("name", mod_id),
                current_version=current,
                latest_version=latest_version,
                release_url=release_url,
                download_url=download_url,
                changelog=changelog,
                size_mb=size_mb,
                published_at=published_at,
            ))

    logger.info(
        f"Verificação concluída: {len(updates)} módulo(s) com atualização "
        f"(latest={latest_version})"
    )
    return updates


def check_single_module(module_id: str, local_version: str) -> Optional[UpdateInfo]:
    """Verifica atualização para um módulo específico."""
    modules = {module_id: {"version": local_version, "name": module_id, "path": ""}}
    updates = check_for_updates(local_modules=modules)
    return updates[0] if updates else None
