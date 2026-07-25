"""
tools/task_tools.py — Ferramentas de Tarefas (3)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
from datetime import datetime

from tools.base_tool import BaseTool


class CriarTarefaTool(BaseTool):
    name = "criar_tarefa"; description = "Cria nova tarefa."
    params_doc = '{"titulo": "Estudar Python", "prioridade": 1}'
    def execute(self, p):
        from tasks.task_manager import task_manager
        try:
            ag = datetime.fromisoformat(p["agendado_em"]) if p.get("agendado_em") else None
            tid = task_manager.criar(titulo=p["titulo"], descricao=p.get("descricao",""),
                prioridade=p.get("prioridade",2), agendado_em=ag, repeticao=p.get("repeticao"))
            return self._success(tid, f"Tarefa criada: '{p['titulo']}' (#{tid})")
        except Exception as e:
            return self._error("Erro ao criar tarefa", e)

class ListarTarefasTool(BaseTool):
    name = "listar_tarefas"; description = "Lista tarefas pendentes."; params_doc = '{}'
    def execute(self, p):
        from tasks.task_manager import task_manager
        try:
            ts = task_manager.listar_pendentes()
            return self._success([task_manager.format_for_display(t) for t in ts], f"{len(ts)} tarefa(s)")
        except Exception as e:
            return self._error("Erro ao listar", e)

class ConcluirTarefaTool(BaseTool):
    name = "concluir_tarefa"; description = "Conclui tarefa pelo ID."
    params_doc = '{"task_id": 1}'
    def execute(self, p):
        from tasks.task_manager import task_manager
        try:
            tid  = int(p["task_id"]); task = task_manager.get(tid)
            if not task: return self._error(f"Tarefa #{tid} não encontrada")
            task_manager.concluir(tid)
            return self._success(tid, f"Concluída: '{task['titulo']}'")
        except Exception as e:
            return self._error("Erro ao concluir", e)


# Auto-registro V11
REGISTRY = [CriarTarefaTool(), ListarTarefasTool(), ConcluirTarefaTool()]