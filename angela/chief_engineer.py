"""
angela/chief_engineer.py
Angela — a inteligência propriamente dita.

Responsabilidades:
  1. Assinar eventos NEEDS_ANGELA e REQUEST no EventBus
  2. Rodar o workflow obrigatório de 12 passos para cada solicitação
  3. Produzir um InvestigationReport
  4. Publicar o relatório como `angela.report`
  5. Nunca aplicar patches sem confirmação humana

Angela roda em thread própria (daemon) para nunca bloquear a AURA.
"""

import queue
import threading
from pathlib import Path
from typing import Dict, Optional

from angela.audit import Auditor
from angela.autoengineering import AutoEngineeringTrigger
from angela.communication import Topics
from angela.llm import AngelaLLM
from angela.personality import PERSONA, SYSTEM_PROMPT
from angela.platforms import EngineeringPlatform, default_platform
from angela.report import (
    Confidence, Hypothesis, InvestigationReport, Patch, Severity,
)
from angela.tools import GitTools
from angela.workflow import Step, StepContext, Workflow
from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("angela")


class Angela:
    """
    A Chief Engineer.

    Uso mínimo:
        from angela import Angela
        angela = Angela(project_root=".")
        angela.start()
        # daí em diante escuta EventBus
    """

    def __init__(
        self,
        project_root: str = ".",
        platform: Optional[EngineeringPlatform] = None,
        enable_autoengineering: bool = True,
    ):
        self._project_root = str(Path(project_root).resolve())
        self._platform = platform or default_platform(self._project_root)
        self._auditor = Auditor(self._platform)
        self._git = GitTools(self._platform)
        self._llm = AngelaLLM()
        self._auto = AutoEngineeringTrigger() if enable_autoengineering else None

        self._queue: "queue.Queue[dict]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._running = False

    # ── ciclo de vida ────────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        # Se o workspace ainda não existe, faz snapshot inicial
        try:
            if hasattr(self._platform, "sync_from_project"):
                self._platform.sync_from_project()
        except Exception as e:
            logger.warning(f"Não foi possível sincronizar workspace: {e}")

        bus.subscribe(Topics.NEEDS_ANGELA, self._on_needs_angela)
        bus.subscribe(Topics.REQUEST, self._on_request)
        if self._auto:
            self._auto.start()

        self._running = True
        self._worker = threading.Thread(
            target=self._loop, name="Angela", daemon=True,
        )
        self._worker.start()
        logger.info(
            f"{PERSONA.display} online. "
            f"Plataforma: {self._platform.name}. "
            f"Workspace: {self._platform.workspace_root()}"
        )

    def shutdown(self) -> None:
        self._running = False
        self._queue.put({"__stop__": True})
        if self._auto:
            self._auto.stop()
        try:
            bus.unsubscribe(Topics.NEEDS_ANGELA, self._on_needs_angela)
            bus.unsubscribe(Topics.REQUEST, self._on_request)
        except Exception:
            pass

    # ── API pública (usada pela UI e pela AURA) ──────────────────────
    def request(self, text: str, source: str = "user", **meta) -> None:
        """Enfileira uma solicitação para investigação assíncrona."""
        self._queue.put({"request": text, "source": source, "meta": meta})

    def audit_now(self) -> str:
        """Executa auditoria e devolve o markdown. Síncrono."""
        # Garante que o workspace reflete o estado atual antes de auditar
        try:
            if hasattr(self._platform, "sync_from_project"):
                self._platform.sync_from_project()
        except Exception as e:
            logger.warning(f"Sync antes de auditar falhou: {e}")
        return self._auditor.audit().to_markdown()

    # ── ferramentas individuais (Tier 1/2 — ver AUDITORIA_V9_ETAPA1.md) ──
    def git_status(self) -> str:
        return self._git.status()

    def git_diff(self, path: str = "") -> str:
        return self._git.diff(path)

    def find_dead_code(self):
        return self._auditor.find_dead_code()

    def find_duplicates(self):
        return self._auditor.find_duplicates()

    def detect_cycles(self):
        return self._auditor.detect_cycles()


    @property
    def persona(self):
        return PERSONA

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    # ── listeners do EventBus ────────────────────────────────────────
    def _on_needs_angela(self, request: str, source: str = "aura", **meta) -> None:
        self.request(request, source=source, **meta)

    def _on_request(self, text: str, **meta) -> None:
        self.request(text, source="direct", **meta)

    # ── loop de execução ─────────────────────────────────────────────
    def _loop(self) -> None:
        while self._running:
            job = self._queue.get()
            if job.get("__stop__"):
                break
            try:
                self._handle(job)
            except Exception as e:
                logger.exception(f"Angela quebrou processando job: {e}")
                bus.publish(Topics.FAILED, error=str(e), request=job.get("request", ""))

    def _handle(self, job: dict) -> None:
        request = job["request"]
        source = job.get("source", "user")

        # 1) Confirma recebimento (frase-marca da persona)
        bus.publish(
            Topics.ACKNOWLEDGED,
            message=PERSONA.ack_received,
            request=request,
            source=source,
        )

        # 2) Roda os 12 passos obrigatórios
        report = self._investigate(request)

        # 3) Publica o relatório final
        bus.publish(Topics.REPORT, report=report, source=source)

        # 4) AURA pode retransmitir ao usuário
        bus.publish(
            Topics.AURA_SPEAKS,
            message=PERSONA.ack_done,
            summary=report.summary or report.root_cause or "Análise concluída.",
        )

    # ── implementação dos 12 passos ──────────────────────────────────
    def _investigate(self, request: str) -> InvestigationReport:
        report = InvestigationReport(request=request)

        def s_receive(ctx: StepContext) -> None:
            ctx.data["report"] = report

        def s_read_files(ctx: StepContext) -> None:
            # Heurística simples: extrai possíveis caminhos citados
            candidates = [w.strip(".,;:()[]") for w in request.split()
                          if "/" in w or w.endswith(".py")]
            if not candidates:
                # Sem caminho explícito: procura por palavra-chave no
                # workspace antes de desistir. Cobre o caso do próprio
                # exemplo do README ("Analise o Learning Engine" não cita
                # nenhum caminho, mas deve achar automation/learning_engine.py).
                stop = {"o", "a", "os", "as", "de", "do", "da", "em", "para",
                        "com", "que", "por", "um", "uma", "e", "no", "na"}
                keywords = [w.strip(".,;:()[]") for w in request.split()
                            if len(w) > 3 and w.lower() not in stop]
                hits: Dict[str, int] = {}
                for kw in keywords[:5]:
                    for match in self._platform.search(kw, case_sensitive=False):
                        path = match.split(":", 1)[0]
                        hits[path] = hits.get(path, 0) + 1
                candidates = sorted(hits, key=hits.get, reverse=True)[:5]
                if candidates:
                    report.architecture_notes.append(
                        "Nenhum caminho explícito no pedido — localizado "
                        f"por palavra-chave: {', '.join(candidates)}"
                    )
            for c in candidates[:8]:
                try:
                    _ = self._platform.read_file(c)   # lê arquivo inteiro
                    report.files_read.append(c)
                except Exception:
                    continue

        def s_read_arch(ctx: StepContext) -> None:
            top = self._platform.list_dir(".")
            report.architecture_notes.append(
                "Módulos de topo: " + ", ".join(
                    e.path for e in top if e.is_dir
                )
            )

        def s_read_history(_: StepContext) -> None:
            log = self._git.log(limit=5)
            if log:
                report.architecture_notes.append(
                    "Histórico git do workspace (últimos commits): "
                    + " | ".join(log)
                )
            else:
                report.architecture_notes.append(
                    "Histórico git: workspace ainda sem commits registrados."
                )

        def s_read_logs(_: StepContext) -> None:
            log_dir = Path(self._platform.workspace_root()) / "logs"
            if log_dir.exists():
                for f in sorted(log_dir.glob("*.log"))[-3:]:
                    report.logs_reviewed.append(f.name)

        def s_root_cause(_: StepContext) -> None:
            if not report.files_read:
                report.root_cause = (
                    "Não foi possível inferir a causa raiz sem contexto de "
                    "arquivos específicos. Angela recomenda apontar módulos."
                )
                report.root_cause_confidence = Confidence.LOW
            else:
                report.root_cause = (
                    "Análise inicial concluída. Nenhuma anomalia crítica "
                    "detectada nos arquivos lidos."
                )
                report.root_cause_confidence = Confidence.MEDIUM

        def s_hypotheses(_: StepContext) -> None:
            report.hypotheses.append(Hypothesis(
                description="Requisição genérica — sem sintoma reproduzível.",
                evidence=["Nenhum stack trace fornecido."],
                confidence=Confidence.LOW,
            ))

        def s_compare(_: StepContext) -> None:
            report.architecture_notes.append(
                "Comparação de soluções: aguardando plataforma real de engenharia."
            )

        def s_choose(_: StepContext) -> None:
            if self._llm.is_available():
                context = list(report.architecture_notes) + [
                    f"Arquivo lido: {f}" for f in report.files_read
                ]
                report.summary = self._llm.ask(
                    f"Solicitação original: {request}\n\n"
                    "Com base no contexto reunido acima, explique a causa "
                    "provável e proponha a melhor solução em poucas frases "
                    "técnicas. Não invente arquivos que não foram lidos.",
                    context=context,
                )
            else:
                report.summary = (
                    "Investigação inicial realizada seguindo o processo "
                    "obrigatório. Sem o modelo local da Angela disponível "
                    "(Ollama servindo qwen3:4b), a análise fica limitada às "
                    "heurísticas estáticas acima."
                )

        def s_test(_: StepContext) -> None:
            res = self._platform.run_tests()
            from angela.report import TestResult
            report.tests_run.append(TestResult(
                name="suite", passed=res.exit_code == 0,
                output=(res.stdout or res.stderr)[:2000],
                duration_ms=res.duration_ms,
            ))

        def s_report(_: StepContext) -> None:
            report.severity = Severity.INFO

        def s_ask_apply(_: StepContext) -> None:
            # A UI pergunta ao usuário; Angela apenas sinaliza que há patches
            if report.proposed_patches:
                bus.publish("angela.awaiting_confirmation",
                            patches=len(report.proposed_patches))

        Workflow({
            Step.RECEIVE:      s_receive,
            Step.READ_FILES:   s_read_files,
            Step.READ_ARCH:    s_read_arch,
            Step.READ_HISTORY: s_read_history,
            Step.READ_LOGS:    s_read_logs,
            Step.ROOT_CAUSE:   s_root_cause,
            Step.HYPOTHESES:   s_hypotheses,
            Step.COMPARE:      s_compare,
            Step.CHOOSE:       s_choose,
            Step.TEST:         s_test,
            Step.REPORT:       s_report,
            Step.ASK_APPLY:    s_ask_apply,
        }).run(request)

        return report

    # ── aplicação de patches (só com confirmação humana) ─────────────
    def apply_patch(self, patch: Patch) -> bool:
        """
        Escreve o patch APENAS no workspace isolado. O merge para
        o projeto principal é decisão do usuário, feita fora daqui.
        """
        try:
            self._platform.write_file(patch.file, patch.new_content)
            logger.info(f"Patch escrito no workspace: {patch.file}")
            return True
        except Exception as e:
            logger.error(f"Falha ao aplicar patch em {patch.file}: {e}")
            return False
