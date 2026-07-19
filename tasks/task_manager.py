"""
tasks/task_manager.py
Gerenciador de Tarefas do AURA.

Funcionalidades:
  - CRUD completo (criar, ler, editar, concluir, cancelar)
  - Agendamento via threading.Timer (sem dependência externa)
  - Repetição diária e semanal com recálculo automático
  - Integração com EventBus (publica eventos para a UI)
  - Persistência em SQLite (tabela 'tasks' já existente no banco)

Prioridades:
  1 = Alta   2 = Média (padrão)   3 = Baixa

Status:
  pendente | em_progresso | concluida | cancelada
"""

import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from database.db_manager import db
from core.event_bus import bus
from core.logger import setup_logger

logger = setup_logger("tasks")


# ── Constantes ────────────────────────────────────────────────────────────────

STATUS_PENDENTE     = "pendente"
STATUS_EM_PROGRESSO = "em_progresso"
STATUS_CONCLUIDA    = "concluida"
STATUS_CANCELADA    = "cancelada"

PRIORIDADE_ALTA   = 1
PRIORIDADE_MEDIA  = 2
PRIORIDADE_BAIXA  = 3

REPETICAO_DIARIA  = "diaria"
REPETICAO_SEMANAL = "semanal"

PRIORIDADE_LABELS = {1: "Alta", 2: "Média", 3: "Baixa"}
STATUS_ICONS       = {
    STATUS_PENDENTE:     "○",
    STATUS_EM_PROGRESSO: "◐",
    STATUS_CONCLUIDA:    "●",
    STATUS_CANCELADA:    "✕",
}


