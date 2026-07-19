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
