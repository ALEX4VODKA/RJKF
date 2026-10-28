"""停车登记、结算、缴费与放行的持久化业务服务。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from parking.billing import FeeRuleSnapshot, calculate_fee, money
from parking.data import (
    AdminRepository,
    AuditRepository,
    Database,
    FeeRuleRepository,
    RecordRepository,
    VehicleRepository,
)
from parking.models import Bill, VehicleRow
from parking.services.admin_service import UserSession, require_admin


PLATE_COLORS = {"blue", "yellow", "green", "white", "black", "other"}
ENTRY_SOURCES = {"manual", "recognition", "demo"}
_PLATE_SEPARATORS = re.compile(r"[\s·•・\-]+")


class ParkingError(ValueError):
    """可直接向操作员展示的业务错误。"""


def normalize_plate(value: str) -> str:
    plate = _PLATE_SEPARATORS.sub("", value or "").upper()
    if not 6 <= len(plate) <= 8:
        raise ParkingError("车牌号应为 6～8 个字符")
    if not all(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in plate):
        raise ParkingError("车牌号包含无效字符")
    return plate


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _cents(amount: Decimal) -> int:
    return int(money(amount) * 100)


def _amount(cents: int | None) -> Decimal:
    return money(Decimal(cents or 0) / 100)


class ParkingService:
    def __init__(
        self,
        database: Database,
        actor: UserSession,
        *,
        capacity: int = 50,
        local_timezone=None,
    ):
        if capacity < 1:
            raise ValueError("停车场容量必须大于 0")
        self.database = database
        self.actor = actor
        self.capacity = capacity
        self.local_timezone = local_timezone or datetime.now().astimezone().tzinfo

    @staticmethod
    def _now(value: datetime | None = None) -> datetime:
        current = value or datetime.now().astimezone()
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("业务时间必须包含时区信息")
        return current

    def _require_actor(self, connection) -> None:
        row = AdminRepository(connection).get(self.actor.admin_id)
        if (
            row is None
            or row["username"] != self.actor.username
            or row["role"] != self.actor.role
        ):
            raise PermissionError("当前登录身份已失效，请重新登录")

    def available_vehicle_types(self, *, at: datetime | None = None) -> list[str]:
        current = self._now(at)
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT vehicle_type FROM fee_rule
                WHERE active = 1 AND effective_at <= ? ORDER BY vehicle_type
                """,
                (current.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),),
            ).fetchall()
        return [row["vehicle_type"] for row in rows]

    def enter_vehicle(
        self,
        plate: str,
        vehicle_type: str,
        plate_color: str,
        *,
        entry_photo: str | None = None,
        source: str = "manual",
        at: datetime | None = None,
    ) -> VehicleRow:
        plate_no = normalize_plate(plate)
        vehicle_type = vehicle_type.strip()
        if not vehicle_type:
            raise ParkingError("请选择收费车型")
        if plate_color not in PLATE_COLORS:
            raise ParkingError("车牌颜色无效")
        if source not in ENTRY_SOURCES:
            raise ParkingError("进场来源无效")
        current = self._now(at)

        with self.database.transaction() as connection:
            self._require_actor(connection)
            records = RecordRepository(connection)
            if records.find_open(plate_no) is not None:
                raise ParkingError(f"{plate_no} 已有未离场记录，不能重复进场")
            rule = FeeRuleRepository(connection).latest_for(vehicle_type, current)
            if rule is None:
                raise ParkingError(f"{vehicle_type} 暂无已生效的收费标准，请先配置")
            VehicleRepository(connection).upsert(plate_no, vehicle_type, plate_color)
            record_id = records.create_open(
                plate_no,
                int(rule["rule_id"]),
                current,
                entry_photo=entry_photo,
                entry_source=source,
            )
            AuditRepository(connection).insert(
                "parking.entry",
                admin_id=self.actor.admin_id,
                target=f"record:{record_id}",
                after_value=json.dumps(
                    {
                        "plate": plate_no,
                        "vehicle_type": vehicle_type,
                        "source": source,
                    },
                    ensure_ascii=False,
                ),
            )
        return VehicleRow(record_id, plate_no, plate_color, current, "在场")

    def present_vehicles(self) -> list[VehicleRow]:
        with self.database.connect() as connection:
            rows = RecordRepository(connection).list_present()
        result = []
        for row in rows:
            status = "在场"
            if row["release_status"] == "passed":
                status = "等待落杆"
            elif row["release_status"] == "released":
                status = "等待通过"
            elif row["payment_status"] == "paid":
                status = "已缴费"
            elif row["payment_status"] == "authorized":
                status = "授权放行"
            elif row["payment_status"] == "unpaid":
                status = "待缴费"
            result.append(
                VehicleRow(
                    int(row["record_id"]),
                    row["plate_no"],
                    row["plate_color"],
                    _parse_utc(row["entry_time"]).astimezone(self.local_timezone),
                    status,
                )
            )
        return result

    def stats(self, *, now: datetime | None = None) -> dict:
        current = self._now(now).astimezone(self.local_timezone)
        local_start = datetime.combine(current.date(), time.min, tzinfo=self.local_timezone)
        local_end = local_start + timedelta(days=1)
        start_text = local_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_text = local_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.database.connect() as connection:
            present = int(
                connection.execute(
                    "SELECT COUNT(*) FROM parking_record WHERE exit_time IS NULL"
                ).fetchone()[0]
            )
            today_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM parking_record
                    WHERE entry_time >= ? AND entry_time < ?
                    """,
                    (start_text, end_text),
                ).fetchone()[0]
            )
            income_cents = int(
                connection.execute(
                    """
                    SELECT COALESCE(SUM(paid_cents), 0) FROM parking_record
                    WHERE payment_status = 'paid' AND paid_at >= ? AND paid_at < ?
                    """,
                    (start_text, end_text),
                ).fetchone()[0]
            )
        return {
            "present": present,
            "today_count": today_count,
            "today_income": _amount(income_cents),
            "free_spaces": max(0, self.capacity - present),
            "capacity": self.capacity,
        }

    def list_history(self, actor: UserSession, *, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 1000:
            raise ValueError("历史记录条数须为 1～1000")
        with self.database.connect() as connection:
            require_admin(actor, connection)
            rows = connection.execute(
                """
                SELECT record_id, plate_no, vehicle_type, entry_time,
                       billing_cutoff_at, fee_cents, payment_status,
                       release_status, release_type, exit_time
                FROM parking_record
                ORDER BY record_id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _rule_from_record(row) -> FeeRuleSnapshot:
        return FeeRuleSnapshot(
            vehicle_type=row["vehicle_type"],
            free_minutes=int(row["rule_free_minutes"]),
            first_hours=int(row["rule_first_hours"]),
            first_price=_amount(row["rule_first_price_cents"]),
            extra_price=_amount(row["rule_extra_price_cents"]),
            day_cap=_amount(row["rule_day_cap_cents"]),
            rule_id=int(row["fee_rule_id"]),
        )

    @staticmethod
    def _prior_usage(rows) -> tuple[dict[date, Decimal], dict[date, Decimal]]:
        due: dict[date, Decimal] = {}
        caps: dict[date, Decimal] = {}
        for row in rows:
            day = date.fromisoformat(row["billing_date"])
            due[day] = money(due.get(day, Decimal("0")) + _amount(row["charged_cents"]))
            caps.setdefault(day, _amount(row["rule_day_cap_cents"]))
        return due, caps

    def bill(
        self,
        plate: str,
        *,
        at: datetime | None = None,
        exit_photo: str | None = None,
    ) -> Bill:
        plate_no = normalize_plate(plate)
        current = self._now(at)
        with self.database.transaction() as connection:
            self._require_actor(connection)
            records = RecordRepository(connection)
            row = records.find_open(plate_no)
            if row is None:
                raise ParkingError(f"未找到 {plate_no} 的在场记录，请人工核对")
            if row["payment_status"] == "unbilled":
                started = _parse_utc(row["entry_time"]).astimezone(self.local_timezone)
                cutoff = current.astimezone(self.local_timezone)
                if cutoff <= started:
                    cutoff = started + timedelta(seconds=1)
                prior_due, cap_limits = self._prior_usage(
                    records.prior_daily_usage(
                        plate_no, excluding_record_id=int(row["record_id"])
                    )
                )
                result = calculate_fee(
                    started,
                    cutoff,
                    self._rule_from_record(row),
                    prior_daily_due=prior_due,
                    daily_cap_limits=cap_limits,
                )
                details = [
                    {
                        "billing_date": item.billing_date.isoformat(),
                        "period_start": item.period_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "period_end": item.period_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "duration_minutes": item.duration_minutes,
                        "fee_before_cap_cents": _cents(item.fee_before_cap),
                        "prior_daily_fee_cents": _cents(item.prior_daily_due),
                        "charged_cents": _cents(item.charged),
                    }
                    for item in result.daily
                ]
                records.freeze_bill(
                    int(row["record_id"]),
                    cutoff_at=cutoff,
                    exit_photo=exit_photo,
                    duration_minutes=result.duration_minutes,
                    fee_cents=_cents(result.total),
                    daily_details=details,
                )
                AuditRepository(connection).insert(
                    "parking.bill.freeze",
                    admin_id=self.actor.admin_id,
                    target=f"record:{row['record_id']}",
                    after_value=json.dumps(
                        {"fee_cents": _cents(result.total), "cutoff": cutoff.isoformat()}
                    ),
                )
                row = records.get(int(row["record_id"]))
            assert row is not None
            details = records.daily_details(int(row["record_id"]))
        return self._bill_from_rows(row, details)

    def get_bill(self, record_id: int) -> Bill:
        with self.database.connect() as connection:
            records = RecordRepository(connection)
            row = records.get(record_id)
            if row is None or row["payment_status"] == "unbilled":
                raise ParkingError("账单不存在或尚未生成")
            details = records.daily_details(record_id)
        return self._bill_from_rows(row, details)

    def _bill_from_rows(self, row, details) -> Bill:
        entered = _parse_utc(row["entry_time"]).astimezone(self.local_timezone)
        cutoff = _parse_utc(row["billing_cutoff_at"]).astimezone(self.local_timezone)
        rule = self._rule_from_record(row)
        minutes = int(row["duration_minutes"] or 0)
        capped = any(item["fee_before_cap_cents"] > item["charged_cents"] for item in details)
        lines = [
            ("停放时长", f"{minutes // 60} 小时 {minutes % 60} 分"),
            ("收费车型", row["vehicle_type"]),
        ]
        for item in details:
            lines.append(
                (
                    item["billing_date"],
                    f"{item['duration_minutes']} 分钟 · {_amount(item['charged_cents']):.2f} 元",
                )
            )
        if capped:
            lines.append(("日封顶", "已按同车当日累计封顶计收"))
        return Bill(
            record_id=int(row["record_id"]),
            plate=row["plate_no"],
            kind=row["plate_color"],
            enter_time=entered,
            exit_time=cutoff,
            minutes=minutes,
            free_minutes=rule.free_minutes,
            first_hours=rule.first_hours,
            first_price=rule.first_price,
            extra_price=rule.extra_price,
            day_cap=rule.day_cap,
            billable_minutes=sum(max(0, int(d["duration_minutes"]) - rule.free_minutes) for d in details),
            total=_amount(row["fee_cents"]),
            capped=capped,
            payment_status=row["payment_status"],
            release_status=row["release_status"],
            entry_photo=row["entry_photo"],
            exit_photo=row["exit_photo"],
            lines=lines,
        )

    def pay(self, record_id: int, *, at: datetime | None = None) -> Bill:
        current = self._now(at)
        with self.database.transaction() as connection:
            self._require_actor(connection)
            records = RecordRepository(connection)
            row = records.get(record_id)
            if row is None:
                raise ParkingError("停车记录不存在")
            if row["payment_status"] == "paid":
                pass
            elif row["payment_status"] == "authorized":
                raise ParkingError("该账单已授权放行，不能重复缴费")
            elif row["payment_status"] != "unpaid":
                raise ParkingError("请先生成账单再缴费")
            else:
                records.mark_paid(record_id, current)
                AuditRepository(connection).insert(
                    "parking.payment",
                    admin_id=self.actor.admin_id,
                    target=f"record:{record_id}",
                    after_value=json.dumps({"paid_cents": int(row["fee_cents"] or 0)}),
                )
            row = records.get(record_id)
            details = records.daily_details(record_id)
        assert row is not None
        return self._bill_from_rows(row, details)

    def release(self, record_id: int, *, at: datetime | None = None) -> Bill:
        current = self._now(at)
        with self.database.transaction() as connection:
            self._require_actor(connection)
            records = RecordRepository(connection)
            row = records.get(record_id)
            if row is None:
                raise ParkingError("停车记录不存在")
            if row["release_status"] == "not_released":
                if row["payment_status"] == "unpaid" and int(row["fee_cents"] or 0) == 0:
                    records.mark_paid(record_id, current)
                    row = records.get(record_id)
                if row["payment_status"] != "paid":
                    raise ParkingError("未缴费车辆禁止放行")
                release_type = "free" if int(row["fee_cents"] or 0) == 0 else "auto"
                records.mark_released(
                    record_id,
                    release_type=release_type,
                    released_at=current,
                )
                AuditRepository(connection).insert(
                    "parking.release",
                    admin_id=self.actor.admin_id,
                    target=f"record:{record_id}",
                    after_value=json.dumps({"type": release_type}),
                )
            row = records.get(record_id)
            details = records.daily_details(record_id)
        assert row is not None
        return self._bill_from_rows(row, details)

    def authorize_release(
        self,
        record_id: int,
        reason: str,
        admin: UserSession,
        *,
        at: datetime | None = None,
    ) -> Bill:
        reason = reason.strip()
        if not 2 <= len(reason) <= 200:
            raise ParkingError("授权放行原因须为 2～200 个字符")
        current = self._now(at)
        with self.database.transaction() as connection:
            require_admin(admin, connection)
            records = RecordRepository(connection)
            row = records.get(record_id)
            if row is None:
                raise ParkingError("停车记录不存在")
            if row["payment_status"] == "unbilled":
                raise ParkingError("请先生成账单再授权放行")
            if row["release_status"] == "not_released":
                if row["payment_status"] == "paid":
                    raise ParkingError("该账单已缴费，请使用正常放行")
                if row["payment_status"] != "unpaid":
                    raise ParkingError("当前账单状态不能授权放行")
                records.mark_released(
                    record_id,
                    release_type="authorized",
                    released_at=current,
                    released_by=admin.admin_id,
                    reason=reason,
                    authorized=True,
                )
                AuditRepository(connection).insert(
                    "parking.release.authorized",
                    admin_id=admin.admin_id,
                    target=f"record:{record_id}",
                    after_value=json.dumps({"reason": reason}, ensure_ascii=False),
                )
            row = records.get(record_id)
            details = records.daily_details(record_id)
        assert row is not None
        return self._bill_from_rows(row, details)

    def mark_vehicle_passed(self, record_id: int) -> None:
        with self.database.transaction() as connection:
            self._require_actor(connection)
            records = RecordRepository(connection)
            row = records.get(record_id)
            if row is None:
                raise ParkingError("停车记录不存在")
            if row["release_status"] == "passed":
                return
            if not records.mark_passed(record_id):
                raise ParkingError("车辆尚未获得放行，不能确认通过")
            AuditRepository(connection).insert(
                "parking.vehicle_passed",
                admin_id=self.actor.admin_id,
                target=f"record:{record_id}",
            )

    def complete_exit(self, record_id: int, *, at: datetime | None = None) -> None:
        current = self._now(at)
        with self.database.transaction() as connection:
            self._require_actor(connection)
            records = RecordRepository(connection)
            row = records.get(record_id)
            if row is None:
                raise ParkingError("停车记录不存在")
            if row["exit_time"] is not None:
                return
            if not records.complete_exit(record_id, current):
                raise ParkingError("请先确认车辆已通过并完成落杆")
            AuditRepository(connection).insert(
                "parking.exit.complete",
                admin_id=self.actor.admin_id,
                target=f"record:{record_id}",
            )
