"""本地运行数据路径。

默认把数据库与备份放在项目的 ``runtime`` 目录。测试、演示或部署时可通过
``PARKING_DATA_DIR`` 指向独立目录，避免混用真实业务库与测试库。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    database: Path
    backups: Path

    @classmethod
    def from_environment(cls, project_root: Path | None = None) -> "RuntimePaths":
        configured = os.environ.get("PARKING_DATA_DIR")
        if configured:
            root = Path(configured).expanduser().resolve()
        else:
            base = project_root or Path(__file__).resolve().parents[1]
            root = (base / "runtime").resolve()
        return cls(root=root, database=root / "parking.sqlite3", backups=root / "backup")

    def ensure_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(parents=True, exist_ok=True)
