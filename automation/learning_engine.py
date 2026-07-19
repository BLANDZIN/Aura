"""
automation/learning_engine.py — AURA V6.1
============================================
Motor de Aprendizado Unificado — FACHADA, não reimplementação.

Correção de arquitetura (auditoria pós-V6):
  A versão anterior deste arquivo duplicava ~150 linhas de
  register_failure/check_correction/find_known_correction que já
  existiam em error_learning.py — nunca chamadas em produção,
  puro código morto competindo com o sistema real.

  Esta versão compõe os dois sistemas especializados existentes:
    - error_learning.ErrorLearner    -> aprendizado NEGATIVO (falha->correção)
    - automation_learner.AutomationLearner -> padrões por REPETIÇÃO
  e adiciona a camada que era genuinamente nova: afinidade, feedback
  positivo e níveis de confiança. Não há mais dois lugares para a
  mesma lógica de correção de erro.

Ciclo completo (agora com um único dono por responsabilidade):
  Erro     -> error_learner.register_failure()      [ErrorLearner]
  Correção -> error_learner.check_correction()       [ErrorLearner]
  Repetição-> automation_learner.register_action()   [AutomationLearner]
  Elogio   -> learning_engine.register_positive()    [aqui, novo]
  Cafuné   -> learning_engine.register_cafune()      [aqui, novo]

Desenvolvido por Bland | Claude
"""

import time
import random
from typing import Optional, Dict, Any
from database.db_manager import db
from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("learning")

# Incremento de confiança por evento positivo
CONF_DELTA_POSITIVE = 0.10

# Fontes de reforço positivo reconhecidas (word-boundary, evita falso
# positivo tipo "errou" casando substring de "funcionou")
POSITIVE_SIGNALS = (
    "obrigado","obrigada","valeu","brigado","brigada","muito obrigado",
    "perfeito","excelente","ótimo","otimo","muito bom","show","incrível",
    "incrivel","top","parabéns","parabens","adorei","amei","gostei",
    "funcionou","deu certo","certo","isso mesmo","exato","perfeita",
)


