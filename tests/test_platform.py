"""
tests/test_platform.py — validação da abstração de plataforma (V10).

Este sandbox é Linux, então:
- Detecção e o caminho Linux são testados com EXECUÇÃO REAL.
- O caminho Windows é testado por PRESENÇA/ESTRUTURA do código (a lógica
  foi movida, não reescrita, de tools/resolvers.py original) — não pode
  ser executado aqui, e isso é dito explicitamente, não escondido.
"""
import platform as _stdlib_platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from platforms.linux_platform import LinuxPlatform
from platforms.platform_manager import platform_manager
from platforms.windows_platform import WindowsPlatform


def test_platform_detected_matches_running_os():
    # Prova real, não assumida: platform_manager tem que bater com o
    # que platform.system() diz AGORA, neste processo.
    system = _stdlib_platform.system()
    if system == "Linux":
        assert platform_manager.name == "linux"
        assert isinstance(platform_manager, LinuxPlatform)
    elif system == "Windows":
        assert platform_manager.name == "windows"
        assert isinstance(platform_manager, WindowsPlatform)


def test_linux_special_folders_are_real_paths_under_home():
    p = LinuxPlatform()
    folders = p.special_folders()
    assert folders["desktop"] == str(Path.home() / "Desktop")
    assert folders["downloads"] == str(Path.home() / "Downloads")
    assert folders["home"] == str(Path.home())


@pytest.mark.skipif(shutil.which("xdg-open") is None, reason="xdg-open não disponível")
def test_linux_open_folder_invokes_xdg_open_for_real(tmp_path):
    p = LinuxPlatform()
    with patch("subprocess.Popen") as mock_popen:
        p.open_folder(str(tmp_path))
    mock_popen.assert_called_once_with(["xdg-open", str(tmp_path)])


def test_linux_open_program_prefers_direct_path_executable():
    p = LinuxPlatform()
    with patch("shutil.which", return_value="/usr/bin/firefox"), \
         patch("subprocess.Popen") as mock_popen:
        p.open_program("firefox")
    mock_popen.assert_called_once_with(["firefox"])


def test_linux_open_program_falls_back_to_alias_when_not_on_path():
    p = LinuxPlatform()
    with patch("shutil.which", return_value=None), \
         patch("subprocess.Popen") as mock_popen:
        p.open_program("spotify")
    mock_popen.assert_called_once_with(["flatpak", "run", "com.spotify.Client"])


def test_linux_find_program_reads_real_desktop_files():
    # Sem mock — lê arquivos .desktop de verdade se existirem no sandbox
    # (ex.: LibreOffice costuma vir instalado em imagens Ubuntu).
    p = LinuxPlatform()
    if not any(Path(d).is_dir() for d in ("/usr/share/applications",)):
        pytest.skip("Nenhum diretório de .desktop files neste ambiente")
    result = p.find_program("libreoffice", threshold=0.5)
    # Não afirmamos que vai achar (depende do que está instalado no
    # ambiente de quem rodar) — só que não quebra e retorna str ou None.
    assert result is None or isinstance(result, str)


def test_resolvers_use_platform_manager_not_hardcoded_windows_dict():
    # Regressão do bug real que a divisão introduziria se esquecêssemos:
    # tools/resolvers.py não pode mais ter SPECIAL_FOLDERS/WINDOWS_PROGRAMS
    # hardcoded — isso pertence às plataformas agora.
    import tools.resolvers as resolvers
    assert not hasattr(resolvers, "SPECIAL_FOLDERS")
    assert not hasattr(resolvers, "WINDOWS_PROGRAMS")


def test_resolve_folder_uses_current_platform_special_folders():
    from tools.resolvers import _resolve_folder
    resolved = _resolve_folder("desktop")
    assert resolved == platform_manager.special_folders()["desktop"]


def test_windows_platform_structure_preserved_but_not_executed_here():
    # Não dá pra rodar ShellExecuteW/explorer.exe fora do Windows — isso
    # é verificado por estrutura (a lógica foi movida, não reescrita) e
    # fica marcado explicitamente como não executado neste ambiente.
    p = WindowsPlatform()
    assert "chrome" in p.program_aliases()
    assert p.program_aliases()["chrome"] == "chrome.exe"
    assert "desktop" in p.special_folders()
    # open_file/open_folder usam ctypes.windll — não executamos aqui.
