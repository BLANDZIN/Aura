"""
tests/test_task_manager.py
===========================
Testes para tasks/task_manager.py (V11).
"""
import pytest


class TestTaskCRUD:
    """Testes de criacao, leitura, atualizacao e remocao de tarefas."""

    def test_create_task(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        tid = tm.criar(titulo="Teste pytest", prioridade=1)
        assert tid > 0
        task = tm.get(tid)
        assert task["titulo"] == "Teste pytest"
        assert task["prioridade"] == 1
        assert task["status"] == "pendente"

    def test_create_with_defaults(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        tid = tm.criar(titulo="Sem prioridade")
        task = tm.get(tid)
        assert task["prioridade"] == 2  # default MEDIA

    def test_edit_task(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        tid = tm.criar(titulo="Original")
        ok = tm.editar(tid, titulo="Editado", prioridade=1)
        assert ok is True
        task = tm.get(tid)
        assert task["titulo"] == "Editado"
        assert task["prioridade"] == 1

    def test_concluir(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        tid = tm.criar(titulo="Para concluir")
        ok = tm.concluir(tid)
        assert ok is True
        task = tm.get(tid)
        assert task["status"] == "concluida"

    def test_cancelar(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        tid = tm.criar(titulo="Para cancelar")
        ok = tm.cancelar(tid)
        assert ok is True
        task = tm.get(tid)
        assert task["status"] == "cancelada"

    def test_edit_nonexistent(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        ok = tm.editar(99999, titulo="Nao existe")
        assert ok is False


class TestTaskListing:
    """Testes de listagem e estatisticas."""

    def test_listar_pendentes(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        tasks = tm.listar_pendentes()
        assert isinstance(tasks, list)

    def test_stats(self):
        from tasks.task_manager import TaskManager
        tm = TaskManager()
        stats = tm.stats()
        assert "total" in stats
        assert "pendentes" in stats
        assert isinstance(stats["total"], int)


class TestSQLWhitelist:
    """Testes da validacao de colunas SQL (V11)."""

    def test_valid_column(self):
        from tasks.task_manager import _validate_column
        assert _validate_column("titulo") == "titulo"
        assert _validate_column("prioridade") == "prioridade"

    def test_invalid_column_raises(self):
        import pytest
        from tasks.task_manager import _validate_column
        with pytest.raises(ValueError):
            _validate_column("'; DROP TABLE tasks; --")
