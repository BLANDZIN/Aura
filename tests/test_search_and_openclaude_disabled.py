from pathlib import Path

from angela.chief_engineer import Angela
from angela.platforms.local_stub import LocalStubPlatform
from angela.platforms.openclaude import OpenClaudePlatform


def make_platform(tmp_path: Path) -> LocalStubPlatform:
    ws = tmp_path / "ws"
    ws.mkdir()
    return LocalStubPlatform(project_root=tmp_path, workspace_dir=ws)


def test_search_is_case_sensitive_by_default(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "mod.py").write_text("class LearningEngine:\n    pass\n")

    assert p.search("learningengine") == []
    assert len(p.search("LearningEngine")) == 1


def test_search_case_insensitive_when_requested(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "mod.py").write_text("class LearningEngine:\n    pass\n")

    matches = p.search("learningengine", case_sensitive=False)
    assert len(matches) == 1
    assert "mod.py" in matches[0]


def test_s_read_files_finds_file_without_explicit_path(tmp_path):
    # Reproduz o exemplo do README: "Analise o Learning Engine" não cita
    # nenhum caminho — antes da correção, files_read ficava vazio.
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "automation").mkdir()
    (ws / "automation" / "learning_engine.py").write_text(
        "class LearningEngine:\n    def aprende(self):\n        pass\n"
    )
    platform = LocalStubPlatform(project_root=tmp_path, workspace_dir=ws)

    angela = Angela(project_root=str(tmp_path), platform=platform,
                     enable_autoengineering=False)
    report = angela._investigate("Analise o Learning Engine")

    assert any("learning_engine.py" in f for f in report.files_read)


def test_openclaude_adapter_permanently_disabled(tmp_path):
    # LICENSE do repositório declara que é derivado do Claude Code sem
    # autorização da Anthropic — este adapter nunca pode voltar a ligar
    # sozinho, mesmo que "openclaude" apareça no PATH de alguém.
    adapter = OpenClaudePlatform(project_root=str(tmp_path))
    assert adapter.is_available() is False
