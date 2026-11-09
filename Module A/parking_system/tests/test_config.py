from pathlib import Path

import parking.config as config
from parking.config import RuntimePaths, application_directory


def test_frozen_application_dir_uses_executable_parent(monkeypatch, tmp_path):
    executable = tmp_path / "智慧停车收费系统.exe"
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(executable))

    assert application_directory(tmp_path / "_internal") == tmp_path


def test_runtime_path_can_be_isolated_with_environment(monkeypatch, tmp_path):
    configured = tmp_path / "demo-data"
    monkeypatch.setenv("PARKING_DATA_DIR", str(configured))

    paths = RuntimePaths.from_environment(Path("unused"))
    paths.ensure_directories()

    assert paths.root == configured.resolve()
    assert paths.database == configured.resolve() / "parking.sqlite3"
    assert paths.backups.is_dir()
