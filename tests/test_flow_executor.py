import sys
import types

import pytest


@pytest.fixture
def fake_tool_manager():
    """
    tools/tool_manager.py importa pyautogui (via control_tools), que
    exige um display e nem sempre está disponível. Injeta um stub
    mínimo com a forma exata que flow_executor.py usa — o que está sob
    teste aqui é o flow_executor (e o aura.problem que conectamos),
    não o tool_manager real.

    Importante: injeta e RESTAURA sys.modules depois do teste. Sem
    isso, o stub vaza pra sessão inteira do pytest e quebra qualquer
    outro teste que importe tools.tool_manager depois deste (achado
    real, não hipotético — foi descoberto rodando a suíte inteira).
    """
    fake = types.ModuleType("tools.tool_manager")
    fake.tool_manager = types.SimpleNamespace(_tools={})
    fake.normalize_params = lambda acao, params: params

    original = sys.modules.get("tools.tool_manager")
    sys.modules["tools.tool_manager"] = fake
    try:
        yield
    finally:
        if original is not None:
            sys.modules["tools.tool_manager"] = original
        else:
            sys.modules.pop("tools.tool_manager", None)


def test_flow_abort_publishes_aura_problem(fake_tool_manager):
    from automation.flow_executor import FlowExecutor
    from automation.planner import Plan, Step
    from core.event_bus import bus

    received = []
    bus.subscribe("aura.problem", lambda **kw: received.append(kw))
    bus.subscribe("flow.aborted", lambda **kw: None)  # evita warning de "sem subscriber"
    try:
        plan = Plan(
            descricao="fluxo de teste",
            steps=[Step(acao="__ferramenta_que_nao_existe__", parametros={})],
        )
        FlowExecutor().execute(plan, async_mode=False)
    finally:
        bus.clear("aura.problem")
        bus.clear("flow.aborted")

    assert len(received) == 1
    assert received[0]["kind"] == "flow_failure"
    assert "fluxo de teste" in received[0]["detail"]
