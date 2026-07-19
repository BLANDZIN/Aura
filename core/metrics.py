"""
core/metrics.py — Observabilidade (V10, Fase 7)

Coleta métricas de tempo REAIS (não estimativas) dos pontos do sistema
que fazem I/O ou trabalho significativo: modelo (AURA e Angela — cada
um aparece com o nome do próprio modelo, já que reutilizam o mesmo
OllamaProvider), ferramentas, EventBus, fluxos. Em memória, thread-safe,
sem dependência externa.

Tempo de teste não tem instrumentação própria aqui de propósito: o
pytest já mede isso nativamente (`pytest --durations=10`) — duplicar
seria exatamente o tipo de coisa que este projeto tenta evitar.

Uso:
    with metrics.timer("tool", "abrir_programa"):
        ...

    metrics.summary()          # dict agregado
    metrics.to_markdown()      # relatório legível (mesmo padrão de
                                # angela/report.py::to_markdown)
"""
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class _Stats:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    samples: List[float] = field(default_factory=list)  # janela recente, p/ p95

    def add(self, ms: float) -> None:
        self.count += 1
        self.total_ms += ms
        self.min_ms = min(self.min_ms, ms)
        self.max_ms = max(self.max_ms, ms)
        self.samples.append(ms)
        if len(self.samples) > 200:
            self.samples.pop(0)

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        idx = min(int(len(s) * 0.95), len(s) - 1)
        return s[idx]


class MetricsRegistry:
    """Registro global em memória. Thread-safe (várias ferramentas e o
    EventBus podem gravar de threads diferentes ao mesmo tempo)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stats: Dict[str, Dict[str, _Stats]] = defaultdict(lambda: defaultdict(_Stats))

    def record(self, category: str, name: str, duration_ms: float) -> None:
        with self._lock:
            self._stats[category][name].add(duration_ms)

    @contextmanager
    def timer(self, category: str, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(category, name, (time.perf_counter() - start) * 1000)

    def summary(self) -> Dict[str, Dict[str, Dict]]:
        with self._lock:
            return {
                cat: {
                    name: {
                        "count": s.count,
                        "avg_ms": round(s.avg_ms, 1),
                        "min_ms": round(s.min_ms, 1) if s.count else 0.0,
                        "max_ms": round(s.max_ms, 1),
                        "p95_ms": round(s.p95_ms, 1),
                    }
                    for name, s in names.items()
                }
                for cat, names in self._stats.items()
            }

    def to_markdown(self) -> str:
        summary = self.summary()
        if not summary:
            return "# Métricas\n\nNenhuma amostra coletada ainda nesta sessão."
        lines = ["# Métricas de desempenho (amostras reais desta sessão)\n"]
        for cat in sorted(summary):
            lines.append(f"## {cat}")
            lines.append("| Nome | Amostras | Média | p95 | Min | Max |")
            lines.append("|---|---:|---:|---:|---:|---:|")
            for name, s in sorted(summary[cat].items()):
                lines.append(
                    f"| {name} | {s['count']} | {s['avg_ms']}ms | "
                    f"{s['p95_ms']}ms | {s['min_ms']}ms | {s['max_ms']}ms |"
                )
            lines.append("")
        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


metrics = MetricsRegistry()


def timed(category: str, name_fn=None):
    """
    Decorator para instrumentar um método sem precisar reestruturar seu
    corpo (útil quando o método tem vários caminhos de retorno/exceção
    — envolver cada um em `with metrics.timer(...)` seria repetitivo e
    arriscado de manter sincronizado).

    name_fn(self) -> str decide o nome da métrica em tempo de chamada
    (ex.: lambda self: self.model, pra separar AURA de Angela mesmo
    usando a mesma classe OllamaProvider). Se omitido, usa o nome da
    própria função decorada.
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            name = name_fn(self) if name_fn else func.__name__
            start = time.perf_counter()
            try:
                return func(self, *args, **kwargs)
            finally:
                metrics.record(category, name, (time.perf_counter() - start) * 1000)
        return wrapper
    return decorator
