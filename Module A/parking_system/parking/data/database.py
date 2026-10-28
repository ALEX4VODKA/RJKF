"""SQLite 连接、初始化、事务与每日备份。"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 1
DEFAULT_BUSY_TIMEOUT_MS = 5000


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    def _open(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {DEFAULT_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")

        with self.connect() as connection:
            current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current_version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"数据库版本 {current_version} 高于程序支持版本 {SCHEMA_VERSION}"
                )
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{schema}\n"
                f"PRAGMA user_version = {SCHEMA_VERSION};\n"
                "COMMIT;"
            )
            try:
                connection.executescript(script)
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def backup_daily(
        self,
        backup_dir: str | Path,
        *,
        today: date | None = None,
        retain: int = 7,
    ) -> Path:
        if retain < 1:
            raise ValueError("备份保留数量必须大于 0")
        if not self.path.exists():
            raise FileNotFoundError(self.path)

        target_dir = Path(backup_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        backup_date = today or date.today()
        target = target_dir / f"parking_{backup_date:%Y%m%d}.sqlite3"

        if not target.exists():
            with self.connect() as source, closing(sqlite3.connect(target)) as destination:
                with destination:
                    source.backup(destination)

        backups = sorted(target_dir.glob("parking_????????.sqlite3"), reverse=True)
        for obsolete in backups[retain:]:
            obsolete.unlink()
        return target
