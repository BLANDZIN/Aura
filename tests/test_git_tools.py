from pathlib import Path

from angela.platforms.local_stub import LocalStubPlatform
from angela.tools.git_tools import GitTools


def make_git(tmp_path: Path) -> GitTools:
    ws = tmp_path / "ws"
    ws.mkdir()
    platform = LocalStubPlatform(project_root=tmp_path, workspace_dir=ws)
    return GitTools(platform)


def test_ensure_repo_creates_baseline_commit(tmp_path):
    git = make_git(tmp_path)
    assert not git.is_repo()
    git.ensure_repo()
    assert git.is_repo()
    log = git.log()
    assert len(log) == 1
    assert "baseline" in log[0]


def test_status_reports_new_file(tmp_path):
    git = make_git(tmp_path)
    ws = Path(git._p.workspace_root())
    git.ensure_repo()
    (ws / "novo.py").write_text("x = 1\n")
    status = git.status()
    assert "novo.py" in status


def test_commit_and_diff(tmp_path):
    git = make_git(tmp_path)
    ws = Path(git._p.workspace_root())
    (ws / "arquivo.py").write_text("x = 1\n")
    git.commit("adiciona arquivo.py")
    (ws / "arquivo.py").write_text("x = 2\n")
    diff = git.diff("arquivo.py")
    assert "-x = 1" in diff
    assert "+x = 2" in diff


def test_restore_discards_changes(tmp_path):
    git = make_git(tmp_path)
    ws = Path(git._p.workspace_root())
    (ws / "arquivo.py").write_text("original\n")
    git.commit("versão original")
    (ws / "arquivo.py").write_text("modificado\n")
    git.restore("arquivo.py")
    assert (ws / "arquivo.py").read_text() == "original\n"
