"""
angela/platforms/openclaude.py

** DESATIVADO DELIBERADAMENTE (Fase 2 — ver AUDITORIA_V9_ETAPA1.md) **

O repositório https://github.com/Gitlawb/openclaude declara no seu
próprio LICENSE:

    "This repository contains code derived from Anthropic's Claude
    Code CLI... This project does not have Anthropic's authorization
    to distribute their proprietary source."

Ou seja: é uma cópia não autorizada do Claude Code (produto proprietário
da Anthropic) redistribuída sem permissão. Por isso este adapter nunca
mais se ativa — `is_available()` retorna sempre False — e
`default_platform()` cai automaticamente no LocalStubPlatform.

O código abaixo foi mantido como referência de estrutura (não é
chamado por ninguém) caso vocês queiram adaptar este adapter para uma
ferramenta legítima no futuro — a interface `EngineeringPlatform`
continua sendo o contrato a seguir, e é exatamente por isso que essa
troca não exige tocar em Angela.

Caminho recomendado para a Etapa 4 (Angela ↔ Qwen3 4B): conectar a
Angela diretamente ao Ollama, ver `angela/llm/backend.py` — reaproveita
o mesmo `OllamaProvider` que `ai/ai_provider.py` já usa para a AURA,
só que com configuração e contexto totalmente separados.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from angela.platforms.base import EngineeringPlatform, CommandResult, FileEntry
from angela.platforms.local_stub import LocalStubPlatform
from core.logger import setup_logger

logger = setup_logger("angela.openclaude")


class OpenClaudePlatform(EngineeringPlatform):
    """
    Wrapper sobre OpenClaude. Enquanto o binário não está presente
    delega no LocalStubPlatform para manter Angela operacional.
    """

    name = "openclaude"

    def __init__(self, project_root: str, workspace_dir: Optional[str] = None,
                 binary: str = "openclaude"):
        self._binary = binary
        self._fallback = LocalStubPlatform(project_root, workspace_dir)
        self._project_root = Path(project_root).resolve()

    # ── introspecção ─────────────────────────────────────────────────
    def is_available(self) -> bool:
        # Desativado deliberadamente — ver docstring do módulo.
        # Não faz mais shutil.which(): mesmo que "openclaude" apareça no
        # PATH de alguém, este adapter não deve voltar a ligar sozinho.
        logger.debug(
            "OpenClaudePlatform desativado (proveniência não autorizada "
            "do binário) — usando LocalStubPlatform."
        )
        return False

    def workspace_root(self) -> str:
        return self._fallback.workspace_root()

    # ── ponto de extensão real ───────────────────────────────────────
    def _invoke_cli(self, args: List[str], timeout: int = 60) -> CommandResult:
        """
        Chame aqui o CLI/API real do OpenClaude.
        Substitua quando for integrar de fato.
        """
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [self._binary, *args],
                cwd=self.workspace_root(),
                capture_output=True, text=True, timeout=timeout,
            )
            return CommandResult(proc.returncode, proc.stdout, proc.stderr,
                                 int((time.monotonic() - start) * 1000))
        except Exception as e:
            logger.warning(f"OpenClaude falhou: {e}. Delegando ao fallback.")
            return CommandResult(-1, "", str(e), 0)

    # ── delegação transparente ao fallback quando OC não está pronto ─
    def list_dir(self, path: str = ".") -> List[FileEntry]:
        return self._fallback.list_dir(path)

    def read_file(self, path: str) -> str:
        return self._fallback.read_file(path)

    def search(self, pattern: str, path: str = ".",
               case_sensitive: bool = True) -> List[str]:
        return self._fallback.search(pattern, path, case_sensitive)

    def write_file(self, path: str, content: str) -> None:
        self._fallback.write_file(path, content)

    def run(self, command: List[str], cwd: Optional[str] = None,
            timeout: int = 60) -> CommandResult:
        return self._fallback.run(command, cwd, timeout)

    def run_tests(self) -> CommandResult:
        return self._fallback.run_tests()

    def generate_diff(self, path: str) -> str:
        return self._fallback.generate_diff(path)
