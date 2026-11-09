"""生成独立、可重复的停车场演示数据库。"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from parking.config import RuntimePaths
from parking.data import Database
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService


DEMO_GENERATOR_ID = "parking-demo-v1"
DEFAULT_SEED = 20261030
DEFAULT_START_DATE = date(2025, 10, 1)
SCENARIOS = ("free", "first", "extra", "cap", "cross_day")
CN_TZ = timezone(timedelta(hours=8))
ABNORMAL_PLATES = (
    "",
    "陕A1",
    "陕A123456789",
    "陕A12@345",
    "陕A12/345",
    "陕A12.345",
    "陕A12_345",
    "陕A12#345",
    "陕A12?345",
    "陕A12:345",
    "陕A12，345",
    "陕A12$345",
    "陕A12%345",
    "陕A12&345",
    "陕A12*345",
    "陕A12+345",
    "陕A12=345",
    "陕A12(345",
    "陕A12)345",
    "陕A12[345",
    "陕A12]345",
    "陕A12{345",
    "陕A12}345",
    "陕A12;345",
    "陕A12!345",
    "陕A😀1234",
)


@dataclass(frozen=True)
class DemoDataSummary:
    database_path: Path
    seed: int
    start_date: date
    plate_count: int
    record_count: int
    scenario_counts: dict[str, int]
    abnormal_plate_count: int


def default_demo_path(project_root: Path) -> Path:
    return (project_root / "runtime" / "demo" / "parking.sqlite3").resolve()


def _base36(value: int, width: int = 5) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = ""
    while value:
        value, remainder = divmod(value, len(alphabet))
        result = alphabet[remainder] + result
    return result.rjust(width, "0")


def _is_managed_demo(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with closing(sqlite3.connect(path)) as connection:
            row = connection.execute(
                """
                SELECT value FROM demo_dataset_metadata
                WHERE key = 'generator_id'
                """
            ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None and row[0] == DEMO_GENERATOR_ID


def _duration_for(scenario: str, rng: random.Random) -> timedelta:
    if scenario == "free":
        return timedelta(minutes=rng.randint(5, 14))
    if scenario == "first":
        return timedelta(minutes=rng.randint(16, 120))
    if scenario == "extra":
        return timedelta(minutes=rng.randint(180, 540))
    if scenario == "cap":
        return timedelta(hours=12)
    return timedelta(hours=26)


def _entry_time(index: int, scenario: str, start_date: date, rng: random.Random) -> datetime:
    day = start_date + timedelta(days=(index * 137) % 365)
    if scenario == "cap":
        clock = time(6, rng.randrange(0, 60))
    elif scenario == "cross_day":
        clock = time(10, rng.randrange(0, 60))
    else:
        clock = time(rng.randrange(7, 20), rng.randrange(0, 60))
    return datetime.combine(day, clock, tzinfo=CN_TZ)


def generate_demo_database(
    output: str | Path,
    *,
    project_root: str | Path,
    seed: int = DEFAULT_SEED,
    start_date: date = DEFAULT_START_DATE,
    plate_count: int = 240,
    record_count: int = 1000,
    admin_username: str = "demo_admin",
    admin_password: str = "DemoPass123",
    force: bool = False,
) -> DemoDataSummary:
    if plate_count < 1:
        raise ValueError("演示车牌数量必须大于 0")
    if record_count < 1:
        raise ValueError("演示记录数量必须大于 0")

    root = Path(project_root).resolve()
    target = Path(output).resolve()
    primary = RuntimePaths.from_environment(root).database.resolve()
    if target == primary:
        raise ValueError("演示数据禁止写入实际业务数据库")
    if target.exists() and not force and not _is_managed_demo(target):
        raise FileExistsError("目标不是本工具创建的演示数据库；如确认覆盖请使用 force=True")

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="parking_demo_", suffix=".sqlite3", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    rng = random.Random(seed)
    scenario_counts = {scenario: 0 for scenario in SCENARIOS}

    try:
        database = Database(temporary)
        database.initialize()
        auth = AuthService(database)
        admin = auth.bootstrap_admin(admin_username, admin_password)
        service = ParkingService(database, admin, local_timezone=CN_TZ)
        with database.transaction() as connection:
            connection.execute(
                "UPDATE fee_rule SET effective_at = ? WHERE vehicle_type = '小型车'",
                ((start_date - timedelta(days=1)).isoformat() + "T00:00:00Z",),
            )
            connection.executescript(
                """
                CREATE TABLE demo_dataset_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE demo_record_scenario (
                    record_id INTEGER PRIMARY KEY,
                    scenario TEXT NOT NULL,
                    FOREIGN KEY (record_id) REFERENCES parking_record(record_id) ON DELETE CASCADE
                );
                CREATE TABLE demo_abnormal_plate_case (
                    case_id INTEGER PRIMARY KEY,
                    plate_input TEXT NOT NULL
                );
                """
            )

        plates = [f"陕A{_base36(index)}" for index in range(plate_count)]
        colors = ("blue", "yellow", "green", "white", "black", "other")
        for index in range(record_count):
            scenario = SCENARIOS[index % len(SCENARIOS)]
            entered_at = _entry_time(index, scenario, start_date, rng)
            cutoff_at = entered_at + _duration_for(scenario, rng)
            plate = plates[index % len(plates)]
            row = service.enter_vehicle(
                plate,
                "小型车",
                colors[index % len(colors)],
                source="demo",
                at=entered_at,
            )
            service.bill(plate, at=cutoff_at)
            if index % 11 == 0:
                service.authorize_release(
                    row.record_id,
                    "演示数据：人工授权放行",
                    admin,
                    at=cutoff_at + timedelta(minutes=1),
                )
            else:
                service.pay(row.record_id, at=cutoff_at + timedelta(minutes=1))
                service.release(row.record_id, at=cutoff_at + timedelta(minutes=2))
            service.mark_vehicle_passed(row.record_id)
            service.complete_exit(row.record_id, at=cutoff_at + timedelta(minutes=3))
            with database.transaction() as connection:
                connection.execute(
                    "INSERT INTO demo_record_scenario (record_id, scenario) VALUES (?, ?)",
                    (row.record_id, scenario),
                )
            scenario_counts[scenario] += 1

        metadata = {
            "generator_id": DEMO_GENERATOR_ID,
            "seed": str(seed),
            "start_date": start_date.isoformat(),
            "plate_count": str(plate_count),
            "record_count": str(record_count),
            "scenario_counts": json.dumps(scenario_counts, sort_keys=True),
        }
        with database.transaction() as connection:
            connection.executemany(
                "INSERT INTO demo_dataset_metadata (key, value) VALUES (?, ?)",
                metadata.items(),
            )
            connection.executemany(
                "INSERT INTO demo_abnormal_plate_case (case_id, plate_input) VALUES (?, ?)",
                enumerate(ABNORMAL_PLATES, start=1),
            )
        with database.connect() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(target) + suffix)
            if sidecar.exists():
                try:
                    sidecar.unlink()
                except PermissionError as exc:
                    raise PermissionError(
                        f"演示数据库正在被占用，请关闭使用它的程序后重试：{target}"
                    ) from exc
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(temporary) + suffix)
            if sidecar.exists():
                sidecar.unlink()

    return DemoDataSummary(
        database_path=target,
        seed=seed,
        start_date=start_date,
        plate_count=plate_count,
        record_count=record_count,
        scenario_counts=scenario_counts,
        abnormal_plate_count=len(ABNORMAL_PLATES),
    )
