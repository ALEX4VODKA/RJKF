from pathlib import Path

from parking.config import RuntimePaths


def test_runtime_path_can_be_isolated_with_environment(monkeypatch, tmp_path):
    configured = tmp_path / "demo-data"
    monkeypatch.setenv("PARKING_DATA_DIR", str(configured))

    paths = RuntimePaths.from_environment(Path("unused"))
    paths.ensure_directories()

    assert paths.root == configured.resolve()
    assert paths.database == configured.resolve() / "parking.sqlite3"
    assert paths.backups.is_dir()
