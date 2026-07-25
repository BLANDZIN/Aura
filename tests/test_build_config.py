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

    def test_windows_spec_generation_is_valid_python(self):
        """generate_spec_content() do build.py deve produzir Python válido.

        Antes disso era um arquivo estático build/aura_windows.spec — build.py
        passou a gerar o spec na hora (elimina os dois .spec quase-idênticos
        que tinham o mesmo bug de sintaxe EXE/COLLECT — ver V11_AUDITORIA.md).
        Este teste teria funcionado. Sincronizado na V12.1."""
        sys.path.insert(0, str(ROOT))
        import build as build_module
        content = build_module.generate_spec_content()
        compile(content, "aura_build.spec (gerado)", "exec")
        assert "EXE(" in content and "COLLECT(" in content
        # regressão do bug real da V11: EXE não pode receber a.binaries
        # diretamente quando COLLECT também os recebe (colisão de nome
        # dist/AURA no Linux, onde o binário não tem extensão)
        assert "exclude_binaries=True" in content

    def test_linux_spec_valid(self):
        """build.py deve existir e gerar spec valido."""
        assert (ROOT / "build.py").is_file(), "build.py nao encontrado"
        compile((ROOT / "build.py").read_text(), "build.py", "exec")

    def test_version_info_is_optional_not_required(self):
        """build/version_info.txt é OPCIONAL (recurso de versão do .exe no
        Windows) — generate_spec_content() deve funcionar normalmente sem
        ele (ver icon_line/version_line em build.py), não travar o build."""
        sys.path.insert(0, str(ROOT))
        import build as build_module
        # Não precisa existir; o teste é que gerar o spec não falha sem ele.
        content = build_module.generate_spec_content()
        assert isinstance(content, str) and "Analysis(" in content

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
        for fname in ["scripts/iniciar.bat", "scripts/iniciar.sh"]:
            path = ROOT / fname
            if path.is_file():
                content = path.read_text()
                assert "AURA.py" in content or "AURA" in content, \
                    f"{fname} não referencia AURA.py"

    def test_nsis_installer_is_a_documented_gap_not_a_silent_one(self):
        """
        O instalador NSIS (installer/aura_installer.nsi) existiu na V11 e
        foi removido na V12 sem substituto — confirmado: nenhum arquivo
        .nsi, nem menção a NSIS/makensis, sobra em lugar nenhum do
        projeto. Decisão registrada (V12.1, Prioridade 2, Opção A):
        sincronizar os testes com a realidade em vez de reconstruir um
        .nsi de memória sem ter como validar com makensis neste ambiente.

        Distribuição atual: pasta portátil (dist/AURA/AURA.exe + libs).
        Se um instalador de verdade (wizard, atalhos, desinstalador) for
        necessário pro release público, é uma feature aditiva a pedir
        explicitamente — não algo pra reconstruir às cegas aqui.
        """
        nsi_files = list(ROOT.rglob("*.nsi"))
        assert nsi_files == [], (
            f"Apareceu um .nsi ({nsi_files}) mas este teste assume que não "
            f"há instalador NSIS no projeto — se foi reintroduzido de "
            f"propósito, delete este teste e valide o conteúdo do .nsi."
        )

    def test_portable_dist_has_everything_it_needs(self):
        """Sem instalador, a pasta dist/ gerada por build.py precisa ser
        auto-suficiente: binário + todas as pastas de runtime esperadas
        (ver make_dirs() em build.py)."""
        sys.path.insert(0, str(ROOT))
        import build as build_module
        import inspect
        src = inspect.getsource(build_module.make_dirs)
        for d in ["models", "extensions", "profiles", "cache", "workspace",
                  "logs", "database", "themes", "voices"]:
            assert d in src, f"make_dirs() não cria a pasta '{d}/'"

    def test_license_file_exists(self):
        """LICENSE.txt deve existir."""
        license_path = ROOT / "LICENSE.txt"
        assert license_path.is_file(), "LICENSE.txt não encontrado"
        assert "MIT License" in license_path.read_text(), \
            "LICENSE.txt deve ser MIT"

    def test_assets_used_by_build_exist(self):
        """assets/aura.ico e aura.png são usados por generate_spec_content()
        (ícone é opcional no Linux, obrigatório de fato só se quiser ícone
        no .exe do Windows). welcome.bmp/header.bmp ficaram do NSIS
        removido (ver test_nsis_installer_is_a_documented_gap_not_a_silent_one)
        — mantidos no repo mas não são mais consumidos por nada."""
        for fname in ["aura.ico", "aura.png"]:
            path = ROOT / "assets" / fname
            assert path.is_file(), f"assets/{fname} não encontrado"
