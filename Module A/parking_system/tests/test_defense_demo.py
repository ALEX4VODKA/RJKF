from datetime import datetime, timedelta, timezone
from pathlib import Path

from parking.data import Database
from parking.defense_demo import (
    DEMO_PASSWORD,
    DEMO_USERNAME,
    install_packaged_demo,
    prepare_defense_demo,
)
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService


def test_defense_demo_prepares_current_reports_and_repeatable_case_vehicles(tmp_path):
    now = datetime(2026, 11, 9, 16, 30, tzinfo=timezone(timedelta(hours=8)))
    target = tmp_path / "defense" / "parking.sqlite3"

    summary = prepare_defense_demo(tmp_path, output=target, now=now)

    assert summary.database_path == target.resolve()
    assert summary.report_start_date == now.date() - timedelta(days=364)
    database = Database(target)
    admin = AuthService(database).authenticate(DEMO_USERNAME, DEMO_PASSWORD)
    assert admin.username == "test"
    service = ParkingService(database, admin, local_timezone=now.tzinfo)
    present = {row.plate for row in service.present_vehicles()}
    assert set(summary.open_plates) <= present
    assert service.bill("陕A90002", at=now).total == 11
    assert service.bill("陕A90003", at=now).total == 0
    cross_day = service.get_bill(next(row.record_id for row in service.present_vehicles() if row.plate == "陕A90009"))
    assert cross_day.minutes == 26 * 60
    assert cross_day.total == 60
    assert cross_day.capped is True

    with database.connect() as connection:
        report_count = connection.execute(
            "SELECT COUNT(*) FROM parking_record WHERE entry_time >= ?",
            ((now - timedelta(days=30)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),),
        ).fetchone()[0]
    assert report_count > 0


def test_packaged_demo_template_is_copied_without_sidecars(tmp_path):
    source = tmp_path / "template.sqlite3"
    source.write_bytes(b"demo-template")
    target = tmp_path / "runtime" / "defense_demo" / "parking.sqlite3"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    Path(str(target) + "-wal").write_bytes(b"wal")
    Path(str(target) + "-shm").write_bytes(b"shm")

    assert install_packaged_demo(source, target) == target.resolve()
    assert target.read_bytes() == b"demo-template"
    assert not Path(str(target) + "-wal").exists()
    assert not Path(str(target) + "-shm").exists()
