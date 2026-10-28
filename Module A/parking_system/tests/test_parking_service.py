from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from parking.data import Database
from parking.services.admin_service import AuthService, AuthorizationError
from parking.services.parking_service import ParkingError, ParkingService, normalize_plate


CN_TZ = timezone(timedelta(hours=8))


@pytest.fixture
def context(tmp_path):
    database = Database(tmp_path / "parking-service.sqlite3")
    database.initialize()
    auth = AuthService(database)
    admin = auth.bootstrap_admin("admin", "StrongPass123")
    service = ParkingService(database, admin, local_timezone=CN_TZ)
    tomorrow = datetime.combine(
        datetime.now(CN_TZ).date() + timedelta(days=1), time(hour=1), tzinfo=CN_TZ
    )
    return database, auth, admin, service, tomorrow


def test_plate_normalization_removes_display_separators():
    assert normalize_plate(" 陕a · 12-345 ") == "陕A12345"
    with pytest.raises(ParkingError, match="6～8"):
        normalize_plate("陕A1")


def test_full_paid_flow_persists_each_state_and_is_idempotent(context):
    database, _auth, admin, service, entered_at = context
    row = service.enter_vehicle("陕a·12345", "小型车", "blue", at=entered_at)
    assert row.plate == "陕A12345"

    with pytest.raises(ParkingError, match="重复进场"):
        service.enter_vehicle("陕A12345", "小型车", "blue", at=entered_at)

    bill = service.bill("陕A·12345", at=entered_at + timedelta(minutes=200))
    assert bill.record_id == row.record_id
    assert bill.total == Decimal("11.00")
    assert bill.payment_status == "unpaid"

    restarted = ParkingService(database, admin, local_timezone=CN_TZ)
    frozen = restarted.bill("陕A12345", at=entered_at + timedelta(hours=8))
    assert frozen.exit_time == bill.exit_time
    assert frozen.total == bill.total

    with pytest.raises(ParkingError, match="未缴费"):
        restarted.release(row.record_id, at=entered_at + timedelta(minutes=201))

    paid = restarted.pay(row.record_id, at=entered_at + timedelta(minutes=202))
    paid_again = restarted.pay(row.record_id, at=entered_at + timedelta(minutes=203))
    assert paid.payment_status == paid_again.payment_status == "paid"
    assert restarted.stats(now=entered_at + timedelta(minutes=203))["today_income"] == Decimal("11.00")

    released = restarted.release(row.record_id, at=entered_at + timedelta(minutes=204))
    assert released.release_status == "released"
    assert restarted.present_vehicles()[0].status == "等待通过"

    restarted.mark_vehicle_passed(row.record_id)
    assert restarted.present_vehicles()[0].status == "等待落杆"
    with database.connect() as connection:
        stored = connection.execute(
            "SELECT exit_time FROM parking_record WHERE record_id = ?", (row.record_id,)
        ).fetchone()
        assert stored["exit_time"] is None

    restarted.complete_exit(row.record_id, at=entered_at + timedelta(minutes=205))
    restarted.complete_exit(row.record_id, at=entered_at + timedelta(minutes=206))
    assert restarted.present_vehicles() == []


def test_free_bill_can_release_without_payment_click(context):
    _database, _auth, _admin, service, entered_at = context
    row = service.enter_vehicle("陕A54321", "小型车", "green", at=entered_at)
    bill = service.bill("陕A54321", at=entered_at + timedelta(minutes=10))
    assert bill.total == Decimal("0.00")

    released = service.release(row.record_id, at=entered_at + timedelta(minutes=11))
    assert released.payment_status == "paid"
    assert released.release_status == "released"


def test_authorized_release_requires_valid_admin_and_records_reason(context):
    database, auth, admin, _service, entered_at = context
    operator = auth.create_account(admin, "operator", "OperatorPass123", "operator")
    service = ParkingService(database, operator, local_timezone=CN_TZ)
    row = service.enter_vehicle("陕A67890", "小型车", "yellow", at=entered_at)
    service.bill("陕A67890", at=entered_at + timedelta(hours=3))

    with pytest.raises(AuthorizationError):
        service.authorize_release(row.record_id, "设备故障", operator)
    with pytest.raises(AuthorizationError):
        service.list_history(operator)

    released = service.authorize_release(row.record_id, "设备故障，人工核验", admin)
    assert released.payment_status == "authorized"
    assert released.release_status == "released"
    with database.connect() as connection:
        stored = connection.execute(
            "SELECT release_reason, released_by FROM parking_record WHERE record_id = ?",
            (row.record_id,),
        ).fetchone()
        assert stored["release_reason"] == "设备故障，人工核验"
        assert stored["released_by"] == admin.admin_id
    assert service.list_history(admin)[0]["record_id"] == row.record_id


def test_paid_bill_cannot_be_changed_to_authorized_release(context):
    _database, _auth, admin, service, entered_at = context
    row = service.enter_vehicle("陕A11223", "小型车", "blue", at=entered_at)
    service.bill("陕A11223", at=entered_at + timedelta(hours=3))
    service.pay(row.record_id, at=entered_at + timedelta(hours=3, minutes=1))

    with pytest.raises(ParkingError, match="已缴费"):
        service.authorize_release(row.record_id, "不应覆盖已缴费状态", admin)


def test_unknown_plate_and_missing_rule_fail_explicitly(context):
    _database, _auth, _admin, service, entered_at = context
    with pytest.raises(ParkingError, match="未找到"):
        service.bill("陕A99999", at=entered_at)
    with pytest.raises(ParkingError, match="暂无已生效"):
        service.enter_vehicle("陕A99999", "大型车", "yellow", at=entered_at)


def test_same_plate_daily_cap_uses_prior_confirmed_bill(context):
    _database, _auth, _admin, service, day = context
    first = service.enter_vehicle("陕A88888", "小型车", "blue", at=day)
    assert service.bill("陕A88888", at=day + timedelta(hours=8)).total == Decimal("23.00")
    service.pay(first.record_id, at=day + timedelta(hours=8, minutes=1))
    service.release(first.record_id, at=day + timedelta(hours=8, minutes=2))
    service.mark_vehicle_passed(first.record_id)
    service.complete_exit(first.record_id, at=day + timedelta(hours=8, minutes=3))

    second_entry = day + timedelta(hours=9)
    service.enter_vehicle("陕A88888", "小型车", "blue", at=second_entry)
    second_bill = service.bill("陕A88888", at=second_entry + timedelta(hours=8))
    assert second_bill.total == Decimal("7.00")
    assert second_bill.capped
