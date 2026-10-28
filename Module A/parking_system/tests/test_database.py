from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone

import pytest

from parking.data import Database, FeeRuleRepository, RecordRepository, VehicleRepository


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / "parking.sqlite3")
    database.initialize()
    return database


def test_initialize_is_idempotent_and_enables_required_pragmas(database):
    database.initialize()

    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "admin",
            "vehicle",
            "fee_rule",
            "parking_record",
            "bill_daily_detail",
            "operation_log",
        }.issubset(tables)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        rules = FeeRuleRepository(connection)
        assert len(rules.list_all()) == 1
        assert rules.latest_for("小型车", datetime.now(timezone.utc)) is not None


def test_initialize_rolls_back_partial_schema_on_error(tmp_path):
    path = tmp_path / "broken.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE fee_rule (broken INTEGER)")

    with pytest.raises(sqlite3.OperationalError):
        Database(path).initialize()

    with closing(sqlite3.connect(path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "fee_rule" in tables
        assert "admin" not in tables
        assert "vehicle" not in tables


def test_repository_data_persists_across_connections(database):
    entered_at = datetime(2026, 10, 28, 8, 30, tzinfo=timezone.utc)
    with database.transaction() as connection:
        VehicleRepository(connection).upsert("陕A12345", "小型车", "blue")
        rule = FeeRuleRepository(connection).list_all()[0]
        record_id = RecordRepository(connection).create_open(
            "陕A12345", rule["rule_id"], entered_at
        )

    reopened = Database(database.path)
    with reopened.connect() as connection:
        vehicle = VehicleRepository(connection).get("陕A12345")
        record = RecordRepository(connection).find_open("陕A12345")
        assert vehicle["plate_color"] == "blue"
        assert record["record_id"] == record_id
        assert record["rule_first_price_cents"] == 500


def test_transaction_rolls_back_on_error(database):
    with pytest.raises(RuntimeError):
        with database.transaction() as connection:
            VehicleRepository(connection).upsert("陕A23456", "小型车", "blue")
            raise RuntimeError("force rollback")

    with database.connect() as connection:
        assert VehicleRepository(connection).get("陕A23456") is None


def test_foreign_key_is_enforced(database):
    with database.transaction() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO operation_log (admin_id, action) VALUES (?, ?)",
                (999, "invalid-admin"),
            )


def test_same_plate_cannot_have_two_open_records(database):
    entered_at = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
    with database.transaction() as connection:
        VehicleRepository(connection).upsert("陕A34567", "小型车", "blue")
        rule = FeeRuleRepository(connection).list_all()[0]
        records = RecordRepository(connection)
        records.create_open("陕A34567", rule["rule_id"], entered_at)
        with pytest.raises(sqlite3.IntegrityError):
            records.create_open("陕A34567", rule["rule_id"], entered_at)


def test_record_rejects_naive_datetime(database):
    with database.transaction() as connection:
        VehicleRepository(connection).upsert("陕A56789", "小型车", "blue")
        rule = FeeRuleRepository(connection).list_all()[0]
        with pytest.raises(ValueError, match="时区"):
            RecordRepository(connection).create_open(
                "陕A56789", rule["rule_id"], datetime(2026, 10, 28, 10, 0)
            )


def test_daily_backup_is_idempotent_and_restorable(database, tmp_path):
    with database.transaction() as connection:
        VehicleRepository(connection).upsert("陕A45678", "小型车", "green")

    backup_dir = tmp_path / "backup"
    first = database.backup_daily(backup_dir, today=date(2026, 10, 28))
    second = database.backup_daily(backup_dir, today=date(2026, 10, 28))
    assert first == second

    restored = Database(first)
    with restored.connect() as connection:
        assert VehicleRepository(connection).get("陕A45678") is not None


def test_daily_backup_retains_latest_seven(database, tmp_path):
    backup_dir = tmp_path / "backup-retention"
    for day in range(1, 9):
        database.backup_daily(backup_dir, today=date(2026, 10, day))

    backups = sorted(backup_dir.glob("parking_*.sqlite3"))
    assert len(backups) == 7
    assert not (backup_dir / "parking_20261001.sqlite3").exists()
    assert (backup_dir / "parking_20261008.sqlite3").exists()
