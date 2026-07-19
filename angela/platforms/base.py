"""
angela/platforms/base.py
Interface `EngineeringPlatform`.

Angela é a inteligência; a plataforma é a mão que edita arquivos, executa
comandos e roda testes. Trocamos OpenClaude por qualquer outra plataforma
futura implementando apenas esta interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class FileEntry:
    path: str
    is_dir: bool
    size: int = 0


class EngineeringPlatform(ABC):
    """Contrato mínimo que qualquer backend de engenharia deve cumprir."""

    name: str = "base"

    # ── Introspecção ──────────────────────────────────────────────────
    @abstractmethod
    def is_available(self) -> bool:
        """Backend está pronto para receber comandos."""
        ...

    @abstractmethod
    def workspace_root(self) -> str:
        """Caminho do workspace isolado (nunca o projeto principal)."""
        ...

    # ── Leitura ───────────────────────────────────────────────────────
    @abstractmethod
    def list_dir(self, path: str = ".") -> List[FileEntry]:
        ...

    @abstractmethod
    def read_file(self, path: str) -> str:
        """SEMPRE retorna o arquivo inteiro. Angela nunca lê em fatias."""
        ...

    @abstractmethod
    def search(self, pattern: str, path: str = ".",
               case_sensitive: bool = True) -> List[str]:
        """Busca recursiva estilo grep. Retorna 'path:line:match'."""
        ...

    # ── Escrita (só em workspace isolado) ─────────────────────────────
    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        ...

    # ── Execução ──────────────────────────────────────────────────────
    @abstractmethod
    def run(self, command: List[str], cwd: Optional[str] = None,
            timeout: int = 60) -> CommandResult:
        ...

    # ── Testes / patches ──────────────────────────────────────────────
    @abstractmethod
    def run_tests(self) -> CommandResult:
        ...

    @abstractmethod
    def generate_diff(self, path: str) -> str:
        """Diff unificado entre workspace e projeto principal."""
        ...
