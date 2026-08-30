"""
Testes para as partes já implementadas de scripts/download_models.py
(esqueleto de arquitetura, V12.2 — ver docstring do próprio script).
"""
from unittest.mock import MagicMock, patch

from scripts.download_models import _agent_models, check_installed_models


def test_agent_models_derives_from_settings_not_hardcoded():
    modelos = _agent_models()
    assert modelos["aura"] == "qwen2.5:3b"
    assert set(modelos.keys()) == {
        "aura", "intent", "planner", "reflection",
        "memory", "emotion", "vision", "autonomy",
    }


def test_agent_models_reuses_same_file_for_grouped_roles():
    # planner/reflection/vision compartilham o mesmo arquivo de modelo
    # (ver docs/AI_ARCHITECTURE.md — "5 arquivos distintos, não 8")
    modelos = _agent_models()
    assert modelos["planner"] == modelos["reflection"] == modelos["vision"]
    assert modelos["memory"] == modelos["emotion"]


def test_check_installed_models_parses_ollama_list_output():
    fake_output = "NAME              ID       SIZE\nqwen2.5:3b        abc123   1.9GB\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_output)
        status = check_installed_models()
    assert status["qwen2.5:3b"] is True
    assert status["llama3.2:1b"] is False  # não apareceu no fake output


def test_check_installed_models_handles_missing_ollama_binary():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        status = check_installed_models()
    assert all(v is False for v in status.values())
