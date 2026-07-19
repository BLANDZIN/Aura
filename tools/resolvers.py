"""
tools/resolvers.py
Resolvedores de pasta/programa/site usados pelas ferramentas da AURA.

Desde a Fase V10 (portabilidade Linux), delega toda decisão específica
de SO para platforms/platform_manager.py — este arquivo não sabe mais
se está rodando em Windows ou Linux (SPECIAL_FOLDERS e WINDOWS_PROGRAMS
saíram daqui e viraram platforms/windows_platform.py; o Linux tem seu
equivalente em platforms/linux_platform.py).

KNOWN_SITES e PYAUTOGUI_KEYS continuam aqui: não são específicos de SO
— são universais (URLs e nomes de tecla do pyautogui, que já abstrai o
SO por conta própria).
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from core.logger import setup_logger
from core.fuzzy_search import find_best_folder
from platforms.platform_manager import platform_manager

logger = setup_logger("tools")

HOME = Path.home()
DESKTOP = HOME / "Desktop"

KNOWN_SITES: Dict[str, str] = {
    "google":"https://www.google.com", "google.com":"https://www.google.com",
    "youtube":"https://www.youtube.com", "yt":"https://www.youtube.com",
    "gmail":"https://mail.google.com", "drive":"https://drive.google.com",
    "docs":"https://docs.google.com", "sheets":"https://sheets.google.com",
    "meet":"https://meet.google.com", "calendar":"https://calendar.google.com",
    "github":"https://github.com", "gitlab":"https://gitlab.com",
    "stackoverflow":"https://stackoverflow.com", "so":"https://stackoverflow.com",
    "reddit":"https://www.reddit.com", "twitter":"https://www.twitter.com",
    "x":"https://www.x.com", "facebook":"https://www.facebook.com",
    "instagram":"https://www.instagram.com", "linkedin":"https://www.linkedin.com",
    "whatsapp":"https://web.whatsapp.com", "telegram":"https://web.telegram.org",
    "netflix":"https://www.netflix.com", "amazon":"https://www.amazon.com.br",
    "mercadolivre":"https://www.mercadolivre.com.br",
    "chatgpt":"https://chat.openai.com", "claude":"https://claude.ai",
    "pypi":"https://pypi.org", "npmjs":"https://npmjs.com",
    "xvideos":"https://www.xvideos.com", "pornhub":"https://www.pornhub.com",
}

# Atalhos PyAutoGUI para teclas especiais
PYAUTOGUI_KEYS = {
    "enter":"enter","esc":"escape","escape":"escape","tab":"tab",
    "backspace":"backspace","delete":"delete","del":"delete",
    "up":"up","down":"down","left":"left","right":"right",
    "home":"home","end":"end","pageup":"pageup","pagedown":"pagedown",
    "f1":"f1","f2":"f2","f3":"f3","f4":"f4","f5":"f5",
    "f6":"f6","f7":"f7","f8":"f8","f9":"f9","f10":"f10",
    "f11":"f11","f12":"f12",
    "print screen":"printscreen","prtsc":"printscreen",
    "win":"win","windows":"win","super":"win",
    "ctrl":"ctrl","alt":"alt","shift":"shift","space":"space",
}


def _resolve_folder(caminho: str) -> str:
    """
    Resolve nome de pasta para caminho absoluto de uma pasta EXISTENTE.
    1. Pastas especiais (downloads, desktop, etc.) — da plataforma atual
    2. Caminho absoluto direto
    3. Busca fuzzy por similaridade de nome

    Usado por abrir_pasta — onde a pasta já existe e queremos encontrá-la
    mesmo com erro de digitação. NÃO usar para criar_pasta (ver
    _resolve_new_folder_path abaixo), pois a busca fuzzy aqui pode
    colapsar o caminho para uma pasta-mãe existente e descartar o
    nome da subpasta nova.
    """
    key = caminho.strip().lower().rstrip("/\\")

    special = platform_manager.special_folders()
    if key in special:
        return special[key]

    expanded = os.path.expandvars(os.path.expanduser(caminho))
    if os.path.isdir(expanded):
        return expanded

    fuzzy = find_best_folder(caminho)
    if fuzzy:
        logger.info(f"Fuzzy folder: '{caminho}' → '{fuzzy}'")
        return fuzzy

    return str(HOME / "Desktop" / caminho)


def _resolve_new_folder_path(caminho: str) -> str:
    """
    Resolve o caminho de uma pasta que AINDA NÃO EXISTE e está prestes
    a ser criada (usado por criar_pasta). Diferente de _resolve_folder,
    NUNCA faz busca fuzzy — isso preservaria o nome exato pedido em vez
    de colapsar para uma pasta-mãe parecida que já existe.

    Resolve apenas:
    1. Nome especial como base (ex: "downloads/teste 2" -> pasta real
       de Downloads + "/teste 2")
    2. Caminho absoluto (C:/..., /home/..., expande ~ e %VARS%)
    3. Nome simples sem separador -> cria dentro do Desktop
    """
    caminho = caminho.strip()
    if not caminho:
        return str(HOME / "Desktop")

    if any(c in caminho for c in [":", "\\"]) or caminho.startswith("/"):
        return os.path.expandvars(os.path.expanduser(caminho))

    if "/" in caminho:
        primeira, resto = caminho.split("/", 1)
        key = primeira.strip().lower()
        special = platform_manager.special_folders()
        if key in special:
            return os.path.join(special[key], resto)
        return str(HOME / "Desktop" / caminho)

    return str(HOME / "Desktop" / caminho)


def _resolve_program(nome: str) -> str:
    """
    Busca inteligente de executável/programa, delegando à plataforma
    atual (Windows: mapa de .exe + Program Files; Linux: aliases +
    arquivos .desktop):
    1. Mapa de nomes amigáveis da plataforma
    2. Já é caminho/URI direto
    3. PATH do sistema
    4. Busca fuzzy da plataforma
    5. Retorna o nome original
    """
    key = nome.strip().lower()

    aliases = platform_manager.program_aliases()
    if key in aliases:
        return aliases[key]

    if nome.endswith((".exe", ".desktop")) or ":" in nome:
        return nome

    if shutil.which(nome):
        return nome

    fuzzy = platform_manager.find_program(nome, threshold=0.55)
    if fuzzy:
        logger.info(f"Fuzzy program ({platform_manager.name}): '{nome}' → '{fuzzy}'")
        return fuzzy

    return nome


def _shell_open(target: str, args: List[str] = None) -> None:
    """Abre um arquivo/URI com o programa padrão, via a plataforma atual."""
    platform_manager.open_file(target, args)


def _open_folder_native(caminho: str) -> None:
    """Abre pasta no gerenciador de arquivos, via a plataforma atual."""
    platform_manager.open_folder(os.path.normpath(caminho))
