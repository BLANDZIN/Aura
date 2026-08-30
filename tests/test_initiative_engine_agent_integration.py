"""
Teste focado na integração do agente `autonomy` em
automation/decision_engine.py::InitiativeEngine (V12.2). A heurística
antiga (15% de chance + dicionário fixo por app) virou fallback — este
arquivo cobre o comportamento novo, não a heurística em si (já implícita
nos testes de fallback abaixo).
"""
import time
from unittest.mock import patch

from automation.decision_engine import InitiativeEngine
from config.settings import settings


def test_cooldown_blocks_repeated_suggestions():
    engine = InitiativeEngine()
    engine._last_suggestion_ts = time.time()  # acabou de sugerir agora
    resultado = engine.get_suggestion({"open_programs": ["spotify.exe"]})
    assert resultado is None


def test_agent_disabled_uses_fallback_heuristic():
    settings.set("agents_enabled", value=False)
    engine = InitiativeEngine()
    with patch("random.random", return_value=0.05):  # força entrar no 15%
        resultado = engine.get_suggestion({"open_programs": ["spotify.exe"]})
    assert resultado in engine._APP_SUGGESTIONS["spotify"]


def test_agent_low_confidence_uses_fallback_heuristic():
    settings.set("agents_enabled", value=True)
    try:
        engine = InitiativeEngine()
        with patch(
            "ai.agent_provider.agent_provider.ask_json",
            return_value={"sugestao": "algo pouco confiável", "confianca": 0.2},
        ), patch("random.random", return_value=0.05):
            resultado = engine.get_suggestion({"open_programs": ["spotify.exe"]})
        # 0.2 < 0.6 (limiar) — não usa a sugestão do agente, cai no fallback
        assert resultado in engine._APP_SUGGESTIONS["spotify"]
    finally:
        settings.set("agents_enabled", value=False)


def test_agent_confident_suggestion_is_used_and_sets_cooldown():
    settings.set("agents_enabled", value=True)
    try:
        engine = InitiativeEngine()
        with patch(
            "ai.agent_provider.agent_provider.ask_json",
            return_value={"sugestao": "Você está programando há 3 horas — que tal uma pausa?", "confianca": 0.85},
        ):
            resultado = engine.get_suggestion({"open_programs": ["code.exe"]})
        assert resultado == "Você está programando há 3 horas — que tal uma pausa?"
        # cooldown deve ter sido setado — chamada imediata seguinte bloqueia
        resultado2 = engine.get_suggestion({"open_programs": ["code.exe"]})
        assert resultado2 is None
    finally:
        settings.set("agents_enabled", value=False)


def test_agent_exception_falls_back_without_raising():
    settings.set("agents_enabled", value=True)
    try:
        engine = InitiativeEngine()
        with patch(
            "ai.agent_provider.agent_provider.ask_json",
            side_effect=Exception("ollama indisponível"),
        ), patch("random.random", return_value=0.9):  # fora do 15% -> None limpo
            resultado = engine.get_suggestion({"open_programs": ["spotify.exe"]})
        assert resultado is None  # não propaga exceção, só não sugere nada
    finally:
        settings.set("agents_enabled", value=False)


def test_no_open_apps_returns_none_via_fallback():
    settings.set("agents_enabled", value=False)
    engine = InitiativeEngine()
    with patch("random.random", return_value=0.05):
        resultado = engine.get_suggestion({"open_programs": []})
    assert resultado is None