class TaskManager:
    """
    Gerenciador central de tarefas do AURA.

    Uso:
        tm = TaskManager()
        task_id = tm.criar(titulo="Estudar Python", prioridade=1)
        tm.concluir(task_id)
        tm.listar()
    """

    def __init__(self):
        # Mapa de timers ativos: task_id → threading.Timer
        self._timers: Dict[int, threading.Timer] = {}
        # Recarrega agendamentos pendentes ao iniciar
        self._restore_scheduled_tasks()
        logger.info("TaskManager iniciado")

    # ══════════════════════════════════════════════════════════════
    # CRUD
    # ══════════════════════════════════════════════════════════════

    def criar(
        self,
        titulo: str,
        descricao: str = "",
        prioridade: int = PRIORIDADE_MEDIA,
        agendado_em: Optional[datetime] = None,
        repeticao: Optional[str] = None,
    ) -> int:
        """
        Cria uma nova tarefa e retorna seu ID.

        Args:
            titulo:      Nome da tarefa.
            descricao:   Detalhes opcionais.
            prioridade:  1=Alta, 2=Média, 3=Baixa.
            agendado_em: datetime para execução futura (opcional).
            repeticao:   "diaria" | "semanal" | None.

        Returns:
            ID da tarefa criada.
        """
        prioridade = max(1, min(3, prioridade))
        ag_str = agendado_em.isoformat() if agendado_em else None
        rep_str = repeticao if repeticao in (REPETICAO_DIARIA, REPETICAO_SEMANAL) else None

        cursor = db.execute(
            """INSERT INTO tasks (titulo, descricao, prioridade, agendado_em, repeticao)
               VALUES (?, ?, ?, ?, ?)""",
            (titulo, descricao, prioridade, ag_str, rep_str),
        )
        task_id = cursor.lastrowid
        logger.info(f"Tarefa criada: #{task_id} '{titulo}' (prio={prioridade}, rep={rep_str})")

        # Agenda se tiver horário
        if agendado_em:
            self._schedule(task_id, titulo, agendado_em)

        bus.publish("tasks.created", task_id=task_id, titulo=titulo)
        return task_id

    def editar(
        self,
        task_id: int,
        titulo: Optional[str] = None,
        descricao: Optional[str] = None,
        prioridade: Optional[int] = None,
        agendado_em: Optional[datetime] = None,
        repeticao: Optional[str] = None,
    ) -> bool:
        """
        Atualiza campos de uma tarefa existente.
        Apenas os campos fornecidos (não-None) são atualizados.

        Returns:
            True se encontrada e atualizada, False se não existir.
        """
        task = self.get(task_id)
        if not task:
            logger.warning(f"Tarefa #{task_id} não encontrada para edição")
            return False

        # Monta SET dinâmico
        fields, values = [], []

        if titulo is not None:
            fields.append("titulo = ?");      values.append(titulo)
        if descricao is not None:
            fields.append("descricao = ?");   values.append(descricao)
        if prioridade is not None:
            fields.append("prioridade = ?");  values.append(max(1, min(3, prioridade)))
        if agendado_em is not None:
            fields.append("agendado_em = ?"); values.append(agendado_em.isoformat())
        if repeticao is not None:
            rep = repeticao if repeticao in (REPETICAO_DIARIA, REPETICAO_SEMANAL, "") else None
            fields.append("repeticao = ?");   values.append(rep or None)

        if not fields:
            return True  # nada a fazer

        fields.append("atualizado_em = CURRENT_TIMESTAMP")
        values.append(task_id)

        db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )

        # Reagenda se agendamento mudou
        if agendado_em is not None:
            self._cancel_timer(task_id)
            self._schedule(task_id, titulo or task["titulo"], agendado_em)

        logger.info(f"Tarefa #{task_id} editada")
        bus.publish("tasks.updated", task_id=task_id)
        return True

    def concluir(self, task_id: int) -> bool:
        """
        Marca tarefa como concluída.
        Se tiver repetição, cria automaticamente a próxima ocorrência.

        Returns:
            True se concluída com sucesso.
        """
        task = self.get(task_id)
        if not task:
            return False

        db.execute(
            """UPDATE tasks
               SET status = ?, concluido_em = CURRENT_TIMESTAMP,
                   atualizado_em = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (STATUS_CONCLUIDA, task_id),
        )
        self._cancel_timer(task_id)
        logger.info(f"Tarefa #{task_id} '{task['titulo']}' concluída")

        # Recorrência: cria a próxima ocorrência
        if task.get("repeticao") and task.get("agendado_em"):
            self._create_next_occurrence(task)

        bus.publish("tasks.completed", task_id=task_id, titulo=task["titulo"])
        return True

    def cancelar(self, task_id: int) -> bool:
        """Cancela uma tarefa (não apaga do banco)."""
        task = self.get(task_id)
        if not task:
            return False

        db.execute(
            "UPDATE tasks SET status = ?, atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
            (STATUS_CANCELADA, task_id),
        )
        self._cancel_timer(task_id)
        logger.info(f"Tarefa #{task_id} cancelada")
        bus.publish("tasks.cancelled", task_id=task_id)
        return True

    def deletar(self, task_id: int) -> bool:
        """Remove permanentemente uma tarefa do banco."""
        self._cancel_timer(task_id)
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        logger.info(f"Tarefa #{task_id} deletada")
        bus.publish("tasks.deleted", task_id=task_id)
        return True

    def iniciar(self, task_id: int) -> bool:
        """Muda status para em_progresso."""
        db.execute(
            "UPDATE tasks SET status = ?, atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
            (STATUS_EM_PROGRESSO, task_id),
        )
        bus.publish("tasks.updated", task_id=task_id)
        return True

    # ══════════════════════════════════════════════════════════════
    # LEITURA
    # ══════════════════════════════════════════════════════════════

    def get(self, task_id: int) -> Optional[Dict]:
        """Retorna uma tarefa por ID."""
        return db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))

    def listar(
        self,
        status: Optional[str] = None,
        prioridade: Optional[int] = None,
        limite: int = 50,
    ) -> List[Dict]:
        """
        Lista tarefas com filtros opcionais.

        Args:
            status:     Filtra por status (None = todos exceto canceladas).
            prioridade: Filtra por prioridade.
            limite:     Máximo de resultados.

        Returns:
            Lista de dicts ordenada por prioridade e data de criação.
        """
        wheres, params = [], []

        if status:
            wheres.append("status = ?");      params.append(status)
        else:
            wheres.append("status != ?");     params.append(STATUS_CANCELADA)

        if prioridade is not None:
            wheres.append("prioridade = ?");  params.append(prioridade)

        where_sql = f"WHERE {' AND '.join(wheres)}" if wheres else ""
        params.append(limite)

        return db.fetchall(
            f"SELECT * FROM tasks {where_sql} ORDER BY prioridade ASC, criado_em DESC LIMIT ?",
            tuple(params),
        )

    def listar_pendentes(self) -> List[Dict]:
        """Atalho: lista apenas tarefas pendentes e em progresso."""
        return db.fetchall(
            "SELECT * FROM tasks WHERE status IN (?, ?) ORDER BY prioridade, criado_em",
            (STATUS_PENDENTE, STATUS_EM_PROGRESSO),
        )

    def listar_agendadas(self) -> List[Dict]:
        """Lista tarefas com agendamento futuro pendente."""
        return db.fetchall(
            """SELECT * FROM tasks
               WHERE agendado_em IS NOT NULL
                 AND status = ?
                 AND agendado_em > CURRENT_TIMESTAMP
               ORDER BY agendado_em""",
            (STATUS_PENDENTE,),
        )

    def stats(self) -> Dict[str, Any]:
        """Retorna estatísticas para o painel admin."""
        rows = db.fetchall("SELECT status, COUNT(*) as n FROM tasks GROUP BY status")
        counts = {r["status"]: r["n"] for r in rows}
        total  = sum(counts.values())
        return {
            "total":        total,
            "pendentes":    counts.get(STATUS_PENDENTE,     0),
            "em_progresso": counts.get(STATUS_EM_PROGRESSO, 0),
            "concluidas":   counts.get(STATUS_CONCLUIDA,    0),
            "canceladas":   counts.get(STATUS_CANCELADA,    0),
            "agendadas":    len(self.listar_agendadas()),
            "timers_ativos": len(self._timers),
        }

    # ══════════════════════════════════════════════════════════════
    # AGENDAMENTO
    # ══════════════════════════════════════════════════════════════

    def _schedule(self, task_id: int, titulo: str, when: datetime) -> None:
        """
        Agenda um timer para disparar uma tarefa no horário especificado.
        Ignora se o horário já passou.
        """
        now = datetime.now()
        delay = (when - now).total_seconds()

        if delay <= 0:
            logger.warning(f"Tarefa #{task_id} tem agendamento no passado ({when}). Ignorando.")
            return

        def _fire():
            logger.info(f"⏰ Tarefa agendada disparou: #{task_id} '{titulo}'")
            self._cancel_timer(task_id)
            bus.publish(
                "tasks.due",
                task_id=task_id,
                titulo=titulo,
                mensagem=f"⏰ Lembrete: {titulo}",
            )

        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        timer.start()
        self._timers[task_id] = timer
        logger.info(f"Tarefa #{task_id} agendada para {when} (em {delay:.0f}s)")

    def _cancel_timer(self, task_id: int) -> None:
        """Cancela um timer ativo."""
        timer = self._timers.pop(task_id, None)
        if timer:
            timer.cancel()

    def _restore_scheduled_tasks(self) -> None:
        """
        Ao iniciar, reagenda todas as tarefas pendentes com agendamento futuro.
        Garante que tarefas sobrevivam a reinicializações do sistema.
        """
        pendentes = self.listar_agendadas()
        for task in pendentes:
            try:
                when = datetime.fromisoformat(task["agendado_em"])
                self._schedule(task["id"], task["titulo"], when)
            except Exception as e:
                logger.error(f"Erro ao restaurar agendamento #{task['id']}: {e}")

        if pendentes:
            logger.info(f"{len(pendentes)} tarefa(s) agendada(s) restaurada(s)")

    def _create_next_occurrence(self, task: Dict) -> None:
        """
        Cria a próxima ocorrência de uma tarefa recorrente.

        Regras:
          - diaria:  próxima ocorrência = agendado_em + 1 dia
          - semanal: próxima ocorrência = agendado_em + 7 dias
        """
        repeticao   = task.get("repeticao")
        agendado_em = task.get("agendado_em")

        if not repeticao or not agendado_em:
            return

        try:
            base = datetime.fromisoformat(agendado_em)
        except (ValueError, TypeError):
            logger.error(f"Data inválida para recorrência: {agendado_em}")
            return

        delta = timedelta(days=1) if repeticao == REPETICAO_DIARIA else timedelta(weeks=1)
        proxima = base + delta

        # Avança até o futuro se ficou para trás (ex: AURA ficou offline por dias)
        now = datetime.now()
        while proxima <= now:
            proxima += delta

        novo_id = self.criar(
            titulo=task["titulo"],
            descricao=task.get("descricao", ""),
            prioridade=task.get("prioridade", PRIORIDADE_MEDIA),
            agendado_em=proxima,
            repeticao=repeticao,
        )
        logger.info(
            f"Próxima ocorrência criada: #{novo_id} '{task['titulo']}' em {proxima} ({repeticao})"
        )

    # ══════════════════════════════════════════════════════════════
    # FORMATAÇÃO (para exibição na UI e na IA)
    # ══════════════════════════════════════════════════════════════

    def format_for_display(self, task: Dict) -> str:
        """Formata uma tarefa para exibição no chat ou lista."""
        icon     = STATUS_ICONS.get(task.get("status", "pendente"), "○")
        prio     = PRIORIDADE_LABELS.get(task.get("prioridade", 2), "Média")
        titulo   = task.get("titulo", "")
        ag       = task.get("agendado_em", "")
        ag_str   = f" | ⏰ {ag[:16]}" if ag else ""
        rep      = task.get("repeticao", "")
        rep_str  = f" | 🔁 {rep}" if rep else ""
        return f"{icon} [{prio}] {titulo}{ag_str}{rep_str}"

    def build_context_string(self) -> str:
        """
        Gera resumo de tarefas para incluir no prompt da IA.
        Enviado pelo AIEngine quando relevante.
        """
        pendentes = self.listar_pendentes()
        if not pendentes:
            return ""
        lines = [f"TAREFAS ATIVAS ({len(pendentes)}):"]
        for t in pendentes[:10]:  # máx 10 para não inflar o contexto
            lines.append(f"  {self.format_for_display(t)}")
        return "\n".join(lines)

    def shutdown(self) -> None:
        """Cancela todos os timers ao encerrar o AURA."""
        for task_id in list(self._timers.keys()):
            self._cancel_timer(task_id)
        logger.info("Todos os timers de tarefas cancelados")


# Instância global
task_manager = TaskManager()
