"""
angela/autoengineering.py
Gatilhos automáticos.

Quando a AURA detecta problemas recorrentes (exceções repetidas,
falhas em ferramentas, regressões, baixa confiança, queda de
desempenho), este módulo agrupa os sinais e dispara uma investigação
da Angela sem intervenção do usuário.

Design:
  - Sinal chega via bus.publish("aura.problem", kind=..., detail=...)
  - Contador por `kind` é incrementado
  - Se ultrapassar threshold em janela recente, publica NEEDS_ANGELA
  - Angela investiga em background e AURA depois apresenta ao usuário
"""

from collections import deque
from dataclasses import dataclass
from time import monotonic
from typing import Deque, Dict, Tuple

from core.event_bus import bus
from core.logger import setup_logger
from angela.communication import Topics

logger = setup_logger("angela.auto")


@dataclass
class AutoConfig:
    window_seconds: float = 300.0     # janela deslizante de 5 min
    threshold: int = 3                # 3 ocorrências → dispara Angela


class AutoEngineeringTrigger:
    """Escuta 'aura.problem' e dispara a Angela quando necessário."""

    def __init__(self, config: AutoConfig = AutoConfig()):
        self._cfg = config
        self._events: Dict[str, Deque[float]] = {}
        self._active = False

    def start(self) -> None:
        if self._active:
            return
        bus.subscribe("aura.problem", self._on_problem)
        self._active = True
        logger.info("AutoEngineering ligada.")

    def stop(self) -> None:
        if not self._active:
            return
        bus.unsubscribe("aura.problem", self._on_problem)
        self._active = False

    # ── interno ──────────────────────────────────────────────────────
    def _on_problem(self, kind: str, detail: str = "", **_) -> None:
        now = monotonic()
        dq = self._events.setdefault(kind, deque())
        dq.append(now)
        # purga janela
        while dq and now - dq[0] > self._cfg.window_seconds:
            dq.popleft()

        if len(dq) >= self._cfg.threshold:
            logger.warning(
                f"Threshold atingido para '{kind}' "
                f"({len(dq)} em {self._cfg.window_seconds}s). "
                "Solicitando análise da Angela."
            )
            dq.clear()   # reset para não disparar em loop
            bus.publish(
                Topics.NEEDS_ANGELA,
                request=f"Auto-triagem: '{kind}' recorrente. Último detalhe: {detail}",
                source="autoengineering",
                kind=kind,
            )
