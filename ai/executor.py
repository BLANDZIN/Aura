"""
ai/executor.py — AURA V11
==========================
Executor de fluxos e despachante de intencoes do AIEngine.

Extraido de ai_engine.py (V11) para reduzir o tamanho do God Object.
Responsavel por: despachar intencoes, executar fluxos, gerenciar
correcoes de erro, salvar fluxos como atalhos.
"""
import time
from typing import Dict, List, Any, Optional

from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("ai.executor")


class FlowExecutor:
    """Despacha intencoes e fluxos entre o Planner e o FlowExecutor."""

    def __init__(self, ai_engine):
        self._engine = ai_engine

    def dispatch_intent(self, intent: Dict) -> None:
        """Despacha uma unica intencao pelo Planner."""
        from automation.planner import planner
        from automation.flow_executor import flow_executor
        plan = planner.plan_from_intent(intent)
        if plan.is_simple():
            self._engine._emit("intent", intent)
        else:
            flow_executor.execute(plan)

    def dispatch_flow(self, steps: List[Dict], descricao: str = "") -> None:
        """Despacha um fluxo multi-etapa com otimizacao de contexto."""
        from automation.planner import planner
        from automation.flow_executor import flow_executor
        from automation.decision_engine import context_cache

        filtered = []
        skipped = []
        for step in steps:
            acao = step.get("acao", "")
            params = step.get("parametros", {})
            if acao == "abrir_programa":
                prog = params.get("programa", "").replace(".exe", "").lower()
                if context_cache.is_app_open(prog):
                    skipped.append(prog)
                    continue
            filtered.append(step)

        if skipped:
            logger.info(f"Fluxo: pulou {skipped} (ja aberto)")

        if not filtered:
            self._engine._emit("response", "Tudo ja esta aberto!")
            return

        plan = planner.plan_from_flow(filtered, descricao or f"{len(filtered)} etapas")
        self._engine._emit("response", f"Executando {len(filtered)} etapa(s)...")
        flow_executor.execute(plan)

    @staticmethod
    def flow_signature(steps: List[Dict]) -> str:
        """Gera identificador estavel para um fluxo baseado nas acoes."""
        acoes = [s.get("acao", "?") for s in steps]
        return "+".join(acoes)[:60]

    def save_last_as_flow(self, steps: List[Dict], user_input: str,
                          save_request_text: str) -> str:
        """Salva o ultimo fluxo como atalho na FlowLibrary."""
        if not steps:
            return "Nao executei nada ainda. Peca uma acao primeiro."
        try:
            from automation.flow_library import flow_library
            nome = self._engine._extract_flow_name(save_request_text, user_input)
            flow_library.save(
                nome=nome, passos=steps,
                descricao=user_input[:100], importancia=8
            )
            logger.info(f"Fluxo salvo: '{nome}' ({len(steps)} passo(s))")
            return f"Salvei como '{nome}'! Da proxima vez e so pedir."
        except Exception as e:
            logger.error(f"Erro ao salvar fluxo: {e}")
            return "Tive um problema ao salvar, mas vou lembrar."

    def register_success(self, flow_name: str, passos: List[Dict],
                         user_input: str, t_exec: float):
        """Registra sucesso na Reflexao e no LearningEngine."""
        from automation.decision_engine import reflection_engine
        reflection_engine.reflect(
            flow_name=flow_name, passos=passos, sucesso=True,
            tempo_s=t_exec, objetivo=user_input,
        )
        try:
            if self._engine._learning:
                self._engine._learning.register_success(user_input, flow_name)
        except Exception:
            pass
