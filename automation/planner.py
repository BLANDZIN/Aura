"""
automation/planner.py
Planejador de Execução do AURA — v2.beta

Fluxo:
  Usuário → LLM → Planner → Plano → FlowExecutor → Ferramentas

O Planner recebe a intenção bruta da IA e a converte em um plano
estruturado de etapas, com timeouts, retries e condicionais.

Também detecta planos simples (1 ação) e os executa diretamente,
sem overhead desnecessário.
"""

import json
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from core.logger import setup_logger
from core.event_bus import bus

logger = setup_logger("planner")


@dataclass
class Step:
    """Uma etapa do plano de execução."""
    acao:       str
    parametros: Dict[str, Any]        = field(default_factory=dict)
    descricao:  str                   = ""
    timeout:    float                 = 30.0      # segundos
    retries:    int                   = 0
    esperar:    float                 = 0.0        # segundos após executar
    condicao:   Optional[str]         = None       # "se_sucesso" | "se_erro" | None
    confirmacao_necessaria: bool      = False


@dataclass
class Plan:
    """Plano completo de execução com N etapas."""
    descricao:  str
    steps:      List[Step]  = field(default_factory=list)
    origem:     str         = "llm"    # "llm" | "procedimento" | "usuario"
    proc_nome:  str         = ""       # nome do procedimento se vier da memória

    def __len__(self):
        return len(self.steps)

    def is_simple(self) -> bool:
        """Plano simples = 1 ação sem espera, sem retry, sem condição."""
        return len(self.steps) == 1 and self.steps[0].esperar == 0


class Planner:
    """
    Converte intenções da IA em planos de execução estruturados.

    Responsabilidades:
    1. Receber intent da IA (acao + parametros) ou lista de acoes (fluxo)
    2. Verificar memória de procedimentos antes de planejar
    3. Construir Plan com Steps validados
    4. Publicar plano no EventBus para o FlowExecutor
    """

    def __init__(self):
        # Importação lazy para evitar circular
        self._proc_memory = None

    def _get_proc_memory(self):
        if self._proc_memory is None:
            from memory.memory_manager import memory
            self._proc_memory = memory.procedural
        return self._proc_memory

    def plan_from_intent(self, intent: Dict[str, Any]) -> Plan:
        """
        Cria plano a partir de uma única intenção da IA.
        Verifica se há um procedimento salvo com esse nome antes.
        """
        acao = intent.get("acao", "")

        # 1. Verifica se é uma chamada de procedimento salvo
        proc = self._get_proc_memory().get(acao)
        if proc:
            return self._plan_from_procedure(proc)

        # 2. Plano de ação única
        step = Step(
            acao=acao,
            parametros=intent.get("parametros", {}),
            descricao=intent.get("mensagem", acao),
            confirmacao_necessaria=intent.get("confirmacao_necessaria", False),
        )
        return Plan(descricao=intent.get("mensagem", acao), steps=[step])

    def plan_from_flow(self, flow: List[Dict[str, Any]], descricao: str = "") -> Plan:
        """
        Cria plano a partir de uma lista de ações (fluxo completo).
        Usado quando a IA retorna múltiplas ações ou ao executar procedimentos.
        """
        steps = []
        for item in flow:
            steps.append(Step(
                acao=item.get("acao", ""),
                parametros=item.get("parametros", {}),
                descricao=item.get("descricao", item.get("acao", "")),
                timeout=item.get("timeout", 30.0),
                retries=item.get("retries", 0),
                esperar=item.get("esperar", 0.0),
                condicao=item.get("condicao"),
                confirmacao_necessaria=item.get("confirmacao_necessaria", False),
            ))
        return Plan(descricao=descricao or f"Fluxo com {len(steps)} etapas", steps=steps)

    def _plan_from_procedure(self, proc: Dict) -> Plan:
        """Converte procedimento salvo na memória em plano de execução."""
        passos = proc.get("passos", [])
        steps  = []
        for passo in passos:
            if isinstance(passo, str):
                # Passo em texto livre — envolve em uma ação de log
                steps.append(Step(acao="__log__", parametros={"mensagem": passo}, descricao=passo))
            elif isinstance(passo, dict):
                steps.append(Step(
                    acao=passo.get("acao", ""),
                    parametros=passo.get("parametros", {}),
                    descricao=passo.get("descricao", ""),
                    esperar=passo.get("esperar", 0.0),
                    retries=passo.get("retries", 0),
                ))
        nome = proc.get("nome", "procedimento")
        self._get_proc_memory().increment_usage(nome)
        return Plan(descricao=f"Procedimento: {nome}", steps=steps, origem="procedimento", proc_nome=nome)

    def parse_llm_response(self, response: str) -> Optional[Plan]:
        """
        Tenta extrair um plano multi-ação da resposta da IA.
        A IA pode retornar:
        1. JSON único {"acao": ...}
        2. JSON array [{"acao": ...}, {"acao": ...}]
        3. JSON com "fluxo": [...]
        """
        text = response.strip()

        # Tenta array de ações
        arr_match = re.search(r"\[(\s*\{.*?\}\s*,?\s*)+\]", text, re.DOTALL)
        if arr_match:
            try:
                flow = json.loads(arr_match.group(0))
                if isinstance(flow, list) and all("acao" in f for f in flow):
                    return self.plan_from_flow(flow, "Fluxo multi-ação")
            except Exception:
                pass

        # Tenta objeto com campo "fluxo"
        obj_match = re.search(r"\{.*?\"fluxo\".*?\}", text, re.DOTALL)
        if obj_match:
            try:
                data = json.loads(obj_match.group(0))
                if "fluxo" in data:
                    return self.plan_from_flow(data["fluxo"], data.get("descricao", ""))
            except Exception:
                pass

        return None



    # V12.1 — Prioridade 4: `resolve()` foi removido daqui (auditoria
    # confirmou, por grep, que nada o chamava — código morto real, não
    # hipotético). NÃO foi só apagado às cegas: comparei contra o
    # dispatch de verdade em ai/ai_engine.py::process()._run() antes de
    # decidir, e ele tinha duas lacunas reais que o tornariam uma troca
    # de comportamento, não uma consolidação neutra:
    #   1. Não chamava decision_engine.evaluate_confidence() — perderia
    #      o "ask_user" quando a confiança da decisão é baixa.
    #   2. Não replicava a filtragem de apps já abertos que
    #      ai/executor.py::FlowExecutor._dispatch_flow() faz via
    #      context_cache antes de montar o plano.
    # Consolidar o dispatch aqui de verdade (objetivo genuíno, alinhado
    # com a Prioridade 7 de continuar reduzindo o AIEngine) exige trazer
    # essas duas partes junto e trocar o call site do loop de decisão
    # mais crítico do sistema — risco real de regressão silenciosa sem
    # um LLM de verdade pra testar contra. Fica como próximo passo
    # deliberado, não como esquecimento.

# Instância global
planner = Planner()
