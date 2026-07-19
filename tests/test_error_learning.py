import automation.error_learning  # garante que o singleton error_learner se inscreveu
from core.event_bus import bus


def test_tool_failure_publishes_aura_problem():
    received = []
    bus.subscribe("aura.problem", lambda **kw: received.append(kw))
    try:
        bus.publish("tool.result", sucesso=False, mensagem="falha X", resultado=None)
    finally:
        bus.clear("aura.problem")

    assert len(received) == 1
    assert received[0]["kind"] == "tool_failure"
    assert "falha X" in received[0]["detail"]


def test_tool_success_does_not_publish_aura_problem():
    received = []
    bus.subscribe("aura.problem", lambda **kw: received.append(kw))
    try:
        bus.publish("tool.result", sucesso=True, mensagem="ok", resultado=None)
    finally:
        bus.clear("aura.problem")

    assert received == []
