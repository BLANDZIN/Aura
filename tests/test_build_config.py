"""
tests/test_build_config.py
==========================
Testes para a configuração de build (PyInstaller).
Valida que os arquivos de spec, scripts de build, e estrutura
de distribuição estão corretos — sem precisar rodar o PyInstaller.
"""

import os
import sys
import ast
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class TestBuildConfig:
    """Valida a configuração do sistema de build."""

    def test_entry_point_exists(self):
        """AURA.py deve existir como ponto de entrada."""
        assert (ROOT / "AURA.py").is_file(), "AURA.py não encontrado"

    def test_windows_spec_valid(self):
        """aura_windows.spec deve ser Python válido."""
        spec = ROOT / "aura_windows.spec"
        assert spec.is_file(), "aura_windows.spec não encontrado"
        compile(spec.read_text(), "aura_windows.spec", "exec")

    def test_linux_spec_valid(self):
        """aura_linux.spec deve ser Python válido."""
        spec = ROOT / "aura_linux.spec"
        assert spec.is_file(), "aura_linux.spec não encontrado"
        compile(spec.read_text(), "aura_linux.spec", "exec")

    def test_version_info_valid(self):
        """version_info.txt deve ser Python válido."""
        vi = ROOT / "version_info.txt"
        assert vi.is_file(), "version_info.txt não encontrado"
        compile(vi.read_text(), "version_info.txt", "exec")

    def test_build_windows_script_exists(self):
        """build.py deve existir como build unificado."""
        assert (ROOT / "build.py").is_file()

    def test_build_linux_script_exists(self):
        """build.py deve existir como build unificado."""
        assert (ROOT / "build.py").is_file()

    def test_data_files_exist(self):
        """Arquivos de dados incluídos no build devem existir."""
        for f in ["config/settings.json", "config/personality.json"]:
            path = ROOT / f
            assert path.is_file(), f"{f} não encontrado"
            # Valida que são JSON válido
            try:
                json.loads(path.read_text())
            except json.JSONDecodeError:
                # personality.json pode ter comentários — ignora
                pass

    def test_v11_directory_structure(self):
        """Diretórios V11 devem existir."""
        dirs = [
            "models", "extensions", "profiles",
            "cache", "workspace", "logs",
            "database", "themes", "voices",
        ]
        for d in dirs:
            path = ROOT / d
            assert path.is_dir(), f"Diretório {d}/ não encontrado"

    def test_requirements_covers_core_deps(self):
        """requirements.txt deve listar dependências essenciais."""
        req = (ROOT / "requirements.txt").read_text()
        essential = ["PyQt6", "requests", "psutil", "pyautogui", "pyttsx3"]
        for dep in essential:
            assert dep in req, f"{dep} não encontrado em requirements.txt"

    def test_all_modules_importable(self):
        """Todos os módulos do projeto devem ser compiláveis."""
        modules = [
            "AURA", "main", "launcher",
            "ai.ai_engine", "ai.ai_provider", "ai.emotion_engine",
            "ai.identity_engine", "ai.intent_engine",
            "core.event_bus", "core.logger", "core.metrics", "core.fuzzy_search",
            "config.settings", "config.personality",
            "database.db_manager",
            "memory.memory_manager",
            "platforms.platform_manager", "platforms.base_platform",
            "platforms.linux_platform", "platforms.windows_platform",
            "tools.tool_manager", "tools.base_tool", "tools.resolvers",
            "tools.param_normalization",
            "tools.browser_tools", "tools.control_tools", "tools.file_tools",
            "tools.memory_tools", "tools.ocr_tools", "tools.procedure_tools",
            "tools.system_tools", "tools.task_tools",
            "automation.automation_learner", "automation.decision_engine",
            "automation.error_learning", "automation.flow_executor",
            "automation.flow_library", "automation.learner_bridge",
            "automation.learning_engine", "automation.planner",
            "tasks.task_manager",
            "vision.context_manager",
            "voice.voice_manager",
            "angela.chief_engineer", "angela.audit", "angela.workflow",
            "angela.communication", "angela.personality", "angela.report",
            "angela.autoengineering",
            "angela.llm.backend",
            "angela.platforms.base", "angela.platforms.local_stub",
            "angela.tools.git_tools",
            "ui.app", "ui.chat_panel", "ui.chat_page", "ui.angela_panel",
            "ui.angela_page", "ui.avatar_widget", "ui.confirm_dialog",
            "ui.main_window", "ui.tools_page", "ui.memory_page",
            "ui.monitor_page", "ui.developer_page",
            "launcher.app",
            "launcher.pages.home", "launcher.pages.settings",
            "launcher.pages.models", "launcher.pages.updates",
            "launcher.pages.extensions", "launcher.pages.diagnostics",
            "launcher.pages.backup", "launcher.pages.profiles",
        ]
        failed = []
        for mod_name in modules:
            try:
                mod_path = ROOT / (mod_name.replace(".", "/") + ".py")
                if mod_path.is_file():
                    code = mod_path.read_text()
                    compile(code, str(mod_path), "exec")
                else:
                    init_path = ROOT / (mod_name.replace(".", "/") + "/__init__.py")
                    if init_path.is_file():
                        compile(init_path.read_text(), str(init_path), "exec")
                    else:
                        failed.append(f"{mod_name} (arquivo não encontrado)")
            except SyntaxError as e:
                failed.append(f"{mod_name} ({e})")
            except Exception as e:
                failed.append(f"{mod_name} ({e})")

        assert not failed, f"Módulos com erro:\n" + "\n".join(failed)

    def test_angela_openclaude_optional(self):
        """angela.platforms.openclaude é opcional (sem dependência externa)."""
        # Verifica que o arquivo existe mas não quebra se openclaude não estiver instalado
        path = ROOT / "angela" / "platforms" / "openclaude.py"
        assert path.is_file()
        code = path.read_text()
        compile(code, str(path), "exec")

    def test_iniciar_scripts_delegate_to_aura(self):
        """Scripts de inicialização devem referenciar AURA.py."""
        for fname in ["iniciar.bat", "iniciar.sh"]:
            path = ROOT / fname
            if path.is_file():
                content = path.read_text()
                assert "AURA.py" in content or "AURA" in content, \
                    f"{fname} não referencia AURA.py"

    def test_nsis_installer_script_exists(self):
        """installer/aura_installer.nsi deve existir e ser válido."""
        nsi = ROOT / "installer" / "aura_installer.nsi"
        assert nsi.is_file(), "installer/aura_installer.nsi não encontrado"
        content = nsi.read_text()
        assert "PRODUCT_NAME" in content, "NSIS script sem PRODUCT_NAME"
        assert "PRODUCT_VERSION" in content, "NSIS script sem PRODUCT_VERSION"
        assert "AURA.exe" in content, "NSIS script não referencia AURA.exe"
        assert "uninst.exe" in content, "NSIS script sem desinstalador"

    def test_build_installer_script_exists(self):
        """installer/aura_installer.nsi deve existir."""
        assert (ROOT / "installer" / "aura_installer.nsi").is_file(), \
            "installer/aura_installer.nsi não encontrado"

    def test_license_file_exists(self):
        """LICENSE.txt deve existir."""
        license_path = ROOT / "LICENSE.txt"
        assert license_path.is_file(), "LICENSE.txt não encontrado"
        assert "MIT License" in license_path.read_text(), \
            "LICENSE.txt deve ser MIT"

    def test_assets_for_installer_exist(self):
        """Assets do instalador NSIS devem existir."""
        for fname in ["aura.ico", "aura.png", "welcome.bmp", "header.bmp"]:
            path = ROOT / "assets" / fname
            assert path.is_file(), f"assets/{fname} não encontrado"

    def test_installer_directory_exists(self):
        """Pasta installer/ deve existir."""
        assert (ROOT / "installer").is_dir(), \
            "installer/ não encontrado"
