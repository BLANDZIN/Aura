"""
memory/memory_manager.py
Sistema de memória em três níveis do AURA — v2 com Sistema de Importância.

Níveis:
  1. ShortTermMemory   — histórico recente em RAM (sem alterações estruturais)
  2. PermanentMemory   — SQLite com importance, access_count, last_access
  3. ProceduralMemory  — SQLite com importance opcional

Novidades nesta versão:
  - classify_importance(text)  → auto-classifica texto por regras
  - build_relevant_context()   → contexto filtrado por importância/acesso/recência
  - memory_stats()             → estatísticas do banco de memórias
  - Rastreamento de access_count e last_access em cada leitura
  - Procedimentos ordenados por importance DESC, uso_count DESC
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from database.db_manager import db
from config.settings import settings
from core.logger import setup_logger

logger = setup_logger("memory")

# Limite máximo de memórias enviadas ao contexto da IA
MAX_MEMORY_CONTEXT: int = 20
MAX_PROCEDURE_CONTEXT: int = 10


# ══════════════════════════════════════════════════════════
# CLASSIFICADOR DE IMPORTÂNCIA
# ══════════════════════════════════════════════════════════

# Cada entrada: (padrão_regex, score, descrição)
_IMPORTANCE_RULES: List[Tuple[re.Pattern, int, str]] = [
    # ── Nível 10: crítico, identidade, metas de vida ──────────────
    (re.compile(r"\bmeu nome (é|e)\b", re.I),                        10, "nome do usuário"),
    (re.compile(r"\bme chamo\b", re.I),                              10, "nome do usuário"),
    (re.compile(r"\bobjetivo principal\b", re.I),                     10, "objetivo principal"),
    (re.compile(r"\bsonho\b.{0,30}\b(vida|carreira|futuro)\b", re.I),10, "sonho de vida"),
    (re.compile(r"\bpassar (na|no|em)\b.{0,40}\b(concurso|prova|vestibular|enem|espcex|aman|ime)\b", re.I), 10, "meta de concurso"),
    (re.compile(r"\bprojeto importante\b", re.I),                     10, "projeto importante"),
    (re.compile(r"\bpreferência permanente\b", re.I),                 10, "preferência permanente"),

    # ── Nível 9: projetos e metas de médio prazo ──────────────────
    (re.compile(r"\bestou (desenvolvendo|construindo|criando)\b", re.I), 9, "projeto em andamento"),
    (re.compile(r"\btrabalho (como|de|na|no)\b", re.I),               9, "ocupação"),
    (re.compile(r"\bformação (em|de)\b", re.I),                       9, "formação acadêmica"),
    (re.compile(r"\bidioma\b.{0,20}\b(falo|aprend|estud)\b", re.I),   9, "idioma aprendido"),

    # ── Nível 8: interesses e hobbies relevantes ──────────────────
    (re.compile(r"\bgosto de\b", re.I),                               8, "gosto pessoal"),
    (re.compile(r"\bcurto\b.{0,30}\b(jog|music|esport|livr|film)\b", re.I), 8, "hobby"),
    (re.compile(r"\bhobbi\b", re.I),                                  8, "hobby"),
    (re.compile(r"\bfavorito\b", re.I),                               8, "preferência favorita"),
    (re.compile(r"\bcostum(o|a) (usar|fazer|jogar|assistir)\b", re.I),8, "rotina frequente"),

    # ── Nível 7: tecnologias, ferramentas, contexto profissional ──
    (re.compile(r"\buso\b.{0,20}\b(python|java|javascript|rust|c\+\+|sql)\b", re.I), 7, "linguagem de programação"),
    (re.compile(r"\bferramenta\b.{0,30}\b(uso|utilizo|prefiro)\b", re.I), 7, "ferramenta usada"),
    (re.compile(r"\bsistema operacional\b", re.I),                    7, "sistema operacional"),
    (re.compile(r"\bconfiguração\b", re.I),                           7, "configuração do sistema"),

    # ── Nível 5-6: informações ocasionais ─────────────────────────
    (re.compile(r"\bontem\b|\bessa semana\b|\brecentemente\b", re.I), 5, "informação recente"),
    (re.compile(r"\bpreciso\b.{0,30}\b(depois|mais tarde|amanhã)\b", re.I), 5, "necessidade futura"),
    (re.compile(r"\binstalei\b|\batualizei\b", re.I),                 5, "ação realizada"),

    # ── Nível 2: comentários passageiros ──────────────────────────
    # cobre: almoço/almocei/almocou, janta/jantei/jantou, comi, bebi
    (re.compile(r"\b(almo[cç]\w*|jant\w+|comi|bebi)\b", re.I),       2, "refeição do dia"),
    (re.compile(r"\bestou (com fome|com sono|cansad)\b", re.I),       2, "estado momentâneo"),

    # ── Nível 1: ações triviais de sistema ────────────────────────
    # "abri o Chrome" / "abri Chrome" / "Abri o firefox"
    (re.compile(r"\babri\s+(?:o\s+)?(chrome|firefox|notepad|calculadora)\b", re.I), 1, "ação trivial"),
    (re.compile(r"\bfechei\b|\bminimizei\b", re.I),                   1, "ação de janela"),
]

_DEFAULT_IMPORTANCE = 5


def classify_importance(text: str) -> int:
    """
    Classifica automaticamente a importância de um texto usando regras.

    Retorna um valor inteiro de 1 (descartável) a 10 (crítico).

    Estratégia:
    - Se alguma regra casar, retorna o MAIOR score entre todas as que casaram.
    - Se nenhuma regra casar, retorna o valor default (5).
    - Regras de baixa importância (1-2) apenas prevalecem se nenhuma regra
      de importância maior também casar.

    Exemplos:
        "Meu nome é João"        → 10
        "Quero passar na EsPCEx" → 10
        "Gosto de RPG"           → 8
        "Uso Python"             → 7
        "Hoje almocei arroz"     → 2
        "Abri o Chrome"          → 1
        "Texto qualquer"         → 5  (default)
    """
    matched_scores = []

    for pattern, score, reason in _IMPORTANCE_RULES:
        if pattern.search(text):
            matched_scores.append((score, reason))
            logger.debug(f"  Regra casou: score={score} ({reason})")

    if not matched_scores:
        logger.debug(f"classify_importance: score={_DEFAULT_IMPORTANCE} (sem match) para: '{text[:60]}'")
        return _DEFAULT_IMPORTANCE

    best_score, best_reason = max(matched_scores, key=lambda x: x[0])
    logger.debug(f"classify_importance: score={best_score} ({best_reason}) para: '{text[:60]}'")
    return best_score


# ══════════════════════════════════════════════════════════
# NÍVEL 1: Memória Temporária  (sem alterações estruturais)
# ══════════════════════════════════════════════════════════

class ShortTermMemory:
    """
    Mantém o histórico recente da conversa em memória RAM.
    Descartada ao encerrar o programa.
    Limite configurável via settings.
    """

    def __init__(self):
        self._history: List[Dict] = []
        self._limit: int = settings.get("memory", "short_term_limit", default=20)

    def add(self, role: str, content: str) -> None:
        """Adiciona mensagem ao histórico."""
        self._history.append({"role": role, "content": content})
        if len(self._history) > self._limit:
            for i, msg in enumerate(self._history):
                if msg["role"] != "system":
                    self._history.pop(i)
                    break

    def get_messages(self) -> List[Dict]:
        """Retorna o histórico completo para enviar à IA."""
        return self._history.copy()

    def clear(self) -> None:
        """Limpa o histórico (nova sessão)."""
        self._history.clear()

    def get_last_n(self, n: int) -> List[Dict]:
        return self._history[-n:]

    def count(self) -> int:
        return len(self._history)


# ══════════════════════════════════════════════════════════
# NÍVEL 2: Memória Permanente  (evoluída com importância)
# ══════════════════════════════════════════════════════════

class PermanentMemory:
    """
    Armazena informações de longo prazo no SQLite.

    Novos campos por linha:
      importance   — 1-10, define prioridade no contexto da IA
      access_count — incrementado a cada leitura (popularidade real)
      last_access  — timestamp do último acesso

    Métodos novos:
      save()                 — aceita importance opcional; autoclassifica se omitido
      build_relevant_context()  — contexto filtrado e limitado (substitui build_context_string)
      memory_stats()         — estatísticas gerais
    """

    # ── Escrita ───────────────────────────────────────────────────

    def save(
        self,
        categoria: str,
        chave: str,
        valor: str,
        importance: Optional[int] = None,
    ) -> None:
        """
        Salva ou atualiza um dado permanente.

        Se importance não for informado, a importância é classificada
        automaticamente pelo conteúdo do valor (não da chave técnica).

        Nota: para melhor classificação, passe importance explícito quando
        a informação vier de uma intenção da IA (que conhece o contexto).
        """
        if importance is None:
            importance = classify_importance(valor)
        importance = max(1, min(10, importance))  # clamp 1-10

        existing = db.fetchone(
            "SELECT id FROM memory_permanent WHERE chave = ?", (chave,)
        )
        if existing:
            db.execute(
                """UPDATE memory_permanent
                   SET valor = ?, categoria = ?, importance = ?,
                       atualizado_em = CURRENT_TIMESTAMP
                   WHERE chave = ?""",
                (valor, categoria, importance, chave),
            )
        else:
            db.execute(
                """INSERT INTO memory_permanent
                   (categoria, chave, valor, importance)
                   VALUES (?, ?, ?, ?)""",
                (categoria, chave, valor, importance),
            )
        logger.debug(
            f"Memória permanente salva: [{categoria}] {chave} = {valor!r} "
            f"(importance={importance})"
        )

    # ── Leitura simples ───────────────────────────────────────────

    def get(self, chave: str) -> Optional[str]:
        """Busca um valor pelo campo chave e registra o acesso."""
        row = db.fetchone(
            "SELECT id, valor FROM memory_permanent WHERE chave = ?", (chave,)
        )
        if row:
            self._register_access(row["id"])
            return row["valor"]
        return None

    def get_with_meta(self, chave: str) -> Optional[Dict]:
        """Retorna o registro completo (valor + metadados de importância)."""
        row = db.fetchone(
            "SELECT * FROM memory_permanent WHERE chave = ?", (chave,)
        )
        if row:
            self._register_access(row["id"])
        return row

    def get_by_category(self, categoria: str) -> List[Dict]:
        """Retorna todas as memórias de uma categoria, mais importantes primeiro."""
        rows = db.fetchall(
            """SELECT chave, valor, importance, access_count, atualizado_em
               FROM memory_permanent
               WHERE categoria = ?
               ORDER BY importance DESC, access_count DESC""",
            (categoria,),
        )
        for row in rows:
            self._register_access_by_chave(row["chave"])
        return rows

    def get_all(self) -> List[Dict]:
        """Retorna todas as memórias ordenadas por importância."""
        return db.fetchall(
            """SELECT categoria, chave, valor, importance, access_count,
                      last_access, criado_em, atualizado_em
               FROM memory_permanent
               ORDER BY importance DESC, access_count DESC"""
        )

    def delete(self, chave: str) -> None:
        db.execute("DELETE FROM memory_permanent WHERE chave = ?", (chave,))

    # ── Rastreamento de acesso ────────────────────────────────────

    def _register_access(self, memory_id: int) -> None:
        db.execute(
            """UPDATE memory_permanent
               SET access_count = access_count + 1,
                   last_access = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (memory_id,),
        )

    def _register_access_by_chave(self, chave: str) -> None:
        db.execute(
            """UPDATE memory_permanent
               SET access_count = access_count + 1,
                   last_access = CURRENT_TIMESTAMP
               WHERE chave = ?""",
            (chave,),
        )

    # ── Contexto para IA ──────────────────────────────────────────

    def build_relevant_context(self, limit: int = MAX_MEMORY_CONTEXT) -> str:
        """
        NOVO — Seleciona as memórias mais relevantes para o contexto da IA.

        Estratégia de pontuação composta:
          score = (importance * 3) + (log(access_count + 1) * 2) + recência_bonus

        Retorna no máximo `limit` memórias, priorizando:
          1. Importância alta (9-10) — nunca ficam de fora
          2. Mais acessadas (popularidade real)
          3. Mais recentes (atualizado_em)
        """
        import math

        rows = db.fetchall(
            """SELECT chave, valor, categoria, importance, access_count, atualizado_em
               FROM memory_permanent
               ORDER BY importance DESC"""
        )
        if not rows:
            return ""

        # Separa críticas (9-10) das demais
        criticas = [r for r in rows if r["importance"] >= 9]
        demais   = [r for r in rows if r["importance"] <  9]

        def _recencia_bonus(row: Dict) -> float:
            """Memórias atualizadas nos últimos 7 dias ganham +2."""
            try:
                dt = datetime.fromisoformat(row["atualizado_em"])
                delta = (datetime.now() - dt).days
                return 2.0 if delta <= 7 else (1.0 if delta <= 30 else 0.0)
            except Exception:
                return 0.0

        def _score(row: Dict) -> float:
            imp  = row["importance"]
            acc  = math.log(row["access_count"] + 1, 10) * 2
            rec  = _recencia_bonus(row)
            return (imp * 3) + acc + rec

        # Ordena demais por score composto
        demais_ordenadas = sorted(demais, key=_score, reverse=True)

        # Monta lista final: críticas sempre incluídas + melhores demais
        vagas_restantes = max(0, limit - len(criticas))
        selecionadas = criticas + demais_ordenadas[:vagas_restantes]

        if not selecionadas:
            return ""

        lines = ["MEMÓRIAS RELEVANTES SOBRE O USUÁRIO:"]
        for row in selecionadas:
            imp_label = self._importance_label(row["importance"])
            lines.append(
                f"- [{row['categoria']}] {row['chave']}: {row['valor']}  "
                f"({imp_label})"
            )

        # Registra acesso para todas as memórias enviadas
        for row in selecionadas:
            self._register_access_by_chave(row["chave"])

        return "\n".join(lines)

    def build_context_string(self) -> str:
        """
        MANTIDO para compatibilidade — envia todas as memórias sem filtro.
        Para uso normal prefira build_relevant_context().
        """
        rows = self.get_all()
        if not rows:
            return ""
        lines = ["MEMÓRIAS SOBRE O USUÁRIO:"]
        for row in rows:
            lines.append(f"- [{row['categoria']}] {row['chave']}: {row['valor']}")
        return "\n".join(lines)

    # ── Estatísticas ──────────────────────────────────────────────

    def memory_stats(self) -> Dict:
        """
        Retorna estatísticas gerais do banco de memórias permanentes.
        Usado pelo painel administrativo do AURA.
        """
        rows = self.get_all()
        if not rows:
            return {
                "total_memories": 0,
                "high_importance": 0,
                "medium_importance": 0,
                "low_importance": 0,
                "most_accessed": [],
                "oldest_memory": {},
            }

        high   = [r for r in rows if r["importance"] >= 8]
        medium = [r for r in rows if 4 <= r["importance"] <= 7]
        low    = [r for r in rows if r["importance"] <= 3]

        most_accessed = sorted(rows, key=lambda r: r["access_count"], reverse=True)[:5]
        oldest = sorted(
            rows,
            key=lambda r: r.get("criado_em") or "",
        )
        oldest_entry = oldest[0] if oldest else {}

        return {
            "total_memories":    len(rows),
            "high_importance":   len(high),
            "medium_importance": len(medium),
            "low_importance":    len(low),
            "most_accessed": [
                {
                    "chave": r["chave"],
                    "access_count": r["access_count"],
                    "importance": r["importance"],
                }
                for r in most_accessed
            ],
            "oldest_memory": {
                "chave":     oldest_entry.get("chave", ""),
                "criado_em": oldest_entry.get("criado_em", ""),
            },
        }

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _importance_label(score: int) -> str:
        if score >= 9:  return "crítico"
        if score >= 7:  return "relevante"
        if score >= 4:  return "secundário"
        return "baixa"


