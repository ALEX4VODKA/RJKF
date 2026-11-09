"""准备独立答辩数据并启动本地桌面程序。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from parking.defense_demo import (  # noqa: E402
    DEMO_PASSWORD,
    DEMO_USERNAME,
    default_defense_path,
    prepare_defense_demo,
)
from parking.recognition.service import MODEL_FILES, MODEL_VERSION  # noqa: E402


def _model_root(project_dir: Path) -> Path | None:
    for root in (project_dir / "runtime", project_dir / "runtime" / "demo"):
        model_dir = root / ".hyperlpr3" / MODEL_VERSION / "onnx"
        if all((model_dir / name).is_file() for name in MODEL_FILES):
            return root / ".hyperlpr3"
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=default_defense_path(PROJECT_DIR))
    parser.add_argument("--prepare-only", action="store_true", help="只重置演示数据，不启动界面")
    args = parser.parse_args(argv)

    try:
        summary = prepare_defense_demo(PROJECT_DIR, output=args.output)
    except (OSError, ValueError, PermissionError) as exc:
        print(f"答辩演示数据准备失败：{exc}", file=sys.stderr)
        return 1

    print(f"答辩演示数据库：{summary.database_path}")
    print(f"报表数据起点：{summary.report_start_date.isoformat()}（最近 30 天已有数据）")
    print(f"登录账号：{DEMO_USERNAME}；密码：{DEMO_PASSWORD}")
    print("预置在场车牌：" + "、".join(summary.open_plates))
    if args.prepare_only:
        return 0

    environment = os.environ.copy()
    environment["PARKING_DATA_DIR"] = str(summary.database_path.parent)
    environment["PARKING_DEFENSE_MODE"] = "1"
    model_home = _model_root(PROJECT_DIR)
    if model_home is not None:
        environment["PARKING_RECOGNITION_MODEL_DIR"] = str(model_home)
    else:
        print("未发现本地离线模型；界面仍可演示人工流程，真实识别前请先运行 setup_recognition.py。", file=sys.stderr)

    subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / "app.py"), "--defense-mode"],
        cwd=str(PROJECT_DIR),
        env=environment,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
