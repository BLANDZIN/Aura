"""
ai/agents/coordinator.py - AURA V12.2
=====================================
Coordinator for small deterministic specialist agents.

The goal is not to create more LLM calls. Each specialist is a fast observer
that reads the current turn/context and returns a compact signal. The main
AIEngine remains the only authority that decides or executes actions.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
import time
from typing import Any, Dict, Iterable, List, Optional

from core.event_bus import bus
from core.logger import setup_logger
from core.text_utils import normalize

logger = setup_logger("specialist_agents")


@dataclass(frozen=True)
class AgentInsight:
    """One compact observation from a specialist agent."""

    agent: str
    kind: str
    confidence: float
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentReport:
    """Aggregated specialist analysis for one user turn."""

    insights: List[AgentInsight]
    elapsed_ms: float
    timed_out: bool = False

    def by_agent(self, agent_name: str) -> List[AgentInsight]:
        return [i for i in self.insights if i.agent == agent_name]

    def prompt_block(self, max_items: int = 6) -> str:
        if not self.insights:
            return ""
        lines = ["SINAIS DOS ESPECIALISTAS V12.2:"]
        for insight in self.insights[:max_items]:
            pct = int(max(0.0, min(1.0, insight.confidence)) * 100)
            lines.append(
                f"- {insight.agent}/{insight.kind} ({pct}%): {insight.summary}"
            )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "elapsed_ms": round(self.elapsed_ms, 2),
            "timed_out": self.timed_out,
            "insights": [
                {
                    "agent": i.agent,
                    "kind": i.kind,
                    "confidence": i.confidence,
                    "summary": i.summary,
                    "data": dict(i.data),
                }
                for i in self.insights
            ],
        }


class BaseSpecialist:
    name = "base"

    def analyze(
        self,
        user_input: str,
        *,
        normalized: str,
        context: Dict[str, Any],
        emotion=None,
        learning=None,
    ) -> Iterable[AgentInsight]:
        return ()


class EmotionSpecialist(BaseSpecialist):
    name = "emocao"

    _AFFECTION = (
        "te amo", "amo voce", "adoro voce", "gosto de voce",
        "meu amor", "minha vida", "meu bem",
    )
    _IDENTITY = (
        "voce tem sentimentos", "voce sente", "voce e real",
        "voce e consciente", "voce e so uma ia", "voce existe de verdade",
    )
    _TENSION = (
        "voce errou", "nao era isso", "deu errado", "esta errado",
        "ficou ruim", "nao funcionou", "bug", "travou",
    )

    def analyze(self, user_input: str, *, normalized: str, context: Dict[str, Any],
                emotion=None, learning=None) -> Iterable[AgentInsight]:
        if emotion:
            profile = emotion.get_profile()
            yield AgentInsight(
                self.name,
                "estado",
                0.95,
                f"estado atual {profile.get('estado', 'calma')}; ajustar tom, nao a acao",
                {"profile": profile},
            )

        if any(t in normalized for t in self._AFFECTION):
            yield AgentInsight(
                self.name,
                "afeto",
                0.90,
                "usuario sinalizou afeto; responder com identidade da AURA e naturalidade",
            )
        if any(t in normalized for t in self._IDENTITY):
            yield AgentInsight(
                self.name,
                "identidade",
                0.88,
                "tema de identidade/sentimentos; nao responder como chatbot generico",
            )
        if any(t in normalized for t in self._TENSION):
            yield AgentInsight(
                self.name,
                "tensao",
                0.86,
                "possivel frustracao do usuario; priorizar clareza, correcao e pouco floreio",
            )


class VisionSpecialist(BaseSpecialist):
    name = "visao"

    def analyze(self, user_input: str, *, normalized: str, context: Dict[str, Any],
                emotion=None, learning=None) -> Iterable[AgentInsight]:
        active = (context.get("active_window") or "").strip()
        if active:
            yield AgentInsight(
                self.name,
                "janela_ativa",
                0.85,
                f"janela ativa detectada: {active[:80]}",
                {"active_window": active},
            )

        open_programs = context.get("open_programs") or []
        if open_programs:
            yield AgentInsight(
                self.name,
                "apps_abertos",
                0.78,
                "apps abertos podem evitar reabrir programas ja ativos",
                {"open_programs": list(open_programs)[:10]},
            )

        clipboard = (context.get("clipboard") or "").strip()
        if clipboard and any(w in normalized for w in ("clipboard", "copiado", "colado", "cola", "colar")):
            yield AgentInsight(
                self.name,
                "clipboard",
                0.82,
                "pedido parece depender do clipboard atual",
                {"clipboard_preview": clipboard[:120]},
            )


class ActionSpecialist(BaseSpecialist):
    name = "acao"

    _MULTI_HINTS = (" e ", " depois ", " em seguida ", " apos ", "após")
    _RISK_HINTS = ("delete", "exclua", "apague", "remova", "format", "limpa")

    def analyze(self, user_input: str, *, normalized: str, context: Dict[str, Any],
                emotion=None, learning=None) -> Iterable[AgentInsight]:
        if any(h in f" {normalized} " for h in self._MULTI_HINTS):
            yield AgentInsight(
                self.name,
                "multi_etapa",
                0.76,
                "pedido pode conter varias etapas; preferir plano estruturado quando houver acao",
            )

        if any(h in normalized for h in self._RISK_HINTS):
            yield AgentInsight(
                self.name,
                "risco",
                0.90,
                "acao potencialmente destrutiva; confirmar antes de executar se parametros forem ambiguos",
            )

        if len(normalized.split()) <= 4:
            yield AgentInsight(
                self.name,
                "curto",
                0.65,
                "entrada curta; usar atalhos deterministico/contextuais antes do modelo",
            )


class LearningSpecialist(BaseSpecialist):
    name = "aprendizado"

    def analyze(self, user_input: str, *, normalized: str, context: Dict[str, Any],
                emotion=None, learning=None) -> Iterable[AgentInsight]:
        if not learning:
            return ()

        affinity = learning.get_affinity()
        yield AgentInsight(
            self.name,
            "afinidade",
            0.82,
            f"afinidade atual {affinity:.1f}/100; usar para calibrar espontaneidade",
            {"affinity": affinity},
        )

        if learning.detect_positive_signal(user_input):
            yield AgentInsight(
                self.name,
                "reforco_positivo",
                0.90,
                "mensagem contem reforco positivo; registrar aprendizado e manter resposta natural",
            )

        try:
            stats = learning.stats()
            if stats.get("correcoes_aprendidas", 0) > 0:
                yield AgentInsight(
                    self.name,
                    "correcoes",
                    0.72,
                    "existem correcoes aprendidas; decision engine deve consultar antes do modelo",
                    {"correcoes_aprendidas": stats.get("correcoes_aprendidas", 0)},
                )
        except Exception:
            return ()


class SpecialistCoordinator:
    """Runs specialists under a strict time budget."""

    def __init__(
        self,
        specialists: Optional[List[BaseSpecialist]] = None,
        budget_ms: float = 35.0,
    ):
        self.specialists = specialists or [
            EmotionSpecialist(),
            VisionSpecialist(),
            ActionSpecialist(),
            LearningSpecialist(),
        ]
        self.budget_ms = budget_ms

    def analyze(
        self,
        user_input: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        emotion=None,
        learning=None,
    ) -> AgentReport:
        start = time.perf_counter()
        normalized = normalize(user_input)
        context = context or {}
        insights: List[AgentInsight] = []
        timed_out = False

        def _run(specialist: BaseSpecialist) -> List[AgentInsight]:
            try:
                return list(
                    specialist.analyze(
                        user_input,
                        normalized=normalized,
                        context=context,
                        emotion=emotion,
                        learning=learning,
                    )
                )
            except Exception as exc:
                logger.debug(f"Especialista {specialist.name} falhou: {exc}")
                return []

        timeout_s = max(0.001, self.budget_ms / 1000.0)
        pool = ThreadPoolExecutor(max_workers=len(self.specialists))
        futures = [pool.submit(_run, specialist) for specialist in self.specialists]
        try:
            for future in futures:
                remaining = timeout_s - (time.perf_counter() - start)
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    insights.extend(future.result(timeout=remaining))
                except TimeoutError:
                    timed_out = True
                    break
        finally:
            for future in futures:
                if not future.done():
                    future.cancel()
            pool.shutdown(wait=False, cancel_futures=True)

        insights.sort(key=lambda i: i.confidence, reverse=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        report = AgentReport(insights=insights, elapsed_ms=elapsed_ms, timed_out=timed_out)

        try:
            bus.publish("agents.report", report=report.to_dict())
        except Exception:
            pass

        if timed_out:
            logger.debug(f"Especialistas excederam orcamento de {self.budget_ms:.0f}ms")
        else:
            logger.debug(f"Especialistas concluiram em {elapsed_ms:.1f}ms")

        return report


specialist_coordinator = SpecialistCoordinator()
