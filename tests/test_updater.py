import os, sys, tempfile, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

class TestVersionComparison:
    def test_compare(self):
        from updater.checker import _compare_versions
        assert _compare_versions("11.1.0", "11.0.0") > 0
        assert _compare_versions("11.0.0", "11.0.0") == 0
        assert _compare_versions("10.9.0", "11.0.0") < 0
        assert _compare_versions("11.0", "11.0.0") == 0

    def test_parse_tag(self):
        from updater.checker import _parse_version_from_tag
        assert _parse_version_from_tag("v11.0.0") == "11.0.0"
        assert _parse_version_from_tag("noversion") is None

    def test_update_info(self):
        from updater.checker import UpdateInfo
        info = UpdateInfo(module_id="core", module_name="Core",
            current_version="11.0.0", latest_version="11.1.0",
            release_url="", download_url="")
        assert info.is_update_available is True

class TestProtection:
    def test_protected(self):
        from updater.installer import _is_protected
        assert _is_protected("config/settings.json") is True
        assert _is_protected("database/aura.db") is True
        assert _is_protected("models/x.gguf") is True
        assert _is_protected("updater/checker.py") is True
        assert _is_protected("ai/ai_engine.py") is False
        assert _is_protected("core/event_bus.py") is False

class TestBackup:
    def test_create_and_rollback(self):
        from updater.installer import create_backup, rollback
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            os.makedirs(os.path.join(src, "ai"))
            os.makedirs(os.path.join(src, "config"))
            with open(os.path.join(src, "ai", "engine.py"), "w") as f: f.write("x=1")
            with open(os.path.join(src, "config", "settings.json"), "w") as f: f.write("{}")
            backup = os.path.join(tmp, "backup")
            assert create_backup(src, backup) is True
            assert os.path.exists(os.path.join(backup, "ai", "engine.py"))
            assert not os.path.exists(os.path.join(backup, "config", "settings.json"))
            with open(os.path.join(src, "ai", "engine.py"), "w") as f: f.write("y=2")
            rollback(backup, src)
            with open(os.path.join(src, "ai", "engine.py")) as f:
                assert f.read() == "x=1"

    def test_zip_update(self):
        from updater.installer import apply_zip_update
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            os.makedirs(os.path.join(src, "ai"))
            zip_path = os.path.join(tmp, "update.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("ai/engine.py", "new=2")
                zf.writestr("config/settings.json", "NO")
            assert apply_zip_update(zip_path, src) is True
            with open(os.path.join(src, "ai", "engine.py")) as f:
                assert f.read() == "new=2"
            assert not os.path.exists(os.path.join(src, "config", "settings.json"))

class TestModule:
    def test_manifest(self):
        from updater import MODULES, __version__
        from core.version import AURA_VERSION
        assert __version__ == AURA_VERSION
        assert "core" in MODULES
        assert all("version" in m for m in MODULES.values())

    def test_critical(self):
        from updater.installer import CRITICAL_MODULES
        assert len(CRITICAL_MODULES) >= 5
        assert "core.event_bus" in CRITICAL_MODULES

    def test_offline_no_crash(self):
        from updater.checker import check_for_updates
        updates = check_for_updates()
        assert isinstance(updates, list)

    def test_sha256(self):
        from updater.downloader import sha256_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test")
            p = f.name
        try:
            h = sha256_file(p)
            assert len(h) == 64
        finally:
            os.unlink(p)
