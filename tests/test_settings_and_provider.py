from unittest.mock import MagicMock, patch

from ai.ai_provider import OllamaProvider
from config.settings import DEFAULTS, settings


def test_voice_defaults_have_no_dead_keys():
    voice = DEFAULTS["voice"]
    for dead_key in ("enabled", "tts_engine", "stt_engine"):
        assert dead_key not in voice


def test_voice_defaults_keep_keys_voice_manager_reads():
    voice = DEFAULTS["voice"]
    for used_key in ("tts_enabled", "stt_enabled", "auto_speak",
                      "voice_rate", "voice_volume", "stt_model", "language"):
        assert used_key in voice


def test_ai_default_model_matches_recommendation():
    assert DEFAULTS["ai"]["model"] == "qwen2.5:3b"


def test_angela_namespace_is_independent_from_ai_namespace():
    assert DEFAULTS["angela"]["model"] != DEFAULTS["ai"]["model"]
    assert settings.get("angela", "model") == "qwen3:4b"
    assert settings.get("ai", "model") == "qwen2.5:3b"


def test_ollama_provider_default_namespace_unchanged_for_aura():
    # Compatibilidade: OllamaProvider() sem argumento continua lendo "ai",
    # exatamente como antes desta mudança.
    p = OllamaProvider()
    assert p.model == settings.get("ai", "model")
    assert p.base_url == settings.get("ai", "base_url")


def test_ollama_provider_angela_namespace_reads_separate_config():
    p = OllamaProvider(settings_namespace="angela")
    assert p.model == "qwen3:4b"
    assert p.model != OllamaProvider().model


def test_ollama_provider_chat_uses_configured_model():
    p = OllamaProvider(settings_namespace="angela")
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json.return_value = {"message": {"content": "ok"}}
        return resp

    with patch("ai.ai_provider.requests.post", side_effect=fake_post):
        p.chat([{"role": "user", "content": "oi"}])

    assert captured["json"]["model"] == "qwen3:4b"


def test_ollama_provider_5xx_gives_actionable_diagnostic_not_raw_exception():
    # Reproduz o erro real reportado ao testar a v9 f2: Ollama respondeu
    # 500 em /api/chat. Confirmado por pesquisa que isso é quase sempre
    # falha ao CARREGAR o modelo (RAM/VRAM, versão do Ollama, blob
    # corrompido) -- não um bug de payload. A mensagem deve orientar,
    # não só devolver a exceção crua.
    import requests as requests_module

    p = OllamaProvider(settings_namespace="angela")
    resp = MagicMock()
    resp.status_code = 500
    http_error = requests_module.exceptions.HTTPError(response=resp)

    def fake_post(url, json=None, timeout=None, **kwargs):
        raise http_error

    with patch("ai.ai_provider.requests.post", side_effect=fake_post):
        answer = p.chat([{"role": "user", "content": "oi"}])

    assert "500" in answer
    assert "ollama run" in answer.lower()
    assert p.model in answer
