from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from parking.data import Database
from parking.services.admin_service import AuthService, AuthorizationError
from parking.services.parking_service import ParkingService
from parking.services.report_service import ReportService


CN_TZ = timezone(timedelta(hours=8))


def _complete(service, admin, plate, entered_at, minutes, *, authorized=False):
    row = service.enter_vehicle(plate, "小型车", "blue", at=entered_at)
    cutoff = entered_at + timedelta(minutes=minutes)
    bill = service.bill(plate, at=cutoff)
    if authorized:
        service.authorize_release(row.record_id, "测试授权放行", admin, at=cutoff)
    else:
        service.pay(row.record_id, at=cutoff)
        service.release(row.record_id, at=cutoff)
    service.mark_vehicle_passed(row.record_id)
    service.complete_exit(row.record_id, at=cutoff + timedelta(minutes=1))
    return bill


@pytest.fixture
def report_context(tmp_path):
    database = Database(tmp_path / "reports.sqlite3")
    database.initialize()
    auth = AuthService(database)
    admin = auth.bootstrap_admin("admin", "StrongPass123")
    operator = auth.create_account(admin, "operator", "OperatorPass123", "operator")
    with database.transaction() as connection:
        connection.execute(
            "UPDATE fee_rule SET effective_at = '2020-01-01T00:00:00Z'"
        )
    parking = ParkingService(database, admin, local_timezone=CN_TZ)
    reports = ReportService(database, local_timezone=CN_TZ)
    return database, admin, operator, parking, reports


def test_five_dimensions_use_entry_time_and_iso_year(report_context):
    _database, admin, _operator, parking, reports = report_context
    first = _complete(
        parking, admin, "陕A10001", datetime(2025, 12, 29, 8, tzinfo=CN_TZ), 100
    )
    second = _complete(
        parking,
        admin,
        "陕A10002",
        datetime(2026, 1, 2, 9, tzinfo=CN_TZ),
        200,
        authorized=True,
    )
    _complete(
        parking, admin, "陕A10003", datetime(2026, 1, 10, 10, tzinfo=CN_TZ), 10
    )
    parking.enter_vehicle(
        "陕A10004", "小型车", "blue", at=datetime(2026, 1, 11, 10, tzinfo=CN_TZ)
    )

    start = datetime(2025, 12, 28, tzinfo=CN_TZ)
    end = datetime(2026, 2, 1, tzinfo=CN_TZ)
    weekly = reports.query(admin, start, end, "week")
    assert weekly.vehicle_count == 3
    assert weekly.periods[0].key == "2026-W01"
    assert weekly.periods[0].vehicle_count == 2
    assert weekly.periods[0].receivable == first.total + second.total
    assert weekly.periods[0].received == first.total
    assert weekly.periods[0].authorized_count == 1
    assert weekly.periods[0].authorized_uncollected == second.total

    expected_keys = {
        "day": ["2025-12-29", "2026-01-02", "2026-01-10"],
        "month": ["2025-12", "2026-01"],
        "quarter": ["2025-Q4", "2026-Q1"],
        "year": ["2025", "2026"],
    }
    for dimension, keys in expected_keys.items():
        result = reports.query(admin, start, end, dimension)
        assert [period.key for period in result.periods] == keys


def test_report_range_is_start_inclusive_end_exclusive(report_context):
    _database, admin, _operator, parking, reports = report_context
    _complete(
        parking, admin, "陕A20001", datetime(2026, 1, 1, tzinfo=CN_TZ), 20
    )
    _complete(
        parking, admin, "陕A20002", datetime(2026, 2, 1, tzinfo=CN_TZ), 20
    )
    result = reports.query(
        admin,
        datetime(2026, 1, 1, tzinfo=CN_TZ),
        datetime(2026, 2, 1, tzinfo=CN_TZ),
        "month",
    )
    assert result.vehicle_count == 1
    assert result.details[0].plate_no == "陕A20001"


def test_reports_require_admin_and_aware_valid_range(report_context):
    _database, admin, operator, _parking, reports = report_context
    start = datetime(2026, 1, 1, tzinfo=CN_TZ)
    end = datetime(2026, 2, 1, tzinfo=CN_TZ)
    with pytest.raises(AuthorizationError):
        reports.query(operator, start, end, "month")
    with pytest.raises(ValueError, match="时区"):
        reports.query(admin, datetime(2026, 1, 1), end, "month")
    with pytest.raises(ValueError, match="晚于"):
        reports.query(admin, end, start, "month")
    with pytest.raises(ValueError, match="维度"):
        reports.query(admin, start, end, "invalid")


def test_report_totals_keep_receivable_received_and_authorized_separate(report_context):
    _database, admin, _operator, parking, reports = report_context
    paid = _complete(
        parking, admin, "陕A30001", datetime(2026, 3, 1, 8, tzinfo=CN_TZ), 200
    )
    authorized = _complete(
        parking,
        admin,
        "陕A30002",
        datetime(2026, 3, 2, 8, tzinfo=CN_TZ),
        720,
        authorized=True,
    )
    result = reports.query(
        admin,
        datetime(2026, 3, 1, tzinfo=CN_TZ),
        datetime(2026, 4, 1, tzinfo=CN_TZ),
        "month",
    )
    assert result.receivable == paid.total + authorized.total
    assert result.received == paid.total
    assert result.authorized_count == 1
    assert result.authorized_uncollected == authorized.total
    assert result.receivable == Decimal("41.00")