def _ensure_tables():
    """Garante que as tabelas de afinidade e confiança existem."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS learning_knowledge (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo         TEXT NOT NULL,
            chave        TEXT NOT NULL UNIQUE,
            valor_json   TEXT NOT NULL,
            confianca    REAL NOT NULL DEFAULT 0.55,
            uso_count    INTEGER NOT NULL DEFAULT 0,
            fonte        TEXT,
            criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS affinity_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            evento     TEXT,
            delta      REAL,
            total      REAL,
            criado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


class LearningEngine:
    """
    Fachada de aprendizado. NAO reimplementa error_learning nem
    automation_learner -- delega para eles e adiciona so o que e
    genuinamente novo: afinidade e reforco positivo com confianca.
    """

    def __init__(self):
        _ensure_tables()
        self._affinity: float = self._load_affinity()
        logger.info(f"LearningEngine iniciado (fachada) -- afinidade={self._affinity:.1f}")

    # -- Afinidade --------------------------------------------------------------

    def _load_affinity(self) -> float:
        try:
            row = db.fetchone(
                "SELECT total FROM affinity_log ORDER BY id DESC LIMIT 1"
            )
            return float(row["total"]) if row else 50.0
        except Exception:
            return 50.0

    def get_affinity(self) -> float:
        return round(self._affinity, 1)

    def register_affinity(self, evento: str, delta: float) -> float:
        self._affinity = max(0.0, min(100.0, self._affinity + delta))
        db.execute(
            "INSERT INTO affinity_log (evento, delta, total) VALUES (?,?,?)",
            (evento, delta, self._affinity)
        )
        logger.info(f"Afinidade: {evento} {delta:+.1f} -> {self._affinity:.1f}")
        return self._affinity

    def register_cafune(self) -> str:
        self.register_affinity("cafune", +3.0)
        respostas = [
            "Hm... *ronrona internamente* 😊",
            "Hehe, obrigada. Isso foi bom.",
            "Ei, continua que eu não vou reclamar.",
            "Aprecie. Raramente acontece.",
            "*aceita o cafuné com dignidade*",
            "Valeu. Tô carregando minha bateria de ânimo.",
        ]
        return random.choice(respostas)

    # -- Feedback positivo (novo -- nao existia em nenhum dos outros dois) ------

    def detect_positive_signal(self, text: str) -> bool:
        import re
        text_lower = text.lower()
        return any(
            re.search(r'\b' + re.escape(s) + r'\b', text_lower)
            for s in POSITIVE_SIGNALS
        )

    def register_positive(self, user_input: str, flow_name: str = "") -> None:
        """
        Registra feedback positivo. Aumenta afinidade sempre.
        Se um fluxo foi mencionado, tambem repassa o sucesso para a
        FlowLibrary (que ja tem seu proprio sistema de taxa_sucesso --
        nao duplicamos essa metrica aqui, so a acionamos).
        """
        self.register_affinity("elogio", +1.5)

        if flow_name:
            self._bump_confidence(flow_name, CONF_DELTA_POSITIVE)
            try:
                from automation.flow_library import flow_library
                if flow_library.get(flow_name):
                    flow_library.register_execution(
                        nome=flow_name, sucesso=True, tempo_s=0.0,
                        objetivo=user_input
                    )
            except Exception:
                pass
            logger.info(f"Reforço positivo: '{flow_name}' confiança +{CONF_DELTA_POSITIVE}")

    def register_success(self, user_input: str, acao: str, flow_name: str = "") -> None:
        """Sucesso silencioso (sem elogio explícito) -- incremento menor."""
        self._bump_confidence(flow_name or acao, 0.05)

    # -- Confianca (novo -- camada de generalizacao sobre conhecimento) ---------

    def _bump_confidence(self, chave: str, delta: float) -> None:
        if not chave:
            return
        existing = db.fetchone(
            "SELECT id, confianca FROM learning_knowledge WHERE chave=?", (chave,)
        )
        if existing:
            new_conf = min(1.0, max(0.0, existing["confianca"] + delta))
            db.execute(
                "UPDATE learning_knowledge SET confianca=?, uso_count=uso_count+1, "
                "atualizado_em=CURRENT_TIMESTAMP WHERE chave=?",
                (new_conf, chave)
            )
        else:
            db.execute(
                "INSERT INTO learning_knowledge (tipo, chave, valor_json, confianca, fonte) "
                "VALUES (?,?,?,?,?)",
                ("acao", chave, "{}", max(0.0, min(1.0, 0.55 + delta)), "auto")
            )

    def get_confidence(self, chave: str) -> float:
        row = db.fetchone(
            "SELECT confianca FROM learning_knowledge WHERE chave=?", (chave,)
        )
        return float(row["confianca"]) if row else 0.0

    # -- Delegacao explicita para os sistemas especializados ---------------------
    # Mantidas como metodos de conveniencia para quem so conhece
    # `learning_engine` -- mas a logica real mora em um unico lugar cada.

    @property
    def errors(self):
        """Acesso ao sistema de aprendizado negativo (falha->correção)."""
        from automation.error_learning import error_learner
        return error_learner

    @property
    def patterns(self):
        """Acesso ao sistema de detecção de padrões por repetição."""
        from automation.automation_learner import automation_learner
        return automation_learner

    # -- Estatisticas agregadas ---------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        rows = db.fetchall("SELECT * FROM learning_knowledge")
        error_stats = self.errors.stats()
        pattern_stats = self.patterns.get_stats()
        return {
            "afinidade":              self.get_affinity(),
            "conhecimentos_positivos": len(rows),
            "confianca_media":        round(sum(r["confianca"] for r in rows) / max(1, len(rows)), 3) if rows else 0.0,
            "correcoes_aprendidas":   error_stats.get("total_correcoes", 0),
            "correcoes_aplicadas":    error_stats.get("total_aplicacoes", 0),
            "padroes_detectados":     pattern_stats.get("sequencias_vistas", 0),
        }


# Instância global
learning_engine = LearningEngine()
