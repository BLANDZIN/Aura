"""
platforms/linux_platform.py

Implementação Linux de BasePlatform. Suporte inicial — a lista de
aliases é pequena de propósito (mesmo espírito de WINDOWS_PROGRAMS, que
também começou pequeno e cresceu com uso real); não assume que
flatpak/snap estão instalados, e não assume que qualquer app.exe do
mapa Windows tem equivalente aqui.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from platforms.base_platform import BasePlatform

HOME = Path.home()

# Ponto de partida pequeno — nome amigável -> comando real (pode incluir
# "flatpak run <app-id>" como comando completo, não só o binário).
LINUX_PROGRAM_ALIASES: Dict[str, str] = {
    "explorador": "xdg-open .",
    "explorador de arquivos": "xdg-open .",
    "terminal": "x-terminal-emulator",
    "calculadora": "gnome-calculator",
    "spotify": "flatpak run com.spotify.Client",
    "discord": "flatpak run com.discordapp.Discord",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "chrome": "google-chrome", "google chrome": "google-chrome",
    "chromium": "chromium",
    "firefox": "firefox",
    "vlc": "vlc",
    "libreoffice": "libreoffice", "writer": "libreoffice --writer",
    "calc": "libreoffice --calc", "impress": "libreoffice --impress",
    "gimp": "gimp",
    "steam": "steam",
    "telegram": "flatpak run org.telegram.desktop",
}

_XDG_DIRS = [
    "/usr/share/applications",
    str(HOME / ".local/share/applications"),
]


class LinuxPlatform(BasePlatform):
    name = "linux"

    def open_folder(self, path: str) -> None:
        subprocess.Popen(["xdg-open", path])

    def open_file(self, path: str, args: Optional[List[str]] = None) -> None:
        subprocess.Popen(["xdg-open", path])

    def open_program(self, name_or_path: str, args: Optional[List[str]] = None) -> None:
        args = [str(a) for a in (args or [])]
        key = name_or_path.strip().lower()

        # 1. Executável direto no PATH
        if shutil.which(name_or_path):
            subprocess.Popen([name_or_path, *args])
            return

        # 2. Alias conhecido (pode ser um comando composto, ex: "flatpak run X")
        if key in LINUX_PROGRAM_ALIASES:
            subprocess.Popen(LINUX_PROGRAM_ALIASES[key].split() + args)
            return

        # 3. Flatpak instalado com app-id parecido
        if shutil.which("flatpak"):
            app_id = self._flatpak_match(key)
            if app_id:
                subprocess.Popen(["flatpak", "run", app_id, *args])
                return

        # 4. Snap com esse nome exato
        if shutil.which("snap"):
            try:
                subprocess.Popen(["snap", "run", name_or_path, *args])
                return
            except Exception:
                pass

        # 5. Último recurso: tenta como comando mesmo assim — erro claro
        # do shell é melhor que engolir silenciosamente.
        subprocess.Popen([name_or_path, *args])

    @staticmethod
    def _flatpak_match(query: str) -> Optional[str]:
        try:
            out = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            for app_id in out.splitlines():
                app_id = app_id.strip()
                if app_id and query in app_id.lower():
                    return app_id
        except Exception:
            pass
        return None

    def special_folders(self) -> Dict[str, str]:
        home = str(HOME)
        return {
            "desktop": f"{home}/Desktop",
            "area de trabalho": f"{home}/Desktop",
            "área de trabalho": f"{home}/Desktop",
            "downloads": f"{home}/Downloads",
            "documentos": f"{home}/Documents", "documents": f"{home}/Documents",
            "imagens": f"{home}/Pictures", "pictures": f"{home}/Pictures",
            "musicas": f"{home}/Music", "música": f"{home}/Music",
            "videos": f"{home}/Videos", "vídeos": f"{home}/Videos",
            "home": home, "raiz": "/",
        }

    def program_aliases(self) -> Dict[str, str]:
        return dict(LINUX_PROGRAM_ALIASES)

    def find_program(self, query: str, threshold: float = 0.55) -> Optional[str]:
        """
        Busca fuzzy em arquivos .desktop (padrão freedesktop.org) —
        equivalente Linux de vasculhar Program Files no Windows.
        """
        from core.fuzzy_search import similarity

        best_score, best_exec = 0.0, None
        for d in _XDG_DIRS:
            if not os.path.isdir(d):
                continue
            try:
                for fname in os.listdir(d):
                    if not fname.endswith(".desktop"):
                        continue
                    entry = self._parse_desktop_entry(os.path.join(d, fname))
                    if not entry:
                        continue
                    name, exec_cmd = entry
                    score = similarity(query, name)
                    if score > best_score:
                        best_score, best_exec = score, exec_cmd
            except (PermissionError, OSError):
                continue

        if best_score >= threshold:
            return best_exec
        return None

    @staticmethod
    def _parse_desktop_entry(path: str):
        """Extrai (Name, Exec) de um arquivo .desktop. None se inválido."""
        name, exec_cmd = None, None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("Name=") and name is None:
                        name = line.split("=", 1)[1]
                    elif line.startswith("Exec=") and exec_cmd is None:
                        # Remove placeholders tipo %U, %f
                        exec_cmd = line.split("=", 1)[1].split(" %")[0].strip()
                    if name and exec_cmd:
                        break
        except Exception:
            return None
        if name and exec_cmd:
            return name, exec_cmd
        return None
