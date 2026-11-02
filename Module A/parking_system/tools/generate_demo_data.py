"""生成独立的停车场演示数据库。"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from parking.demo_data import (  # noqa: E402
    DEFAULT_SEED,
    DEFAULT_START_DATE,
    default_demo_path,
    generate_demo_database,
)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式应为 YYYY-MM-DD") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=default_demo_path(PROJECT_DIR))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--start-date", type=_date, default=DEFAULT_START_DATE)
    parser.add_argument("--plates", type=int, default=240)
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument(
        "--force",
        action="store_true",
        help="确认覆盖不是本工具生成的既有目标；实际业务数据库始终禁止覆盖",
    )
    args = parser.parse_args(argv)
    summary = generate_demo_database(
        args.output,
        project_root=PROJECT_DIR,
        seed=args.seed,
        start_date=args.start_date,
        plate_count=args.plates,
        record_count=args.records,
        force=args.force,
    )
    print(f"演示数据库：{summary.database_path}")
    print(f"固定随机种子：{summary.seed}")
    print(f"车牌 / 记录：{summary.plate_count} / {summary.record_count}")
    print(
        "场景："
        + "，".join(f"{name}={count}" for name, count in summary.scenario_counts.items())
    )
    print(f"异常车牌测试输入：{summary.abnormal_plate_count}")
    print("演示登录：admin=demo_admin，password=DemoPass123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
