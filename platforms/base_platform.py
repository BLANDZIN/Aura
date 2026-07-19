"""
platforms/base_platform.py

Abstração de sistema operacional para a AURA (V10 — portabilidade Linux).

Nomeado "platforms/" (plural) e não "platform/" de propósito: um pacote
de topo chamado "platform" sombrearia o módulo `platform` da biblioteca
padrão (usado por platform_manager.py para detectar o SO) para o projeto
inteiro. Mesmo padrão de nome que angela/platforms/ já usa aqui.

Só tem os métodos que o mapeamento real do código encontrou como
genuinamente acoplados a um SO específico (ver FASE1_INVENTARIO_V10.md /
relatório desta fase). Tools de sistema (psutil) e de controle
(pyautogui) já são cross-platform pelas próprias bibliotecas — não
precisam de abstração aqui, e adicionar uma seria complexidade sem
benefício.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BasePlatform(ABC):
    name: str = ""

    @abstractmethod
    def open_folder(self, path: str) -> None:
        """Abre uma pasta no gerenciador de arquivos padrão do SO."""
        ...

    @abstractmethod
    def open_file(self, path: str, args: Optional[List[str]] = None) -> None:
        """Abre um arquivo com o programa padrão associado a ele."""
        ...

    @abstractmethod
    def open_program(self, name_or_path: str, args: Optional[List[str]] = None) -> None:
        """Abre um programa/executável pelo nome ou caminho."""
        ...

    @abstractmethod
    def special_folders(self) -> Dict[str, str]:
        """Mapa nome amigável (pt/en) -> caminho absoluto: desktop, downloads, etc."""
        ...

    @abstractmethod
    def program_aliases(self) -> Dict[str, str]:
        """Mapa nome amigável -> comando/executável conhecido desta plataforma."""
        ...

    @abstractmethod
    def find_program(self, query: str, threshold: float = 0.55) -> Optional[str]:
        """Busca fuzzy por um programa instalado. None se não encontrar nada."""
        ...
