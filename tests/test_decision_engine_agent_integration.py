"""
Teste focado na integração do agente `intent` em automation/decision_engine.py
(V12.2, "Nível 5.5" — só entra depois que regex/fuzzy já falharam). Não
tenta cobrir o DecisionEngine inteiro, só o comportamento novo desta fase.
"""
from unittest.mock import patch

from automation.decision_engine import DecisionEngine
from config.settings import settings


def _sem_regex_nem_fuzzy(texto: str) -> bool:
    """Frase deliberadamente sem verbo/tipo reconhecível pelo IntentEngine
    nem padrão do _DIRECT_PATTERNS — força a decisão a cair até o final."""
    return True


def test_agent_disabled_falls_through_to_llm_unchanged():
    # agents_enabled=False é o default — comportamento idêntico ao V12.1.
    # O gate real (não chamar a rede quando desligado) já é testado em
    # tests/test_agent_provider.py — aqui validamos só o resultado da
    # decisão, sem mockar ask_json (mockar contornaria o próprio gate
    # que queremos exercitar de verdade).
    settings.set("agents_enabled", value=False)
    engine = DecisionEngine()
    d = engine.decide("frase completamente fora de qualquer padrão coloquial xyz")
    assert d.method == "llm"


def test_agent_low_confidence_falls_through_to_llm():
    settings.set("agents_enabled", value=True)
    try:
        engine = DecisionEngine()
        with patch(
            "ai.agent_provider.agent_provider.ask_json",
            return_value={"acao": "abrir", "tipo": "aplicativo", "alvo": "spotify", "confianca": 0.4},
        ):
            d = engine.decide("frase completamente fora de qualquer padrão coloquial xyz")
        assert d.method == "llm"  # 0.4 < 0.75, não usa o agente
    finally:
        settings.set("agents_enabled", value=False)


def test_agent_confident_result_is_used_as_direct_decision():
    settings.set("agents_enabled", value=True)
    try:
        engine = DecisionEngine()
        with patch(
            "ai.agent_provider.agent_provider.ask_json",
            return_value={"acao": "abrir", "tipo": "aplicativo", "alvo": "spotify", "confianca": 0.9},
        ):
            d = engine.decide("frase completamente fora de qualquer padrão coloquial xyz")
        assert d.method == "direct"
        assert d.payload["acao"] == "abrir_programa"
        assert d.payload["parametros"].get("programa") == "spotify"
        # nunca mais confiante que o teto do parser estruturado (0.80),
        # mesmo o agente tendo se autoavaliado em 0.9
        assert d.confidence <= 0.80
    finally:
        settings.set("agents_enabled", value=False)


def test_agent_exception_does_not_break_decide():
    settings.set("agents_enabled", value=True)
    try:
        engine = DecisionEngine()
        with patch(
            "ai.agent_provider.agent_provider.ask_json",
            side_effect=Exception("ollama caiu no meio"),
        ):
            d = engine.decide("frase completamente fora de qualquer padrão coloquial xyz")
        assert d.method == "llm"  # cai pro fallback, não propaga a exceção
    finally:
        settings.set("agents_enabled", value=False)
