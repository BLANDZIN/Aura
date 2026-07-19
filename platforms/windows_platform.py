"""
platforms/windows_platform.py

Implementação Windows de BasePlatform. Lógica movida de tools/resolvers.py
(comportamento idêntico ao que já funcionava) — nada foi reescrito aqui,
só reorganizado atrás da interface comum.
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from platforms.base_platform import BasePlatform

HOME = Path.home()

# Movido de tools/resolvers.py sem alteração.
_SPECIAL_FOLDERS: Dict[str, str] = {
    "desktop":          str(HOME / "Desktop"),
    "area de trabalho": str(HOME / "Desktop"),
    "área de trabalho": str(HOME / "Desktop"),
    "downloads":        str(HOME / "Downloads"),
    "documentos":       str(HOME / "Documents"),
    "documents":        str(HOME / "Documents"),
    "imagens":          str(HOME / "Pictures"),
    "pictures":         str(HOME / "Pictures"),
    "musicas":          str(HOME / "Music"),
    "música":           str(HOME / "Music"),
    "videos":           str(HOME / "Videos"),
    "vídeos":           str(HOME / "Videos"),
    "appdata":          os.environ.get("APPDATA", str(HOME / "AppData/Roaming")),
    "localappdata":     os.environ.get("LOCALAPPDATA", str(HOME / "AppData/Local")),
    "temp":             os.environ.get("TEMP", "C:/Windows/Temp"),
    "sistema":          "C:/Windows/System32",
    "system32":         "C:/Windows/System32",
    "c:":               "C:/",
    "d:":               "D:/",
    "raiz":             "C:/",
}

# Movido de tools/resolvers.py sem alteração.
_WINDOWS_PROGRAMS: Dict[str, str] = {
    "gerenciador de tarefas":"taskmgr.exe", "task manager":"taskmgr.exe", "taskmgr":"taskmgr.exe",
    "explorador":"explorer.exe", "explorador de arquivos":"explorer.exe",
    "file explorer":"explorer.exe", "explorer":"explorer.exe",
    "painel de controle":"control.exe", "control panel":"control.exe",
    "configuracoes":"ms-settings:", "configurações":"ms-settings:", "settings":"ms-settings:",
    "cmd":"cmd.exe", "prompt de comando":"cmd.exe", "prompt":"cmd.exe",
    "powershell":"powershell.exe", "terminal windows":"wt.exe", "terminal":"wt.exe",
    "regedit":"regedit.exe", "registro":"regedit.exe",
    "msconfig":"msconfig.exe",
    "snipping tool":"snippingtool.exe", "captura de tela":"snippingtool.exe",
    "notepad":"notepad.exe", "bloco de notas":"notepad.exe",
    "wordpad":"wordpad.exe", "calculadora":"calc.exe", "calculator":"calc.exe",
    "paint":"mspaint.exe",
    "word":"winword.exe", "excel":"excel.exe", "powerpoint":"powerpnt.exe",
    "outlook":"outlook.exe", "onenote":"onenote.exe", "teams":"teams.exe",
    "chrome":"chrome.exe", "google chrome":"chrome.exe",
    "firefox":"firefox.exe", "mozilla firefox":"firefox.exe",
    "edge":"msedge.exe", "microsoft edge":"msedge.exe",
    "opera":"opera.exe", "brave":"brave.exe",
    "vs code":"code.exe", "vscode":"code.exe", "visual studio code":"code.exe",
    "visual studio":"devenv.exe",
    "git bash":"git-bash.exe", "git":"git-bash.exe",
    "pycharm":"pycharm64.exe", "intellij":"idea64.exe",
    "android studio":"studio64.exe",
    "docker":"docker desktop.exe",
    "vlc":"vlc.exe", "spotify":"spotify.exe", "itunes":"itunes.exe",
    "obs":"obs64.exe", "obs studio":"obs64.exe",
    "audacity":"audacity.exe",
    "discord":"discord.exe", "whatsapp":"whatsapp.exe",
    "telegram":"telegram.exe", "slack":"slack.exe",
    "zoom":"zoom.exe", "skype":"skype.exe",
    "winrar":"winrar.exe", "7zip":"7zfm.exe", "7-zip":"7zfm.exe",
    "steam":"steam.exe", "epic games":"epicgameslauncher.exe",
    "ccleaner":"ccleaner.exe",
    "notepad++":"notepad++.exe",
    "filezilla":"filezilla.exe",
    "putty":"putty.exe",
    "wireshark":"wireshark.exe",
    "postman":"postman.exe",
}


class WindowsPlatform(BasePlatform):
    name = "windows"

    def open_folder(self, path: str) -> None:
        subprocess.Popen(["explorer.exe", os.path.normpath(path)])

    def open_file(self, path: str, args: Optional[List[str]] = None) -> None:
        args = args or []
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None, "open", path,
            (" ".join(str(a) for a in args)) or None,
            None, 1
        )

    def open_program(self, name_or_path: str, args: Optional[List[str]] = None) -> None:
        # ShellExecuteW resolve tanto arquivo quanto programa da mesma forma.
        self.open_file(name_or_path, args)

    def special_folders(self) -> Dict[str, str]:
        return dict(_SPECIAL_FOLDERS)

    def program_aliases(self) -> Dict[str, str]:
        return dict(_WINDOWS_PROGRAMS)

    def find_program(self, query: str, threshold: float = 0.55) -> Optional[str]:
        from core.fuzzy_search import find_best_program
        return find_best_program(query, threshold=threshold)
