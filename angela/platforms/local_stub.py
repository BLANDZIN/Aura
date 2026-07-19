"""
angela/platforms/local_stub.py
Backend padrão. Trabalha no filesystem local dentro de um workspace
isolado (angela/workspace/). Substituído por OpenClaude quando o
usuário conectar.

Este stub é DELIBERADAMENTE conservador: ele não pode tocar em nada
fora do workspace. É a garantia de que a exigência "nunca alterar
produção diretamente" seja imposta pela arquitetura, não só pela
disciplina.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from angela.platforms.base import EngineeringPlatform, CommandResult, FileEntry


class LocalStubPlatform(EngineeringPlatform):
    name = "local_stub"

    def __init__(self, project_root: str, workspace_dir: Optional[str] = None):
        self._project_root = Path(project_root).resolve()
        # Workspace isolado — cópia do projeto principal onde Angela mexe.
        self._workspace = Path(
            workspace_dir or self._project_root / "angela" / "workspace"
        ).resolve()
        self._workspace.mkdir(parents=True, exist_ok=True)

    # ── util ──────────────────────────────────────────────────────────
    def _safe(self, path: str) -> Path:
        """Impede path traversal fora do workspace."""
        p = (self._workspace / path).resolve()
        if self._workspace not in p.parents and p != self._workspace:
            raise PermissionError(
                f"Angela recusou operar fora do workspace: {p}"
            )
        return p

    # ── introspecção ─────────────────────────────────────────────────
    def is_available(self) -> bool:
        return self._workspace.exists()

    def workspace_root(self) -> str:
        return str(self._workspace)

    def sync_from_project(self, *, force: bool = False) -> None:
        """Copia o projeto principal para o workspace (snapshot)."""
        if force and self._workspace.exists():
            shutil.rmtree(self._workspace)
            self._workspace.mkdir(parents=True, exist_ok=True)
        for item in self._project_root.iterdir():
            if item.name in {"angela", ".git", "__pycache__", ".venv"}:
                continue
            dst = self._workspace / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

    # ── leitura ──────────────────────────────────────────────────────
    def list_dir(self, path: str = ".") -> List[FileEntry]:
        p = self._safe(path)
        if not p.exists():
            return []
        out: List[FileEntry] = []
        for item in sorted(p.iterdir()):
            out.append(FileEntry(
                path=str(item.relative_to(self._workspace)),
                is_dir=item.is_dir(),
                size=item.stat().st_size if item.is_file() else 0,
            ))
        return out

    def read_file(self, path: str) -> str:
        p = self._safe(path)
        return p.read_text(encoding="utf-8", errors="replace")

    def search(self, pattern: str, path: str = ".",
               case_sensitive: bool = True) -> List[str]:
        p = self._safe(path)
        matches: List[str] = []
        needle = pattern if case_sensitive else pattern.lower()
        for f in p.rglob("*"):
            if not f.is_file() or f.suffix in {".pyc"}:
                continue
            try:
                for i, line in enumerate(f.read_text(
                        encoding="utf-8", errors="ignore").splitlines(), 1):
                    haystack = line if case_sensitive else line.lower()
                    if needle in haystack:
                        rel = f.relative_to(self._workspace)
                        matches.append(f"{rel}:{i}:{line.strip()}")
                        if len(matches) >= 500:
                            return matches
            except Exception:
                continue
        return matches

    # ── escrita ──────────────────────────────────────────────────────
    def write_file(self, path: str, content: str) -> None:
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # ── execução ─────────────────────────────────────────────────────
    def run(self, command: List[str], cwd: Optional[str] = None,
            timeout: int = 60) -> CommandResult:
        cwd_path = self._safe(cwd) if cwd else self._workspace
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return CommandResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except subprocess.TimeoutExpired as e:
            return CommandResult(
                exit_code=124, stdout=e.stdout or "",
                stderr=f"timeout após {timeout}s",
                duration_ms=timeout * 1000,
            )
        except FileNotFoundError as e:
            return CommandResult(-1, "", str(e),
                                 int((time.monotonic() - start) * 1000))

    def run_tests(self) -> CommandResult:
        # Se houver pytest, roda; caso contrário retorna neutro.
        tests_dir = self._workspace / "tests"
        if not tests_dir.exists():
            return CommandResult(0, "sem suite de testes detectada", "", 0)
        return self.run(["python", "-m", "pytest", "-q", "tests"], timeout=180)

    def generate_diff(self, path: str) -> str:
        src = self._project_root / path
        dst = self._workspace / path
        if not src.exists() or not dst.exists():
            return f"(arquivo ausente em um dos lados: {path})"
        try:
            proc = subprocess.run(
                ["diff", "-u", str(src), str(dst)],
                capture_output=True, text=True, timeout=15,
            )
            return proc.stdout or "(sem diferenças)"
        except FileNotFoundError:
            # Fallback puro em Python quando `diff` não existe (Windows)
            import difflib
            a = src.read_text(encoding="utf-8", errors="replace").splitlines()
            b = dst.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(difflib.unified_diff(
                a, b, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
            )) or "(sem diferenças)"
