"""
automation/automation_learner.py
Aprendizado de Automações — v2.beta

Monitora ações executadas, detecta padrões repetidos e
sugere ao usuário salvar como procedimento reutilizável.

Fluxo:
  1. Cada ação executada é registrada no histórico de sessão
  2. Ao atingir threshold de repetição, sugere automação
  3. Se aceito, salva como procedimento na ProceduralMemory
"""

import json
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("learner")

# Quantas vezes um fluxo deve se repetir para sugerir automação
SUGGESTION_THRESHOLD = 3
# Janela de ações consideradas como "sequência" (últimas N)
SEQUENCE_WINDOW = 5


class AutomationLearner:
    """
    Aprende padrões de uso e sugere automações.

    Monitora os eventos 'tool.result' e detecta sequências repetidas.
    Quando uma sequência aparece >= SUGGESTION_THRESHOLD vezes, publica
    'automation.suggestion' para a UI apresentar ao usuário.
    """

    def __init__(self):
        # Histórico de ações desta sessão: lista de {acao, parametros, ts}
        self._history:     List[Dict]              = []
        # Contador de sequências: chave_sequencia → contagem
        self._seq_counts:  Dict[str, int]          = defaultdict(int)
        # Sequências já sugeridas (evita spam)
        self._suggested:   set                     = set()

        bus.subscribe("tool.result", self._on_tool_result)
        logger.info("AutomationLearner iniciado")

    def _on_tool_result(self, sucesso: bool, mensagem: str, resultado: Any) -> None:
        """Chamado após cada ferramenta executada com sucesso."""
        if not sucesso:
            return

        # A ação em andamento vem do log mais recente — recupera do bus context
        # Nota: como o bus não passa o nome da ação, usamos a última ação logada
        # via registro manual no _register_action()

    def register_action(self, acao: str, parametros: Dict) -> None:
        """
        Registra uma ação no histórico de aprendizado.
        Chamado pelo ToolManager após execução bem-sucedida.
        """
        self._history.append({
            "acao": acao,
            "parametros": parametros,
            "ts": datetime.now().isoformat(),
        })

        # Mantém histórico limitado
        if len(self._history) > 200:
            self._history = self._history[-200:]

        # Verifica sequências
        self._check_sequences()

    def _check_sequences(self) -> None:
        """Verifica se as últimas N ações formam uma sequência conhecida."""
        if len(self._history) < 2:
            return

        # Gera chave para últimas 2, 3 e 4 ações
        for window in [2, 3, 4]:
            if len(self._history) < window:
                continue
            seq = self._history[-window:]
            key = self._sequence_key(seq)

            self._seq_counts[key] += 1
            count = self._seq_counts[key]

            if count >= SUGGESTION_THRESHOLD and key not in self._suggested:
                self._suggested.add(key)
                self._suggest_automation(seq, count)

    def _sequence_key(self, seq: List[Dict]) -> str:
        """Gera uma chave única para uma sequência de ações."""
        return "|".join(item["acao"] for item in seq)

    def _suggest_automation(self, seq: List[Dict], count: int) -> None:
        """Publica sugestão de automação para a UI."""
        acoes = [item["acao"] for item in seq]
        descricao = " → ".join(acoes)
        logger.info(f"Sugerindo automação ({count}x): {descricao}")

        bus.publish(
            "automation.suggestion",
            sequencia=seq,
            descricao=descricao,
            contagem=count,
            mensagem=(
                f"Percebi que você fez '{descricao}' {count} vezes.\n"
                f"Deseja salvar como automação reutilizável?"
            ),
        )

    def save_as_procedure(self, nome: str, seq: List[Dict], descricao: str = "") -> None:
        """Salva uma sequência como procedimento na memória procedimental."""
        from memory.memory_manager import memory
        passos = [{"acao": item["acao"], "parametros": item["parametros"]} for item in seq]
        memory.procedural.save(
            nome=nome,
            descricao=descricao or f"Automação: {nome}",
            passos=passos,
            importance=7,
        )
        logger.info(f"Procedimento salvo: '{nome}' com {len(passos)} passo(s)")
        bus.publish("automation.saved", nome=nome, passos=len(passos))

    def get_stats(self) -> Dict:
        return {
            "acoes_sessao":    len(self._history),
            "sequencias_vistas": len(self._seq_counts),
            "sugestoes_feitas":  len(self._suggested),
            "top_sequencias": sorted(
                self._seq_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }


# Instância global
automation_learner = AutomationLearner()
