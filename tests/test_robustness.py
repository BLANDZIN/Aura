import os
import time

from core.logger import _cleanup_old_logs


def test_cleanup_removes_only_logs_older_than_retention(tmp_path):
    old_log = tmp_path / "aura_20200101.log"
    recent_log = tmp_path / "aura_recent.log"
    old_log.write_text("log antigo")
    recent_log.write_text("log recente")

    # Força o mtime do "antigo" pra 40 dias atrás
    forty_days_ago = time.time() - (40 * 86400)
    os.utime(old_log, (forty_days_ago, forty_days_ago))

    removed = _cleanup_old_logs(retention_days=30, log_dir=str(tmp_path))

    assert removed == 1
    assert not old_log.exists()
    assert recent_log.exists()


def test_cleanup_ignores_non_log_files(tmp_path):
    (tmp_path / "nota.txt").write_text("não é log, não mexe")
    old_ts = time.time() - (100 * 86400)
    os.utime(tmp_path / "nota.txt", (old_ts, old_ts))

    removed = _cleanup_old_logs(retention_days=30, log_dir=str(tmp_path))

    assert removed == 0
    assert (tmp_path / "nota.txt").exists()


def test_cleanup_empty_dir_is_safe():
    assert _cleanup_old_logs(retention_days=30, log_dir="/tmp/dir-que-nao-existe-xyz") == 0


def test_db_manager_has_busy_timeout_configured():
    from database.db_manager import db
    row = db._conn.execute("PRAGMA busy_timeout").fetchone()
    assert row[0] >= 5000


def test_db_manager_has_wal_mode():
    from database.db_manager import db
    row = db._conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"


def test_db_manager_has_indices_for_frequent_queries(tmp_path):
    # V12.1 Prioridade 9 — índices pras consultas reais mais usadas
    # (tasks por status/prioridade, memory_permanent por categoria/
    # importância, flow_library por prioridade/taxa_sucesso,
    # execution_log por flow_nome). Testado num DB novo, não no global,
    # pra não depender de estado deixado por outros testes.
    from database.db_manager import DatabaseManager
    db = DatabaseManager(db_path=str(tmp_path / "idx_test.db"))
    indices = {
        r["name"] for r in db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
    }
    esperados = {
        "idx_tasks_status_prioridade", "idx_tasks_agendado_em",
        "idx_memory_permanent_categoria", "idx_memory_permanent_importance",
        "idx_flow_library_prioridade", "idx_flow_library_taxa_sucesso",
        "idx_execution_log_flow_nome",
    }
    assert esperados <= indices
    db.close()
