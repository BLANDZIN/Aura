import time

from core.metrics import MetricsRegistry, timed


def test_record_and_summary():
    m = MetricsRegistry()
    m.record("tool", "abrir_programa", 12.5)
    m.record("tool", "abrir_programa", 7.5)
    s = m.summary()
    assert s["tool"]["abrir_programa"]["count"] == 2
    assert s["tool"]["abrir_programa"]["avg_ms"] == 10.0
    assert s["tool"]["abrir_programa"]["min_ms"] == 7.5
    assert s["tool"]["abrir_programa"]["max_ms"] == 12.5


def test_timer_context_manager_records_real_elapsed_time():
    m = MetricsRegistry()
    with m.timer("tool", "esperar"):
        time.sleep(0.02)
    s = m.summary()
    assert s["tool"]["esperar"]["count"] == 1
    assert s["tool"]["esperar"]["avg_ms"] >= 15  # tolera jitter, mas tem que ser tempo real


def test_timed_decorator_records_even_on_exception():
    m = MetricsRegistry()

    class Fake:
        model = "qwen-teste"

        @staticmethod
        def _decorate(func):
            return timed("model", name_fn=lambda self: self.model)(func)

    # aplica o decorator manualmente contra o registro isolado 'm'
    # (o decorator real usa o singleton global 'metrics' — aqui testamos
    # a mecânica against um registro isolado via monkeypatch do módulo)
    import core.metrics as metrics_module
    original = metrics_module.metrics
    metrics_module.metrics = m
    try:
        class Provider:
            model = "qwen-teste"

            @timed("model", name_fn=lambda self: self.model)
            def chat(self):
                raise ValueError("erro simulado")

        p = Provider()
        try:
            p.chat()
        except ValueError:
            pass
    finally:
        metrics_module.metrics = original

    s = m.summary()
    assert s["model"]["qwen-teste"]["count"] == 1  # registrou mesmo com exceção


def test_summary_separates_aura_and_angela_models():
    m = MetricsRegistry()
    m.record("model", "qwen2.5:3b", 500)   # AURA
    m.record("model", "qwen3:4b", 3000)    # Angela
    s = m.summary()
    assert "qwen2.5:3b" in s["model"]
    assert "qwen3:4b" in s["model"]
    assert s["model"]["qwen2.5:3b"]["avg_ms"] != s["model"]["qwen3:4b"]["avg_ms"]


def test_to_markdown_empty_and_populated():
    m = MetricsRegistry()
    assert "Nenhuma amostra" in m.to_markdown()
    m.record("eventbus", "tool.result", 1.2)
    md = m.to_markdown()
    assert "eventbus" in md
    assert "tool.result" in md


def test_p95_uses_recent_window():
    m = MetricsRegistry()
    for i in range(10):
        m.record("tool", "x", float(i))
    s = m.summary()
    assert s["tool"]["x"]["count"] == 10
    assert 0 <= s["tool"]["x"]["p95_ms"] <= 9
