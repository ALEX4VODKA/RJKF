from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from parking.data import (
    AdminRepository,
    AuditRepository,
    Database,
    FeeRuleRepository,
    RecordRepository,
    VehicleRepository,
)
from parking.services.admin_service import (
    AuthenticationError,
    AuthorizationError,
    AuthService,
    UserSession,
)
from parking.services.rule_service import RuleDraft, RuleService


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / "parking.sqlite3")
    database.initialize()
    return database


@pytest.fixture
def admin(database):
    return AuthService(database).bootstrap_admin("admin", "StrongPass123")


def test_bootstrap_hashes_password_and_login_succeeds(database):
    auth = AuthService(database)
    session = auth.bootstrap_admin("admin", "StrongPass123")

    with database.connect() as connection:
        row = AdminRepository(connection).find_by_username("admin")
        assert row["password_hash"] != "StrongPass123"
        assert row["salt"]
        assert AuditRepository(connection).list_recent()[0]["action"] == "account.bootstrap"

    logged_in = auth.authenticate("admin", "StrongPass123")
    assert logged_in == session


def test_five_failures_lock_account_for_five_minutes(database):
    auth = AuthService(database)
    auth.bootstrap_admin("admin", "StrongPass123")
    now = datetime(2026, 10, 28, 4, 0, tzinfo=timezone.utc)

    for _ in range(4):
        with pytest.raises(AuthenticationError, match="用户名或密码错误"):
            auth.authenticate("admin", "wrong", now=now)
    with pytest.raises(AuthenticationError, match="锁定 5 分钟"):
        auth.authenticate("admin", "wrong", now=now)
    with pytest.raises(AuthenticationError, match="已锁定"):
        auth.authenticate("admin", "StrongPass123", now=now + timedelta(minutes=4))

    session = auth.authenticate(
        "admin", "StrongPass123", now=now + timedelta(minutes=5, seconds=1)
    )
    assert session.is_admin
    with database.connect() as connection:
        row = AdminRepository(connection).find_by_username("admin")
        assert row["fail_count"] == 0
        assert row["locked_until"] is None


def test_operator_cannot_manage_rules(database, admin):
    auth = AuthService(database)
    operator = auth.create_account(admin, "operator", "Operator123", "operator")
    with pytest.raises(AuthorizationError):
        RuleService(database).list_rules(operator)

    forged = UserSession(operator.admin_id, operator.username, "admin")
    with pytest.raises(AuthorizationError, match="身份校验失败"):
        RuleService(database).list_rules(forged)
    with pytest.raises(AuthorizationError, match="身份校验失败"):
        auth.create_account(forged, "fakeadmin", "FakeAdmin123", "admin")
    with pytest.raises(AuthorizationError):
        auth.list_audit_events(operator)
    assert auth.list_audit_events(admin)


def test_password_change_invalidates_old_password(database):
    auth = AuthService(database)
    admin = auth.bootstrap_admin("admin", "StrongPass123")
    auth.change_password(admin, "StrongPass123", "NewStrongPass456")

    with pytest.raises(AuthenticationError):
        auth.authenticate("admin", "StrongPass123")
    assert auth.authenticate("admin", "NewStrongPass456").is_admin


def test_rule_update_creates_version_and_preserves_record_snapshot(database, admin):
    service = RuleService(database)
    original = service.list_rules(admin)[0]
    entered_at = datetime.now(timezone.utc)
    with database.transaction() as connection:
        VehicleRepository(connection).upsert("陕A12345", "小型车", "blue")
        record_id = RecordRepository(connection).create_open(
            "陕A12345", original.rule_id, entered_at
        )

    effective = max(datetime.now(timezone.utc), original.effective_at) + timedelta(seconds=1)
    updated = service.update_rule(
        admin,
        original.rule_id,
        RuleDraft(
            vehicle_type="小型车",
            free_minutes=20,
            first_hours=2,
            first_price=Decimal("6.00"),
            extra_price=Decimal("4.00"),
            day_cap=Decimal("35.00"),
            effective_at=effective,
        ),
    )

    assert updated.version == original.version + 1
    assert updated.supersedes_rule_id == original.rule_id
    with database.connect() as connection:
        record = connection.execute(
            "SELECT * FROM parking_record WHERE record_id = ?", (record_id,)
        ).fetchone()
        assert record["rule_first_price_cents"] == 500
        latest = FeeRuleRepository(connection).latest_for(
            "小型车", effective + timedelta(seconds=1)
        )
        assert latest["rule_id"] == updated.rule_id
        actions = [row["action"] for row in AuditRepository(connection).list_recent()]
        assert "fee_rule.update" in actions

    with pytest.raises(ValueError, match="最新版本"):
        service.update_rule(
            admin,
            original.rule_id,
            RuleDraft(
                vehicle_type="小型车",
                free_minutes=15,
                first_hours=2,
                first_price=Decimal("7.00"),
                extra_price=Decimal("4.00"),
                day_cap=Decimal("40.00"),
                effective_at=effective + timedelta(seconds=1),
            ),
        )


