from unittest.mock import MagicMock, patch

import requests

from angela.llm.backend import AngelaLLM


def test_is_available_true_when_ollama_responds():
    llm = AngelaLLM()
    with patch("ai.ai_provider.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert llm.is_available() is True


def test_is_available_false_when_no_server():
    llm = AngelaLLM()
    with patch("ai.ai_provider.requests.get", side_effect=Exception("no server")):
        assert llm.is_available() is False


def test_ask_sends_system_prompt_and_context_to_angela_model():
    llm = AngelaLLM()
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json.return_value = {"message": {"content": "resposta do modelo"}}
        return resp

    with patch("ai.ai_provider.requests.post", side_effect=fake_post):
        answer = llm.ask("qual a causa?", context=["nota 1", "nota 2"])

    assert answer == "resposta do modelo"
    payload = captured["json"]
    # Usa o modelo/namespace da Angela, não o da AURA (qwen2.5:3b).
    assert payload["model"] == "qwen3:4b"
    messages = payload["messages"]
    assert messages[0]["role"] == "system"
    assert "nota 1" in messages[1]["content"] and "nota 2" in messages[1]["content"]
    assert messages[-1]["content"] == "qual a causa?"


def test_ask_returns_error_payload_when_ollama_down_instead_of_raising():
    llm = AngelaLLM()
    with patch("ai.ai_provider.requests.post",
               side_effect=requests.exceptions.ConnectionError()):
        answer = llm.ask("qualquer coisa")
    assert "erro" in answer.lower()


def test_ask_without_context_still_works():
    llm = AngelaLLM()

    def fake_post(url, json=None, timeout=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json.return_value = {"message": {"content": "ok"}}
        return resp

    with patch("ai.ai_provider.requests.post", side_effect=fake_post):
        assert llm.ask("pergunta simples") == "ok"
