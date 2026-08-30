"""
Testes para ai/agent_provider.py (V12.2 — agentes especialistas).
Segue o mesmo padrão de mock de rede de tests/test_llm_backend.py
(patch em ai.ai_provider.requests, não em requests global).
"""
from unittest.mock import MagicMock, patch

from ai.agent_provider import AGENT_IDS, AgentProvider, _looks_like_error
from config.settings import settings


def _fake_chat_response(content: str):
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json.return_value = {"message": {"content": content}}
    return resp


def test_disabled_by_default():
    # agents_enabled=False é o default — arquitetura opcional, aditiva.
    ap = AgentProvider()
    assert ap.is_enabled() is False
    assert ap.ask("intent", "abre o spotify") is None


def test_ask_returns_none_when_disabled_without_touching_network():
    ap = AgentProvider()
    with patch("ai.ai_provider.requests.post") as mock_post:
        resultado = ap.ask("intent", "teste")
    mock_post.assert_not_called()
    assert resultado is None


def test_ask_returns_none_for_unknown_agent():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        assert ap.ask("agente_que_nao_existe", "teste") is None
    finally:
        settings.set("agents_enabled", value=False)


def test_ask_returns_content_when_agent_available():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        with patch("ai.ai_provider.requests.post") as mock_post:
            mock_post.return_value = _fake_chat_response('{"acao": "abrir_programa"}')
            resultado = ap.ask("intent", "abre o spotify")
        assert resultado == '{"acao": "abrir_programa"}'
    finally:
        settings.set("agents_enabled", value=False)


def test_ask_uses_short_timeout_per_agent():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        captured = {}

        def fake_post(url, json=None, timeout=None, **kwargs):
            captured["timeout"] = timeout
            return _fake_chat_response("ok")

        with patch("ai.ai_provider.requests.post", side_effect=fake_post):
            ap.ask("emotion", "teste")
        # emotion tem o timeout mais curto (2.0s) — bem menor que os
        # 300s da conversa principal, de proposito (ver docs/AI_ARCHITECTURE.md)
        assert captured["timeout"][1] == 2.0
    finally:
        settings.set("agents_enabled", value=False)


def test_ask_returns_none_when_ollama_unavailable():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        with patch("ai.ai_provider.requests.post", side_effect=Exception("conexao recusada")):
            resultado = ap.ask("autonomy", "teste")
        assert resultado is None
    finally:
        settings.set("agents_enabled", value=False)


def test_ask_json_parses_clean_json():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        with patch("ai.ai_provider.requests.post") as mock_post:
            mock_post.return_value = _fake_chat_response('{"sugestao": "fazer pausa", "confianca": 0.8}')
            resultado = ap.ask_json("autonomy", "contexto de teste")
        assert resultado == {"sugestao": "fazer pausa", "confianca": 0.8}
    finally:
        settings.set("agents_enabled", value=False)


def test_ask_json_strips_markdown_fences():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        with patch("ai.ai_provider.requests.post") as mock_post:
            mock_post.return_value = _fake_chat_response('```json\n{"categoria": "apelido"}\n```')
            resultado = ap.ask_json("memory", "contexto de teste")
        assert resultado == {"categoria": "apelido"}
    finally:
        settings.set("agents_enabled", value=False)


def test_ask_json_returns_none_for_invalid_json():
    settings.set("agents_enabled", value=True)
    try:
        ap = AgentProvider()
        with patch("ai.ai_provider.requests.post") as mock_post:
            mock_post.return_value = _fake_chat_response("isso nao e json de jeito nenhum")
            resultado = ap.ask_json("memory", "teste")
        assert resultado is None
    finally:
        settings.set("agents_enabled", value=False)


def test_looks_like_error_detects_ollama_error_shapes():
    assert _looks_like_error('{"erro": "Ollama não está disponível."}') is True
    assert _looks_like_error("[Erro: timeout]") is True
    assert _looks_like_error("") is True
    assert _looks_like_error(None) is True
    assert _looks_like_error("resposta normal do agente") is False


def test_all_seven_agents_have_distinct_timeout_and_system_prompt():
    from ai.agent_provider import _TIMEOUTS, _SYSTEM_PROMPTS
    assert set(AGENT_IDS) == {
        "intent", "planner", "reflection", "memory",
        "emotion", "vision", "autonomy",
    }
    for agent_id in AGENT_IDS:
        assert agent_id in _TIMEOUTS
        assert agent_id in _SYSTEM_PROMPTS
        assert _TIMEOUTS[agent_id] <= 5.0  # nenhum agente trava por muito tempo
