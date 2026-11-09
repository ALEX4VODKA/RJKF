from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_windows_package_uses_ascii_directory_for_qtwebengine():
    spec = (PROJECT_DIR / "parking_system.spec").read_text(encoding="utf-8")
    build_script = (PROJECT_DIR / "tools" / "build_windows.py").read_text(
        encoding="utf-8"
    )

    assert 'name="智慧停车收费系统"' in spec
    assert 'name="ParkingSystem"' in spec
    assert "console=False" in spec
    assert 'APP_DIR_NAME = "ParkingSystem"' in build_script
    assert 'ARCHIVE_NAME = "智慧停车收费系统"' in build_script