def test_deactivate_disables_all_versions_without_deleting_history(database, admin):
    service = RuleService(database)
    original = service.list_rules(admin)[0]
    effective = max(datetime.now(timezone.utc), original.effective_at) + timedelta(seconds=1)
    updated = service.update_rule(
        admin,
        original.rule_id,
        RuleDraft(
            vehicle_type="小型车",
            free_minutes=15,
            first_hours=2,
            first_price=Decimal("6.00"),
            extra_price=Decimal("3.00"),
            day_cap=Decimal("30.00"),
            effective_at=effective,
        ),
    )
    assert service.deactivate_rule(admin, updated.rule_id) == 2

    history = service.list_rules(admin)
    assert len(history) == 2
    assert not any(rule.active for rule in history)
    with database.connect() as connection:
        assert (
            FeeRuleRepository(connection).latest_for(
                "小型车", effective + timedelta(days=1)
            )
            is None
        )


def test_create_rule_validates_values_and_is_audited(database, admin):
    service = RuleService(database)
    effective = datetime.now(timezone.utc) + timedelta(minutes=1)
    created = service.create_rule(
        admin,
        RuleDraft(
            vehicle_type="大型车",
            free_minutes=10,
            first_hours=1,
            first_price=Decimal("8.00"),
            extra_price=Decimal("5.00"),
            day_cap=Decimal("50.00"),
            effective_at=effective,
        ),
    )
    assert created.version == 1
    assert created.first_price == Decimal("8.00")

    with pytest.raises(ValueError, match="日封顶"):
        service.create_rule(
            admin,
            RuleDraft(
                vehicle_type="超大型车",
                free_minutes=10,
                first_hours=1,
                first_price=Decimal("20.00"),
                extra_price=Decimal("5.00"),
                day_cap=Decimal("10.00"),
                effective_at=effective,
            ),
        )
    with database.connect() as connection:
        actions = [row["action"] for row in AuditRepository(connection).list_recent()]
        assert actions.count("fee_rule.create") == 1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"free_minutes": 121}, "免费时长"),
        ({"first_hours": 0}, "首时段"),
        ({"first_price": Decimal("0.00")}, "价格"),
        ({"extra_price": Decimal("0.00")}, "单价"),
        ({"day_cap": Decimal("4.00")}, "日封顶"),
    ],
)
def test_rule_parameter_ranges_are_enforced(database, admin, changes, message):
    values = {
        "vehicle_type": "测试车型",
        "free_minutes": 15,
        "first_hours": 2,
        "first_price": Decimal("5.00"),
        "extra_price": Decimal("3.00"),
        "day_cap": Decimal("30.00"),
        "effective_at": datetime.now(timezone.utc) + timedelta(minutes=1),
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        RuleService(database).create_rule(admin, RuleDraft(**values))


def test_rule_effective_time_cannot_be_before_today(database, admin):
    with pytest.raises(ValueError, match="当天零点"):
        RuleService(database).create_rule(
            admin,
            RuleDraft(
                vehicle_type="过期车型",
                free_minutes=15,
                first_hours=2,
                first_price=Decimal("5.00"),
                extra_price=Decimal("3.00"),
                day_cap=Decimal("30.00"),
                effective_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
        )
