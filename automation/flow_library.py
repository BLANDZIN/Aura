"""
automation/flow_library.py — AURA v5
=====================================
Biblioteca de Fluxos Inteligente.

Cada fluxo tem métricas reais:
  - taxa_sucesso: sobe com execuções bem-sucedidas, cai com falhas
  - tempo_medio: média móvel do tempo de execução
  - prioridade: calculada automaticamente (sucesso × uso / tempo)
  - contexto: quando usar este fluxo (apps abertos, hora, etc.)

O FlowLibrary decide qual fluxo usar para um objetivo,
priorizando eficiência real medida ao longo do tempo.

Desenvolvido por Bland | Claude
"""

import json
import time
import math
from datetime import datetime
from typing import Optional, Dict, Any, List
from database.db_manager import db
from core.logger import setup_logger

logger = setup_logger("flow_library")


class FlowLibrary:
    """
    Biblioteca central de fluxos com auto-priorização.

    Fluxos ruins (falham muito ou demoram demais) perdem prioridade
    automaticamente. Fluxos eficientes sobem.
    """

    # ── Escrita ───────────────────────────────────────────────────────────────

    def save(
        self,
        nome: str,
        passos: List[Dict],
        descricao: str = "",
        contexto: str = "",
        importancia: int = 5,
    ) -> None:
        """Salva ou atualiza um fluxo na biblioteca."""
        nome = nome.strip().lower().replace(" ", "_")
        passos_json = json.dumps(passos, ensure_ascii=False)
        existing = db.fetchone(
            "SELECT id, uso_count, taxa_sucesso, tempo_medio FROM flow_library WHERE nome = ?",
            (nome,)
        )
        if existing:
            db.execute(
                """UPDATE flow_library
                   SET passos=?, descricao=?, contexto=?, importancia=?,
                       atualizado_em=CURRENT_TIMESTAMP
                   WHERE nome=?""",
                (passos_json, descricao, contexto, importancia, nome)
            )
            logger.info(f"Fluxo atualizado: '{nome}'")
        else:
            db.execute(
                """INSERT INTO flow_library
                   (nome, descricao, passos, contexto, importancia)
                   VALUES (?,?,?,?,?)""",
                (nome, descricao, passos_json, contexto, importancia)
            )
            logger.info(f"Fluxo criado: '{nome}' ({len(passos)} passos)")

    def get(self, nome: str) -> Optional[Dict]:
        """Retorna um fluxo pelo nome."""
        nome = nome.strip().lower().replace(" ", "_")
        row  = db.fetchone("SELECT * FROM flow_library WHERE nome=?", (nome,))
        if row:
            row["passos"] = json.loads(row["passos"])
        return row

    def get_all(self, min_prioridade: float = 0.0) -> List[Dict]:
        """Retorna todos os fluxos ordenados por prioridade calculada."""
        rows = db.fetchall(
            """SELECT * FROM flow_library
               WHERE prioridade >= ?
               ORDER BY prioridade DESC, uso_count DESC""",
            (min_prioridade,)
        )
        for row in rows:
            row["passos"] = json.loads(row["passos"])
        return rows

    def delete(self, nome: str) -> None:
        nome = nome.strip().lower().replace(" ", "_")
        db.execute("DELETE FROM flow_library WHERE nome=?", (nome,))

    # ── Registro de execução ──────────────────────────────────────────────────

    def register_execution(
        self,
        nome: str,
        sucesso: bool,
        tempo_s: float,
        objetivo: str = "",
        erro_msg: str = "",
        passos_usados: List[Dict] = None,
    ) -> None:
        """
        Registra resultado de uma execução e recalcula métricas.
        Chamado pelo FlowExecutor após cada fluxo.
        """
        nome = nome.strip().lower().replace(" ", "_")

        # Salva no log de execuções
        db.execute(
            """INSERT INTO execution_log
               (flow_nome, objetivo, passos_json, sucesso, tempo_s, erro_msg)
               VALUES (?,?,?,?,?,?)""",
            (nome, objetivo,
             json.dumps(passos_usados or [], ensure_ascii=False),
             int(sucesso), round(tempo_s, 3), erro_msg or "")
        )

        # Atualiza métricas do fluxo
        row = db.fetchone(
            "SELECT * FROM flow_library WHERE nome=?", (nome,)
        )
        if not row:
            return

        uso_count  = row["uso_count"] + 1
        erro_count = row["erro_count"] + (0 if sucesso else 1)

        # Taxa de sucesso: média exponencial (mais peso para execuções recentes)
        alpha       = 0.3  # fator de suavização
        taxa_atual  = row["taxa_sucesso"]
        nova_taxa   = alpha * (1.0 if sucesso else 0.0) + (1 - alpha) * taxa_atual
        nova_taxa   = round(nova_taxa, 4)

        # Tempo médio: média móvel
        tempo_atual = row["tempo_medio"]
        if tempo_atual == 0:
            novo_tempo = tempo_s
        else:
            novo_tempo = alpha * tempo_s + (1 - alpha) * tempo_atual
        novo_tempo = round(novo_tempo, 3)

        # Prioridade: f(taxa_sucesso, uso, tempo)
        nova_prioridade = self._calc_priority(nova_taxa, uso_count, novo_tempo, row["importancia"])

        db.execute(
            """UPDATE flow_library
               SET uso_count=?, erro_count=?, taxa_sucesso=?,
                   tempo_medio=?, prioridade=?, ultimo_uso=CURRENT_TIMESTAMP,
                   atualizado_em=CURRENT_TIMESTAMP
               WHERE nome=?""",
            (uso_count, erro_count, nova_taxa, novo_tempo, nova_prioridade, nome)
        )

        logger.info(
            f"Fluxo '{nome}': sucesso={sucesso} t={tempo_s:.1f}s "
            f"taxa={nova_taxa:.2f} prio={nova_prioridade:.2f}"
        )

    def register_correction(self, nome: str, novos_passos: List[Dict], motivo: str = "") -> None:
        """
        Registra correção feita pelo usuário.
        Atualiza o fluxo com os novos passos e penaliza levemente a taxa
        (o fluxo anterior não era perfeito).
        """
        nome = nome.strip().lower().replace(" ", "_")
        row  = db.fetchone("SELECT * FROM flow_library WHERE nome=?", (nome,))
        if not row:
            # Cria novo fluxo a partir da correção
            self.save(nome, novos_passos, descricao=f"Corrigido: {motivo}", importancia=8)
            logger.info(f"Novo fluxo criado por correção: '{nome}'")
            return

        # Penaliza levemente a taxa (havia algo errado)
        taxa_penalizada = max(0.5, row["taxa_sucesso"] * 0.85)
        db.execute(
            """UPDATE flow_library
               SET passos=?, taxa_sucesso=?, atualizado_em=CURRENT_TIMESTAMP
               WHERE nome=?""",
            (json.dumps(novos_passos, ensure_ascii=False), taxa_penalizada, nome)
        )
        # Registra no log de execuções como corrigido
        db.execute(
            """UPDATE execution_log SET corrigido=1
               WHERE flow_nome=? ORDER BY executado_em DESC LIMIT 1""",
            (nome,)
        )
        logger.info(f"Fluxo '{nome}' corrigido pelo usuário: {motivo}")

    # ── Motor de decisão ──────────────────────────────────────────────────────

    def find_best_for(
        self,
        objetivo: str,
        context_apps: List[str] = None,
    ) -> Optional[Dict]:
        """
        Encontra o melhor fluxo para um objetivo dado.

        Usa similaridade fuzzy + prioridade calculada.
        Fluxos com taxa_sucesso < 0.4 são ignorados.

        Args:
            objetivo:     Texto do que o usuário quer fazer.
            context_apps: Programas atualmente abertos (para contexto).

        Returns:
            Melhor fluxo ou None se não encontrado com confiança suficiente.
        """
        from core.fuzzy_search import similarity
        text = objetivo.lower().strip()

        candidates = db.fetchall(
            "SELECT * FROM flow_library WHERE taxa_sucesso >= 0.4 ORDER BY prioridade DESC"
        )

        best_score = 0.0
        best_flow  = None

        for row in candidates:
            nome = row["nome"].replace("_", " ")
            desc = (row.get("descricao") or "").lower()
            ctx  = (row.get("contexto") or "").lower()

            # Score de similaridade com o objetivo
            sim = max(
                similarity(text, nome),
                similarity(text, desc),
                0.88 if nome in text else 0.0,
                0.88 if text in nome else 0.0,
            )

            # Bônus de contexto: apps em comum aumentam o score
            if context_apps and ctx:
                matching = sum(1 for app in context_apps if app.lower() in ctx)
                sim += matching * 0.05

            # Pondera pelo score de prioridade do fluxo. O piso do fator
            # subiu de 0.7 para 0.85: antes, um fluxo recém-criado (baixa
            # prioridade por ainda não ter histórico de uso) podia ter um
            # match de texto quase perfeito (ex: sim=0.80) e mesmo assim
            # cair abaixo do threshold de 0.70 só por ser novo — exatamente
            # o caso de "salvar um atalho agora e usar 5 segundos depois"
            # falhando. Prioridade deve AMPLIFICAR matches bons, não
            # bloquear fluxos legítimos só por falta de histórico.
            final_score = sim * (0.85 + 0.15 * min(1.0, row["prioridade"] / 10.0))

            if final_score > best_score:
                best_score = final_score
                best_flow  = row

        # Threshold: 0.70 para usar sem modelo
        if best_score >= 0.70 and best_flow:
            best_flow["passos"] = json.loads(best_flow["passos"])
            best_flow["match_score"] = round(best_score, 3)
            logger.info(
                f"Melhor fluxo para '{objetivo}': "
                f"'{best_flow['nome']}' score={best_score:.2f} "
                f"taxa={best_flow['taxa_sucesso']:.2f}"
            )
            return best_flow

        return None

    def suggest_optimization(self, nome: str) -> Optional[str]:
        """
        Analisa histórico de um fluxo e sugere otimizações.
        Retorna string com sugestão ou None.
        """
        row = db.fetchone("SELECT * FROM flow_library WHERE nome=?", (nome,))
        if not row:
            return None

        taxa   = row["taxa_sucesso"]
        tempo  = row["tempo_medio"]
        uso    = row["uso_count"]
        erros  = row["erro_count"]

        if uso < 3:
            return None  # Poucos dados para sugerir

        suggestions = []

        if taxa < 0.6:
            suggestions.append(
                f"Taxa de sucesso baixa ({taxa:.0%}). "
                f"Considere aumentar o tempo de espera entre etapas."
            )
        if tempo > 30:
            suggestions.append(
                f"Fluxo demorado ({tempo:.0f}s em média). "
                f"Verifique se alguma etapa pode ser eliminada."
            )
        if erros > uso * 0.3:
            suggestions.append(
                f"{erros} falhas em {uso} usos. "
                f"O fluxo pode precisar de revisão."
            )

        return "\n".join(suggestions) if suggestions else None

    # ── Gerenciamento de memória ──────────────────────────────────────────────

    def cleanup(self, min_uso: int = 1, max_age_days: int = 90) -> int:
        """
        Remove fluxos obsoletos:
        - Taxa de sucesso < 0.2 com mais de 5 usos
        - Nunca usados com mais de 90 dias
        Retorna número de fluxos removidos.
        """
        removed = 0

        # Remove fluxos com taxa de sucesso muito baixa
        bad = db.fetchall(
            "SELECT nome FROM flow_library WHERE taxa_sucesso < 0.2 AND uso_count >= 5"
        )
        for row in bad:
            self.delete(row["nome"])
            removed += 1
            logger.info(f"Fluxo removido (baixa taxa): '{row['nome']}'")

        # Remove fluxos antigos nunca usados
        old = db.fetchall(
            """SELECT nome FROM flow_library
               WHERE uso_count = 0
               AND CAST(julianday('now') - julianday(criado_em) AS INTEGER) > ?""",
            (max_age_days,)
        )
        for row in old:
            self.delete(row["nome"])
            removed += 1
            logger.info(f"Fluxo removido (nunca usado): '{row['nome']}'")

        if removed:
            logger.info(f"Limpeza: {removed} fluxo(s) removido(s)")
        return removed

    def stats(self) -> Dict[str, Any]:
        """Estatísticas da biblioteca para o painel admin."""
        rows   = db.fetchall("SELECT * FROM flow_library")
        total  = len(rows)
        if total == 0:
            return {"total": 0}

        return {
            "total":          total,
            "ativos":         sum(1 for r in rows if r["taxa_sucesso"] >= 0.6),
            "problematicos":  sum(1 for r in rows if r["taxa_sucesso"] < 0.4),
            "nunca_usados":   sum(1 for r in rows if r["uso_count"] == 0),
            "uso_total":      sum(r["uso_count"] for r in rows),
            "tempo_medio_global": round(
                sum(r["tempo_medio"] for r in rows if r["tempo_medio"] > 0) /
                max(1, sum(1 for r in rows if r["tempo_medio"] > 0)), 2
            ),
            "top_fluxos": [
                {"nome": r["nome"], "prioridade": r["prioridade"],
                 "taxa": r["taxa_sucesso"], "usos": r["uso_count"]}
                for r in sorted(rows, key=lambda x: x["prioridade"], reverse=True)[:5]
            ],
        }

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _calc_priority(taxa: float, uso: int, tempo: float, importancia: int) -> float:
        """
        Prioridade = f(taxa_sucesso, frequencia_uso, velocidade, importancia)

        Fórmula:
          base  = taxa_sucesso^2 × importancia
          uso   = log(uso+1) × 0.5       (uso frequente aumenta prioridade)
          tempo = -log(tempo+1) × 0.3    (mais rápido = melhor)
          total = base + uso + tempo
        """
        base  = (taxa ** 2) * importancia
        uso_f = math.log(uso + 1, 10) * 0.5
        vel   = -math.log(max(0.1, tempo) + 1, 10) * 0.3
        return round(max(0.0, base + uso_f + vel), 3)


# Instância global
flow_library = FlowLibrary()
