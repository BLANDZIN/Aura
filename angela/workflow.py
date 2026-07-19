"""
angela/workflow.py
Máquina de estados do processo obrigatório de 12 passos.

Este arquivo existe para que a sequência NUNCA seja quebrada:
qualquer investigação da Angela obrigatoriamente passa por cada etapa
(mesmo que trivial), e cada etapa emite evento no EventBus para que
AURA/UI acompanhem o progresso em tempo real.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("angela.workflow")


class Step(str, Enum):
    RECEIVE       = "receive"
    READ_FILES    = "read_files"
    READ_ARCH     = "read_architecture"
    READ_HISTORY  = "read_history"
    READ_LOGS     = "read_logs"
    ROOT_CAUSE    = "root_cause"
    HYPOTHESES    = "hypotheses"
    COMPARE       = "compare_solutions"
    CHOOSE        = "choose_solution"
    TEST          = "run_tests"
    REPORT        = "generate_report"
    ASK_APPLY     = "ask_to_apply"


ORDER: List[Step] = [
    Step.RECEIVE, Step.READ_FILES, Step.READ_ARCH, Step.READ_HISTORY,
    Step.READ_LOGS, Step.ROOT_CAUSE, Step.HYPOTHESES, Step.COMPARE,
    Step.CHOOSE, Step.TEST, Step.REPORT, Step.ASK_APPLY,
]


@dataclass
class StepContext:
    """Estado compartilhado entre etapas de um único workflow."""
    request: str
    data: Dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class Workflow:
    """
    Executa a sequência obrigatória. Se uma etapa não for implementada,
    ela é apenas registrada como no-op — mas nunca pulada.
    """

    def __init__(self, handlers: Dict[Step, Callable[[StepContext], None]]):
        self._handlers = handlers

    def run(self, request: str) -> StepContext:
        ctx = StepContext(request=request)
        for step in ORDER:
            bus.publish("angela.step", step=step.value, request=request)
            logger.info(f"[workflow] {step.value}")
            handler = self._handlers.get(step)
            if handler is None:
                logger.debug(f"  (no-op) {step.value}")
                continue
            try:
                handler(ctx)
            except Exception as e:
                # Uma etapa que falhou não pode interromper o processo;
                # ela vira evidência no relatório.
                logger.exception(f"Falha na etapa {step.value}: {e}")
                ctx.data.setdefault("_errors", []).append(
                    {"step": step.value, "error": str(e)}
                )
        return ctx
