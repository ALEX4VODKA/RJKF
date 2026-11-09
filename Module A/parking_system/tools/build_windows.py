"""构建 Windows x64 便携目录和 ZIP 交付包。"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
DIST_DIR = PROJECT_DIR / "dist"
APP_DIR_NAME = "ParkingSystem"
ARCHIVE_NAME = "智慧停车收费系统"
APP_DIR = DIST_DIR / APP_DIR_NAME
ZIP_PATH = DIST_DIR / f"{ARCHIVE_NAME}_Windows_x64.zip"
MODEL_SOURCE = PROJECT_DIR / "runtime" / ".hyperlpr3"
MODEL_DESTINATION = APP_DIR / "runtime" / ".hyperlpr3"
DEMO_TEMPLATE = APP_DIR / "demo-template" / "parking.sqlite3"


def _require(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"缺少{label}：{path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("该构建脚本仅支持 Windows")
    _require(PROJECT_DIR / "parking_system.spec", "PyInstaller 配置")
    _require(PROJECT_DIR / "resources" / "model" / "parking.glb", "3D 模型")
    _require(PROJECT_DIR / "viewer" / "index.html", "3D 查看器")
    _require(MODEL_SOURCE / "20230229" / "onnx", "离线车牌模型")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(PROJECT_DIR / "build" / "pyinstaller"),
            str(PROJECT_DIR / "parking_system.spec"),
        ],
        cwd=PROJECT_DIR,
        check=True,
    )

    MODEL_DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(MODEL_SOURCE, MODEL_DESTINATION, dirs_exist_ok=True)
    shutil.copy2(PROJECT_DIR / "README_运行说明.txt", APP_DIR / "README_运行说明.txt")
    shutil.copy2(PROJECT_DIR / "一键演示.cmd", APP_DIR / "一键演示.cmd")

    from parking.defense_demo import prepare_defense_demo

    prepare_defense_demo(PROJECT_DIR, output=DEMO_TEMPLATE)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    shutil.make_archive(
        str(ZIP_PATH.with_suffix("")),
        "zip",
        root_dir=DIST_DIR,
        base_dir=APP_DIR_NAME,
    )
    print(f"程序目录：{APP_DIR}")
    print(f"交付压缩包：{ZIP_PATH}")
    print(f"ZIP SHA-256：{_sha256(ZIP_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