# ══════════════════════════════════════════════════════════
# NÍVEL 3: Memória de Procedimentos  (importance adicionada)
# ══════════════════════════════════════════════════════════

class ProceduralMemory:
    """
    Armazena procedimentos (receitas de ação) que o AURA pode executar.

    Evolução: campo `importance` opcional.
    Procedimentos mais importantes aparecem primeiro no contexto da IA.
    """

    def save(
        self,
        nome: str,
        descricao: str,
        passos: List[str],
        importance: int = 5,
    ) -> None:
        """Salva ou atualiza um procedimento com importância."""
        importance = max(1, min(10, importance))
        passos_json = json.dumps(passos, ensure_ascii=False)
        existing = db.fetchone(
            "SELECT id FROM memory_procedures WHERE nome = ?", (nome,)
        )
        if existing:
            db.execute(
                """UPDATE memory_procedures
                   SET descricao = ?, passos = ?, importance = ?,
                       atualizado_em = CURRENT_TIMESTAMP
                   WHERE nome = ?""",
                (descricao, passos_json, importance, nome),
            )
        else:
            db.execute(
                """INSERT INTO memory_procedures
                   (nome, descricao, passos, importance)
                   VALUES (?, ?, ?, ?)""",
                (nome, descricao, passos_json, importance),
            )
        logger.info(f"Procedimento salvo: {nome} (importance={importance})")

    def get(self, nome: str) -> Optional[Dict]:
        """Busca um procedimento pelo nome e incrementa uso."""
        row = db.fetchone(
            "SELECT * FROM memory_procedures WHERE nome = ?", (nome,)
        )
        if row:
            row["passos"] = json.loads(row["passos"])
            self.increment_usage(nome)
        return row

    def get_all(self) -> List[Dict]:
        """
        Retorna todos os procedimentos.
        Ordem: importance DESC, uso_count DESC (mais importantes e usados primeiro).
        """
        rows = db.fetchall(
            "SELECT * FROM memory_procedures ORDER BY importance DESC, uso_count DESC"
        )
        for row in rows:
            row["passos"] = json.loads(row["passos"])
        return rows

    def delete(self, nome: str) -> None:
        db.execute("DELETE FROM memory_procedures WHERE nome = ?", (nome,))

    def increment_usage(self, nome: str) -> None:
        db.execute(
            "UPDATE memory_procedures SET uso_count = uso_count + 1 WHERE nome = ?",
            (nome,),
        )

    def build_relevant_context(self, limit: int = MAX_PROCEDURE_CONTEXT) -> str:
        """
        NOVO — Retorna apenas os procedimentos mais relevantes.
        Ordenados por importance DESC, uso_count DESC; limitado a `limit` itens.
        """
        rows = self.get_all()[:limit]
        if not rows:
            return ""
        lines = ["PROCEDIMENTOS DISPONÍVEIS (rotinas que você pode seguir):"]
        for row in rows:
            passos_txt = "\n".join(
                f"  {i+1}. {p}" for i, p in enumerate(row["passos"])
            )
            imp_label = PermanentMemory._importance_label(row["importance"])
            lines.append(
                f"\n[{row['nome']}] ({imp_label}): {row.get('descricao', '')}\n{passos_txt}"
            )
        return "\n".join(lines)

    def build_context_string(self) -> str:
        """
        MANTIDO para compatibilidade — envia todos os procedimentos sem limite.
        Para uso normal prefira build_relevant_context().
        """
        rows = self.get_all()
        if not rows:
            return ""
        lines = ["PROCEDIMENTOS DISPONÍVEIS (rotinas que você pode seguir):"]
        for row in rows:
            passos_txt = "\n".join(
                f"  {i+1}. {p}" for i, p in enumerate(row["passos"])
            )
            lines.append(
                f"\n[{row['nome']}]: {row.get('descricao', '')}\n{passos_txt}"
            )
        return "\n".join(lines)

    def procedure_stats(self) -> Dict:
        """Estatísticas dos procedimentos para o painel admin."""
        rows = self.get_all()
        return {
            "total_procedures": len(rows),
            "high_importance":  sum(1 for r in rows if r["importance"] >= 8),
            "most_used": [
                {"nome": r["nome"], "uso_count": r["uso_count"], "importance": r["importance"]}
                for r in sorted(rows, key=lambda r: r["uso_count"], reverse=True)[:5]
            ],
        }


