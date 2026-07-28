"""
automation/flow_executor.py
Executor de Fluxos do AURA — v2.beta

Recebe um Plan do Planner e executa cada Step em sequência.
Cada etapa pode ter timeout, retries, espera e condicionais.

Publica eventos no EventBus a cada etapa para atualizar a UI.
Registra o histórico de execução no banco para aprendizado futuro.
"""

import time
import json
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from automation.planner import Plan, Step
from core.event_bus import bus
from core.logger import setup_logger
from core.metrics import metrics
from database.db_manager import db

logger = setup_logger("flow_executor")


REQUIRES_CONFIRM_FALLBACK = {
    "excluir_arquivo", "fechar_programa", "digitar_texto", "clicar_mouse",
}


@dataclass
class StepResult:
    acao:     str
    sucesso:  bool
    mensagem: str
    resultado: Any  = None
    duracao:   float = 0.0
    tentativas: int  = 1


@dataclass
class FlowResult:
    plan_descricao: str
    steps_total:    int
    steps_ok:       int
    steps_fail:     int
    resultados:     List[StepResult] = field(default_factory=list)
    abortado:       bool = False
    duracao_total:  float = 0.0

    @property
    def sucesso(self) -> bool:
        return not self.abortado and self.steps_fail == 0


class FlowExecutor:
    """
    Executa planos de ação passo a passo.

    Publica:
      flow.started    — início do fluxo
      flow.step       — a cada etapa (n, total, acao, status)
      flow.done       — conclusão com resultado completo
      flow.aborted    — se o fluxo for interrompido
    """

    def __init__(self):
        self._running = False
        self._abort   = False

    # ── API pública ───────────────────────────────────────────────────────────

    def execute(self, plan: Plan, async_mode: bool = True) -> None:
        """Executa o plano. async_mode=True roda em thread daemon."""
        if self._running:
            logger.warning("FlowExecutor: já existe um fluxo em execução")
            bus.publish("flow.error", mensagem="Aguarde o fluxo atual terminar")
            return

        if async_mode:
            threading.Thread(target=self._run, args=(plan,), daemon=True).start()
        else:
            self._run(plan)

    def abort(self) -> None:
        """Aborta o fluxo em execução após a etapa atual."""
        if self._running:
            self._abort = True
            logger.info("FlowExecutor: abortar solicitado")

    # ── Execução interna ──────────────────────────────────────────────────────

    def _run(self, plan: Plan) -> None:
        from tools.tool_manager import tool_manager, normalize_params

        self._running = True
        self._abort   = False
        inicio        = time.time()
        resultados: List[StepResult] = []

        n_total = len(plan.steps)
        bus.publish("flow.started", descricao=plan.descricao, total=n_total)
        logger.info(f"Iniciando fluxo: '{plan.descricao}' ({n_total} etapa(s))")

        for idx, step in enumerate(plan.steps):
            if self._abort:
                logger.info(f"Fluxo abortado na etapa {idx+1}")
                bus.publish("flow.aborted", etapa=idx+1, total=n_total)
                break

            if self._step_requires_confirmation(step):
                logger.warning(
                    "Fluxo aguardando confirmacao antes de executar acao sensivel: %s",
                    step.acao,
                )
                intent = {
                    "acao": step.acao,
                    "parametros": step.parametros,
                    "mensagem": step.descricao or step.acao,
                    "confirmacao_necessaria": True,
                    "_flow_descricao": plan.descricao,
                }
                bus.publish("tool.confirm_required", intent=intent)
                bus.publish(
                    "flow.aborted",
                    etapa=idx+1,
                    total=n_total,
                    mensagem=f"Confirmacao necessaria para '{step.acao}'",
                )
                bus.publish(
                    "aura.problem",
                    kind="flow_confirmation_required",
                    detail=(
                        f"Fluxo '{plan.descricao}' pausado antes de "
                        f"'{step.acao}' porque a acao exige confirmacao."
                    ),
                )
                resultados.append(StepResult(
                    acao=step.acao,
                    sucesso=False,
                    mensagem="Confirmacao necessaria antes da execucao",
                ))
                break

            bus.publish("flow.step",
                        n=idx+1, total=n_total,
                        acao=step.acao,
                        descricao=step.descricao,
                        status="executando")

            result = self._execute_step(step, tool_manager, normalize_params)
            resultados.append(result)

            status = "ok" if result.sucesso else "erro"
            bus.publish("flow.step",
                        n=idx+1, total=n_total,
                        acao=step.acao,
                        descricao=step.descricao,
                        status=status,
                        mensagem=result.mensagem)

            # Para o fluxo se etapa crítica falhar (sem condicional de "continuar_em_erro")
            if not result.sucesso and step.condicao != "continuar_em_erro":
                logger.warning(f"Etapa {idx+1} falhou — interrompendo fluxo")
                bus.publish("flow.aborted",
                            etapa=idx+1, total=n_total,
                            mensagem=f"Falhou em '{step.acao}': {result.mensagem}")
                bus.publish("aura.problem", kind="flow_failure",
                            detail=f"Fluxo '{plan.descricao}' abortado em "
                                   f"'{step.acao}': {result.mensagem}")
                break

            # Espera configurada entre etapas
            if step.esperar > 0:
                logger.debug(f"Aguardando {step.esperar}s...")
                time.sleep(step.esperar)

        duracao = time.time() - inicio
        metrics.record("flow", plan.descricao, duracao * 1000)
        n_ok    = sum(1 for r in resultados if r.sucesso)
        n_fail  = sum(1 for r in resultados if not r.sucesso)

        flow_result = FlowResult(
            plan_descricao=plan.descricao,
            steps_total=n_total,
            steps_ok=n_ok,
            steps_fail=n_fail,
            resultados=resultados,
            abortado=self._abort,
            duracao_total=round(duracao, 2),
        )

        self._log_execution(plan, flow_result)

        # Registra resultado no context_manager
        try:
            from vision.context_manager import context_manager
            status = "concluído" if flow_result.sucesso else f"{flow_result.steps_fail} falha(s)"
            context_manager.register_action(
                f"fluxo:{plan.descricao[:40]}",
                status,
                flow_result.sucesso,
            )
        except Exception:
            pass

        bus.publish("flow.done", resultado=flow_result)
        self._running = False

        if flow_result.sucesso:
            logger.info(f"Fluxo concluído: {n_ok}/{n_total} etapas OK em {duracao:.1f}s")
        else:
            logger.warning(f"Fluxo finalizado com falhas: {n_fail} erro(s)")

    def _step_requires_confirmation(self, step: Step) -> bool:
        if step.confirmacao_necessaria:
            return True
        try:
            from tools.tool_manager import tool_manager
            required = getattr(tool_manager, "REQUIRES_CONFIRM", REQUIRES_CONFIRM_FALLBACK)
        except Exception:
            required = REQUIRES_CONFIRM_FALLBACK
        return step.acao in required

    def _execute_step(self, step: Step, tool_manager, normalize_params) -> StepResult:
        """Executa uma etapa com retry e timeout."""
        inicio     = time.time()
        tentativas = 0
        last_result = {"sucesso": False, "mensagem": "Não executado", "resultado": None}

        # Etapa especial de log (usada em procedimentos de texto livre)
        if step.acao == "__log__":
            msg = step.parametros.get("mensagem", "")
            logger.info(f"[PROC] {msg}")
            return StepResult(acao="__log__", sucesso=True, mensagem=msg,
                              duracao=0.0, tentativas=1)

        # Etapa de espera explícita
        if step.acao == "esperar":
            seg = float(step.parametros.get("segundos", 1.0))
            time.sleep(seg)
            return StepResult(acao="esperar", sucesso=True,
                              mensagem=f"Aguardei {seg}s", duracao=seg, tentativas=1)

        max_tentativas = max(1, step.retries + 1)

        for tentativa in range(max_tentativas):
            tentativas = tentativa + 1
            try:
                params   = normalize_params(step.acao, step.parametros)
                tool     = tool_manager._tools.get(step.acao)
                if not tool:
                    last_result = {"sucesso": False,
                                   "mensagem": f"Ferramenta '{step.acao}' não encontrada",
                                   "resultado": None}
                    break

                raw = tool.execute(params)
                last_result = raw

                if raw["sucesso"]:
                    break  # sucesso — não precisa retry

                if tentativa < max_tentativas - 1:
                    logger.debug(f"  Retry {tentativa+1}/{step.retries} para '{step.acao}'")
                    time.sleep(0.5 * (tentativa + 1))

            except Exception as e:
                logger.error(f"Exceção na etapa '{step.acao}': {e}")
                last_result = {"sucesso": False, "mensagem": str(e), "resultado": None}
                if tentativa < max_tentativas - 1:
                    time.sleep(0.5)

        return StepResult(
            acao=step.acao,
            sucesso=last_result.get("sucesso", False),
            mensagem=last_result.get("mensagem", ""),
            resultado=last_result.get("resultado"),
            duracao=round(time.time() - inicio, 3),
            tentativas=tentativas,
        )

    def _log_execution(self, plan: Plan, result: FlowResult) -> None:
        """Salva execução no banco para análise de padrões futura."""
        try:
            db.execute(
                """INSERT INTO action_log (acao, parametros, resultado, sucesso)
                   VALUES (?, ?, ?, ?)""",
                (
                    f"flow:{plan.descricao}",
                    json.dumps({"steps": len(plan.steps), "origem": plan.origem},
                               ensure_ascii=False),
                    json.dumps({
                        "ok": result.steps_ok,
                        "fail": result.steps_fail,
                        "duracao": result.duracao_total,
                    }, ensure_ascii=False),
                    int(result.sucesso),
                ),
            )
        except Exception as e:
            logger.error(f"Erro ao logar execução: {e}")

    @property
    def is_running(self) -> bool:
        return self._running


# Instância global
flow_executor = FlowExecutor()
