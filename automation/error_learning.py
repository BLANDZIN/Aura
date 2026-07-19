"""
automation/error_learning.py
==============================
Memória de Erros e Auto-Correção.

Fecha o circuito de aprendizado que faltava: até agora a AURA só
aprendia sequências de SUCESSO repetidas (automation_learner.py).
Erros eram corrigidos no código (prompt, validação), mas a própria
AURA nunca "lembrava" de um erro específico para evitar repeti-lo.

Fluxo:
  1. Uma ferramenta falha (tool.result com sucesso=False)
  2. ErrorLearner registra: o que o usuário pediu, o que a IA tentou,
     e a mensagem de erro retornada.
  3. Se o usuário corrige manualmente (pede a ação certa em seguida,
     dentro de uma janela curta de tempo), isso é capturado como o
     par (erro → correção) e salvo permanentemente.
  4. Na próxima vez que um pedido similar aparecer, o DecisionEngine
     consulta essa memória ANTES de deixar a IA tentar de novo —
     aplicando a correção direto, sem repetir o erro.

Diferença em relação ao automation_learner.py:
  - automation_learner: aprende o que FUNCIONOU, por repetição (3x)
  - error_learning:     aprende o que FALHOU, em 1 ocorrência,
                         e a correção aplicada (se houver)

Isso transforma a AURA de "executora que segue regras fixas" para
um agente que ajusta seu próprio comportamento a partir da experiência,
sem depender de eu reescrever o prompt manualmente cada vez.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from database.db_manager import db
from core.event_bus import bus
from core.logger import setup_logger
from core.fuzzy_search import similarity

logger = setup_logger("error_learning")

# Janela de tempo para considerar a mensagem seguinte como "correção"
# de uma falha anterior (em segundos)
CORRECTION_WINDOW_S = 90

# Confiança mínima para aplicar uma correção aprendida automaticamente
MIN_CONFIDENCE_TO_AUTOCORRECT = 0.78


class ErrorLearner:
    """
    Memória de erros conhecidos com correção automática.

    Mantém na sessão atual o último erro ocorrido, esperando uma
    possível correção do usuário. Se a correção vier, salva o par
    (pedido original → ação errada → ação corrigida) permanentemente.
    """

    def __init__(self):
        # Última falha desta sessão, aguardando possível correção
        self._pending_failure: Optional[Dict[str, Any]] = None
        bus.subscribe("tool.result", self._on_tool_result)
        logger.info("ErrorLearner iniciado")

    # ── Captura de falhas ────────────────────────────────────────────────────

    def _on_tool_result(self, sucesso: bool, mensagem: str, resultado: Any) -> None:
        """
        Observa resultados de ferramentas. Se falhar, guarda como
        'falha pendente' aguardando correção do usuário.
        """
        if sucesso:
            return
        # A falha em si é registrada com mais contexto via register_failure(),
        # chamado pelo AIEngine/ToolManager que tem acesso ao pedido original.
        # Aqui só logamos o evento bruto para diagnóstico.
        logger.debug(f"Falha observada via bus: {mensagem}")
        # Sinaliza para quem estiver monitorando a saúde do projeto (ex.: a
        # Angela, via angela/autoengineering.py). automation/ não conhece
        # angela/ — é só um evento público no bus, sem acoplamento direto.
        bus.publish("aura.problem", kind="tool_failure", detail=mensagem)

    def register_failure(
        self,
        user_input: str,
        acao_tentada: str,
        parametros_tentados: Dict,
        erro_msg: str,
    ) -> None:
        """
        Registra uma falha explicitamente, junto com o que o usuário pediu.
        Chamado pelo AIEngine logo após uma ferramenta retornar sucesso=False.
        """
        self._pending_failure = {
            "user_input":  user_input,
            "acao":        acao_tentada,
            "parametros":  parametros_tentados,
            "erro_msg":    erro_msg,
            "ts":          time.time(),
        }
        logger.info(
            f"Falha registrada: '{user_input[:60]}' -> {acao_tentada} "
            f"falhou ({erro_msg[:60]})"
        )

    # ── Captura de correção ──────────────────────────────────────────────────

    def check_correction(
        self,
        user_input: str,
        acao_corrigida: str,
        parametros_corrigidos: Dict,
    ) -> bool:
        """
        Verifica se este novo pedido é uma correção da falha pendente.
        Se sim, salva o par erro→correção permanentemente.

        Chamado pelo AIEngine antes de processar uma nova mensagem,
        quando a mensagem anterior da AURA foi uma falha.

        Returns:
            True se uma correção foi capturada e salva.
        """
        if not self._pending_failure:
            return False

        elapsed = time.time() - self._pending_failure["ts"]
        if elapsed > CORRECTION_WINDOW_S:
            self._pending_failure = None
            return False

        falha = self._pending_failure
        # Evita salvar "correções" idênticas à própria falha (loop)
        if acao_corrigida == falha["acao"] and parametros_corrigidos == falha["parametros"]:
            return False

        self._save_correction(
            gatilho=falha["user_input"],
            acao_errada=falha["acao"],
            parametros_errados=falha["parametros"],
            erro_msg=falha["erro_msg"],
            acao_correta=acao_corrigida,
            parametros_corretos=parametros_corrigidos,
        )
        self._pending_failure = None
        return True

    def _save_correction(
        self,
        gatilho: str,
        acao_errada: str,
        parametros_errados: Dict,
        erro_msg: str,
        acao_correta: str,
        parametros_corretos: Dict,
    ) -> None:
        """Persiste o par erro→correção no banco."""
        db.execute(
            """INSERT INTO error_corrections
               (gatilho_padrao, acao_errada, parametros_errados, erro_msg,
                acao_correta, parametros_corretos)
               VALUES (?,?,?,?,?,?)""",
            (
                gatilho.lower().strip(),
                acao_errada,
                json.dumps(parametros_errados, ensure_ascii=False),
                erro_msg,
                acao_correta,
                json.dumps(parametros_corretos, ensure_ascii=False),
            ),
        )
        logger.info(
            f"Correção aprendida: '{gatilho[:50]}' "
            f"[{acao_errada} -> {acao_correta}]"
        )
        bus.publish(
            "aura.learned_correction",
            gatilho=gatilho, de=acao_errada, para=acao_correta,
        )

    # ── Aplicação de correções aprendidas ───────────────────────────────────

    def find_known_correction(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Busca se já existe uma correção aprendida para um pedido similar.
        Usado pelo DecisionEngine ANTES de deixar a IA tentar de novo —
        evitando repetir um erro já conhecido.

        Returns:
            {"acao": str, "parametros": dict, "confidence": float} ou None
        """
        text = user_input.lower().strip()
        rows = db.fetchall("SELECT * FROM error_corrections")
        if not rows:
            return None

        best_score = 0.0
        best_row   = None
        for row in rows:
            score = similarity(text, row["gatilho_padrao"])
            if score > best_score:
                best_score = score
                best_row   = row

        if best_row and best_score >= MIN_CONFIDENCE_TO_AUTOCORRECT:
            db.execute(
                """UPDATE error_corrections
                   SET vezes_evitado = vezes_evitado + 1,
                       ultima_aplicacao = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (best_row["id"],),
            )
            logger.info(
                f"Correção aplicada automaticamente (score={best_score:.2f}): "
                f"'{user_input[:50]}' -> {best_row['acao_correta']}"
            )
            return {
                "acao":       best_row["acao_correta"],
                "parametros": json.loads(best_row["parametros_corretos"]),
                "confidence": round(best_score, 3),
                "evitou":     best_row["acao_errada"],
            }
        return None

    def get_pending_failure(self) -> Optional[Dict]:
        """Retorna a falha pendente atual, se houver (para debug/UI)."""
        return self._pending_failure

    def clear_pending(self) -> None:
        """Limpa a falha pendente sem registrar correção (ex: sessão nova)."""
        self._pending_failure = None

    # ── Estatísticas e manutenção ────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        rows = db.fetchall("SELECT * FROM error_corrections")
        return {
            "total_correcoes": len(rows),
            "total_aplicacoes": sum(r["vezes_evitado"] for r in rows),
            "mais_uteis": [
                {"gatilho": r["gatilho_padrao"], "vezes_evitado": r["vezes_evitado"],
                 "correcao": r["acao_correta"]}
                for r in sorted(rows, key=lambda x: x["vezes_evitado"], reverse=True)[:5]
            ],
        }

    def cleanup(self, min_age_days: int = 180, max_unused: int = 0) -> int:
        """
        Remove correções muito antigas que nunca foram reaplicadas
        (provavelmente caso isolado, não um padrão real).
        """
        old = db.fetchall(
            """SELECT id FROM error_corrections
               WHERE vezes_evitado <= ?
               AND CAST(julianday('now') - julianday(criado_em) AS INTEGER) > ?""",
            (max_unused, min_age_days),
        )
        for row in old:
            db.execute("DELETE FROM error_corrections WHERE id=?", (row["id"],))
        if old:
            logger.info(f"Limpeza: {len(old)} correção(ões) obsoleta(s) removida(s)")
        return len(old)


# Instância global
error_learner = ErrorLearner()
