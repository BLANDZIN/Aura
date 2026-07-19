"""
angela/tools/git_tools.py

Ferramentas de git para a Angela — SEMPRE dentro do workspace isolado
(nunca no projeto principal), construídas sobre o único primitivo que
EngineeringPlatform já expõe para isso: run().

Por que isto não é parte de EngineeringPlatform: git é uma capacidade
de mais alto nível montada sobre "rodar comando". Deixar fora da
interface abstrata mantém a troca de plataforma restrita aos 9
primitivos originais, não a uma dezena de métodos git-específicos.

Se o workspace ainda não for um repositório git, ensure_repo() inicia
um silenciosamente na primeira chamada (baseline commitada).
"""
from typing import List

from angela.platforms.base import EngineeringPlatform, CommandResult


class GitTools:
    def __init__(self, platform: EngineeringPlatform):
        self._p = platform

    # ── infraestrutura ──────────────────────────────────────────────
    def _git(self, *args: str, timeout: int = 30) -> CommandResult:
        return self._p.run(["git", *args], timeout=timeout)

    def is_repo(self) -> bool:
        r = self._git("rev-parse", "--is-inside-work-tree")
        return r.exit_code == 0 and r.stdout.strip() == "true"

    def ensure_repo(self) -> None:
        """Garante que o workspace é um repo git, com um commit baseline."""
        if self.is_repo():
            return
        self._git("init", "-q")
        self._git("config", "user.email", "angela@aura.local")
        self._git("config", "user.name", "Angela (workspace)")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "baseline: snapshot do workspace",
                   "--allow-empty")

    # ── consulta ─────────────────────────────────────────────────────
    def status(self) -> str:
        self.ensure_repo()
        r = self._git("status", "--short")
        return r.stdout.strip() or "(nada modificado desde o último commit)"

    def diff(self, path: str = "") -> str:
        self.ensure_repo()
        args = ["diff"] + ([path] if path else [])
        return self._git(*args).stdout

    def log(self, limit: int = 10) -> List[str]:
        self.ensure_repo()
        r = self._git("log", f"-{limit}", "--oneline")
        return [ln for ln in r.stdout.splitlines() if ln.strip()]

    # ── escrita (só no workspace, nunca no projeto real) ────────────
    def commit(self, message: str) -> CommandResult:
        self.ensure_repo()
        self._git("add", "-A")
        return self._git("commit", "-q", "-m", message, "--allow-empty")

    def restore(self, path: str) -> CommandResult:
        """Descarta modificações não commitadas em um arquivo do workspace."""
        self.ensure_repo()
        return self._git("restore", path)
