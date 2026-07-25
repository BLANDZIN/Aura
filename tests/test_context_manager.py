"""
Testes básicos para vision/context_manager.py — não existia nenhuma
cobertura antes (achado da revisão V12.1, Prioridade 10). Foca na API
que não depende de detalhes de SO específicos (register_action,
build_context_string) — _get_open_programs/_get_active_window já
degradam graciosamente por design (try/except retornando "" ou []),
então testar aqui só reforçaria esse comportamento sem valor real.
"""
from vision.context_manager import ContextManager


def test_register_action_keeps_only_last_5():
    cm = ContextManager.__new__(ContextManager)  # evita _collect() pesado no __init__
    cm._action_history = []
    for i in range(8):
        cm.register_action(f"acao_{i}", f"resultado_{i}", True)
    assert len(cm._action_history) == 5
    assert cm._action_history[-1]["acao"] == "acao_7"
    assert cm._action_history[0]["acao"] == "acao_3"


def test_build_context_string_includes_recent_actions():
    import threading
    cm = ContextManager.__new__(ContextManager)
    cm._lock = threading.Lock()
    cm._ctx = {"datetime": "24/07/2026 10:00:00 (sexta)"}
    cm._action_history = []
    cm.register_action("abrir_programa", "Spotify aberto", True)
    cm.register_action("pesquisar_web", "falha de rede", False)

    texto = cm.build_context_string()
    assert "abrir_programa" in texto
    assert "pesquisar_web" in texto
    assert "✓" in texto  # sucesso
    assert "✗" in texto  # falha


def test_build_context_string_empty_ctx_returns_empty():
    import threading
    cm = ContextManager.__new__(ContextManager)
    cm._lock = threading.Lock()
    cm._ctx = {}
    cm._action_history = []
    assert cm.build_context_string() == ""


def test_get_returns_a_copy_not_the_live_dict():
    cm = ContextManager.__new__(ContextManager)
    import threading
    cm._lock = threading.Lock()
    cm._ctx = {"cpu_percent": 10}
    snapshot = cm.get()
    snapshot["cpu_percent"] = 999
    assert cm._ctx["cpu_percent"] == 10  # não deve ter mudado o original
