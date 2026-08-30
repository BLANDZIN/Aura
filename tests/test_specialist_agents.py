from ai.agents.coordinator import SpecialistCoordinator
from ai.prompt_builder import build_system_message


class _SlowSpecialist:
    name = "lento"

    def analyze(self, *args, **kwargs):
        import time
        time.sleep(0.2)
        return []


class _FakeEmotion:
    def get_profile(self):
        return {"estado": "curiosa", "energia": 0.6}


class _FakeLearning:
    def get_affinity(self):
        return 72.5

    def detect_positive_signal(self, text):
        return "perfeito" in text.lower()

    def stats(self):
        return {"correcoes_aprendidas": 2}


def test_specialist_coordinator_returns_compact_context():
    coordinator = SpecialistCoordinator(budget_ms=50.0)
    report = coordinator.analyze(
        "perfeito aura, abre o chrome e depois cria uma nova aba",
        context={"active_window": "VS Code", "open_programs": ["Chrome"]},
        emotion=_FakeEmotion(),
        learning=_FakeLearning(),
    )

    block = report.prompt_block()
    assert "SINAIS DOS ESPECIALISTAS V12.2" in block
    assert "emocao/estado" in block
    assert "acao/multi_etapa" in block
    assert "aprendizado/reforco_positivo" in block


def test_specialist_coordinator_has_time_budget():
    coordinator = SpecialistCoordinator(specialists=[_SlowSpecialist()], budget_ms=5.0)
    report = coordinator.analyze("teste", context={})

    assert report.timed_out is True
    assert report.elapsed_ms < 80


def test_specialist_context_reaches_system_prompt():
    class _FakePersonality:
        def build_system_prompt(self, tools_catalog=""):
            return "PROMPT BASE"

    class _FakeMemory:
        def build_relevant_context(self):
            return ""

    class _FakeToolManager:
        def build_tools_catalog(self, compact=True):
            return ""

    msg = build_system_message(
        personality=_FakePersonality(),
        memory=_FakeMemory(),
        tool_manager=_FakeToolManager(),
        specialist_context="SINAIS DOS ESPECIALISTAS V12.2:\n- teste",
    )

    assert "SINAIS DOS ESPECIALISTAS V12.2" in msg["content"]
