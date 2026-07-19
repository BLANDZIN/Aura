"""
vision/context_manager.py — AURA v3
Sistema de Consciência de Contexto.

A AURA agora sabe em tempo real:
  - Qual janela está em foco (programa ativo)
  - Quais programas estão abertos
  - Conteúdo do clipboard
  - Hora, data, dia da semana
  - Uso de CPU e RAM
  - Pasta de trabalho atual
  - Últimas ações executadas
  - Arquivos recentes na área de trabalho

Esse contexto é injetado no system prompt a cada mensagem,
dando à IA consciência do que está acontecendo no computador.
"""

import os
import sys
import time
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.logger import setup_logger

logger = setup_logger("context")


class ContextManager:
    """
    Coleta e mantém o contexto atual do ambiente do usuário.
    Atualiza em background a cada N segundos.
    """

    def __init__(self, update_interval: float = 12.0):
        # Intervalo aumentado de 5s para 12s: o contexto não precisa ser
        # atualizado tão frequentemente, e psutil.process_iter() varrendo
        # TODOS os processos do sistema a cada 5s competia por CPU com
        # o modelo de IA rodando local (Ollama), tornando as respostas
        # mais lentas. _get_open_programs() agora roda a cada 2 ciclos
        # (24s) — é o dado mais caro de coletar e o que menos muda
        # segundo a segundo.
        self._interval  = update_interval
        self._lock      = threading.Lock()
        self._running   = False
        self._thread    = None
        self._ctx: Dict[str, Any] = {}
        self._action_history: List[Dict] = []  # últimas ações executadas
        self._cycle_count = 0

        # Coleta inicial imediata
        self._collect(full=True)
        logger.info("ContextManager iniciado")

    # ── API pública ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Inicia coleta periódica em background."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def get(self) -> Dict[str, Any]:
        """Retorna snapshot atual do contexto."""
        with self._lock:
            return dict(self._ctx)

    def register_action(self, acao: str, resultado: str, sucesso: bool) -> None:
        """Registra ação executada para incluir no contexto."""
        self._action_history.append({
            "acao":      acao,
            "resultado": resultado,
            "sucesso":   sucesso,
            "ts":        datetime.now().strftime("%H:%M:%S"),
        })
        # Mantém só as últimas 5
        self._action_history = self._action_history[-5:]

    def build_context_string(self) -> str:
        """
        Gera string de contexto para incluir no system prompt.
        Formato compacto para não inflar o prompt desnecessariamente.
        """
        ctx = self.get()
        if not ctx:
            return ""

        lines = ["CONTEXTO ATUAL DO COMPUTADOR:"]

        # Data e hora
        lines.append(f"- Data/hora: {ctx.get('datetime', '')}")

        # Janela ativa
        if ctx.get("active_window"):
            lines.append(f"- Janela ativa: {ctx['active_window']}")

        # Programas abertos (top 8)
        progs = ctx.get("open_programs", [])
        if progs:
            lines.append(f"- Programas abertos: {', '.join(progs[:8])}")

        # CPU e RAM
        cpu = ctx.get("cpu_percent")
        ram = ctx.get("ram_percent")
        if cpu is not None:
            lines.append(f"- Recursos: CPU {cpu}% | RAM {ram}%")

        # Clipboard
        clip = ctx.get("clipboard", "")
        if clip and len(clip.strip()) > 0:
            clip_preview = clip.strip()[:80].replace("\n", " ")
            lines.append(f"- Clipboard: \"{clip_preview}\"")

        # Pasta de trabalho
        cwd = ctx.get("cwd", "")
        if cwd:
            lines.append(f"- Diretório atual: {cwd}")

        # Arquivos recentes no Desktop
        desktop_files = ctx.get("desktop_files", [])
        if desktop_files:
            lines.append(f"- Desktop: {', '.join(desktop_files[:6])}")

        # Últimas ações
        if self._action_history:
            lines.append("- Últimas ações:")
            for act in self._action_history[-3:]:
                icon = "✓" if act["sucesso"] else "✗"
                lines.append(f"  {icon} [{act['ts']}] {act['acao']}: {act['resultado'][:50]}")

        return "\n".join(lines)

    # ── Coleta de dados ───────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            time.sleep(self._interval)
            self._cycle_count += 1
            # Varredura completa de processos a cada 2 ciclos (24s);
            # campos leves (hora, janela ativa, CPU/RAM, clipboard) a
            # cada ciclo (12s) — bom equilíbrio entre atualidade e custo.
            self._collect(full=(self._cycle_count % 2 == 0))

    def _collect(self, full: bool = True) -> None:
        """
        Coleta dados do ambiente de forma segura.
        full=False pula a varredura cara de processos (_get_open_programs),
        reaproveitando o último valor conhecido.
        """
        ctx = dict(self._ctx)  # preserva campos não recoletados neste ciclo

        # Data/hora
        now = datetime.now()
        ctx["datetime"] = now.strftime("%d/%m/%Y %H:%M:%S (%A)")
        ctx["date"]     = now.strftime("%d/%m/%Y")
        ctx["time"]     = now.strftime("%H:%M:%S")

        # Janela ativa (barato — uma chamada WinAPI)
        ctx["active_window"] = self._get_active_window()

        # Programas abertos — caro, só roda em ciclos "full"
        if full:
            ctx["open_programs"] = self._get_open_programs()

        # CPU e RAM (barato, psutil já mantém cache interno)
        try:
            import psutil
            ctx["cpu_percent"] = psutil.cpu_percent(interval=None)
            ctx["ram_percent"] = psutil.virtual_memory().percent
        except Exception:
            ctx["cpu_percent"] = None
            ctx["ram_percent"] = None

        # Clipboard
        ctx["clipboard"] = self._get_clipboard()

        # Diretório de trabalho
        try:
            ctx["cwd"] = os.getcwd()
        except Exception:
            ctx["cwd"] = ""

        # Arquivos do Desktop — também não muda a cada segundo
        if full:
            ctx["desktop_files"] = self._get_desktop_files()

        with self._lock:
            self._ctx = ctx

    def _get_active_window(self) -> str:
        """Retorna o título da janela em foco."""
        try:
            if sys.platform == "win32":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value or ""
            elif sys.platform == "linux":
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    def _get_open_programs(self) -> List[str]:
        """Lista programas únicos em execução (sem processos do sistema)."""
        try:
            import psutil
            SYSTEM_PROCS = {
                "system", "registry", "smss.exe", "csrss.exe", "wininit.exe",
                "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
                "conhost.exe", "runtimebroker.exe", "searchindexer.exe",
                "antimalware", "spoolsv.exe", "fontdrvhost.exe", "sihost.exe",
                "taskhostw.exe", "explorer.exe",  # incluímos abaixo separado
            }
            seen   = set()
            result = []
            for proc in psutil.process_iter(["name", "status"]):
                try:
                    name = proc.info["name"].lower()
                    if (proc.info["status"] == "running"
                            and name not in SYSTEM_PROCS
                            and name not in seen
                            and not name.startswith("microsoft.")
                            and len(name) > 3):
                        seen.add(name)
                        # Formata o nome mais amigável
                        display = name.replace(".exe", "").replace("-", " ").title()
                        result.append(display)
                except Exception:
                    pass
            return sorted(result)[:15]
        except Exception:
            return []

    def _get_clipboard(self) -> str:
        """Lê o conteúdo atual do clipboard."""
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            pass
        # Fallback Windows
        try:
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["powershell", "-command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    def _get_desktop_files(self) -> List[str]:
        """Lista arquivos na área de trabalho do usuário."""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                return []
            files = []
            for f in os.listdir(desktop):
                if not f.startswith(".") and not f.endswith(".lnk"):
                    files.append(f)
            return sorted(files)[:10]
        except Exception:
            return []


# Instância global
context_manager = ContextManager()