# ══════════════════════════════════════════════════════════
# FACADE UNIFICADA
# ══════════════════════════════════════════════════════════

class MemoryManager:
    """
    Ponto de acesso unificado para todos os sistemas de memória.

    build_full_context()     — mantido para compatibilidade (envia tudo)
    build_relevant_context() — NOVO: envia apenas o que importa
    memory_stats()           — NOVO: estatísticas unificadas
    """

    def __init__(self):
        self.short_term  = ShortTermMemory()
        self.permanent   = PermanentMemory()
        self.procedural  = ProceduralMemory()

    # ── Contexto inteligente (uso recomendado) ────────────────────

    def build_relevant_context(self) -> str:
        """
        Monta o contexto de memória filtrado pela relevância.
        Fluxo recomendado para o AIEngine:

          System Prompt
          ↓
          Memórias Permanentes Relevantes   (importance + acesso + recência)
          ↓
          Procedimentos Relevantes          (importance + uso)
          ↓
          Histórico Temporário
          ↓
          IA
        """
        parts = []
        perm = self.permanent.build_relevant_context()
        if perm:
            parts.append(perm)
        proc = self.procedural.build_relevant_context()
        if proc:
            parts.append(proc)
        return "\n\n".join(parts)

    # ── Contexto completo (compatibilidade) ───────────────────────

    def build_full_context(self) -> str:
        """
        MANTIDO para compatibilidade — envia todas as memórias sem filtro.
        Para uso normal prefira build_relevant_context().
        """
        parts = []
        perm = self.permanent.build_context_string()
        if perm:
            parts.append(perm)
        proc = self.procedural.build_context_string()
        if proc:
            parts.append(proc)
        return "\n\n".join(parts)

    # ── Estatísticas unificadas ───────────────────────────────────

    def memory_stats(self) -> Dict:
        """
        Estatísticas completas de todos os sistemas de memória.
        Retornadas no formato esperado pelo painel administrativo.
        """
        perm  = self.permanent.memory_stats()
        proc  = self.procedural.procedure_stats()
        short = self.short_term.count()
        return {
            "short_term": {
                "messages_in_context": short,
                "limit": self.short_term._limit,
            },
            "permanent":  perm,
            "procedural": proc,
        }


# Instância global — compatível com todo o código existente
memory = MemoryManager()
