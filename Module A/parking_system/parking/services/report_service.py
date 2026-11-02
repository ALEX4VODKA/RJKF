"""管理员停车统计查询。

正式报表仅统计已经完成离场的停车记录，并按进场时间归属统计区间。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from parking.data import Database
from parking.services.admin_service import UserSession, require_admin


DIMENSION_LABELS = {
    "day": "日",
    "week": "ISO 周",
    "month": "月",
    "quarter": "季度",
    "year": "年",
}


def _money(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("统计时间必须包含时区信息")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ReportPeriod:
    key: str
    label: str
    start: datetime
    end: datetime
    vehicle_count: int
    receivable_cents: int
    received_cents: int
    authorized_count: int
    authorized_uncollected_cents: int

    @property
    def receivable(self) -> Decimal:
        return _money(self.receivable_cents)

    @property
    def received(self) -> Decimal:
        return _money(self.received_cents)

    @property
    def authorized_uncollected(self) -> Decimal:
        return _money(self.authorized_uncollected_cents)


@dataclass(frozen=True)
class ReportDetail:
    record_id: int
    plate_no: str
    vehicle_type: str
    entry_time: datetime
    exit_time: datetime
    fee_cents: int
    paid_cents: int
    payment_status: str
    release_type: str

    @property
    def fee(self) -> Decimal:
        return _money(self.fee_cents)

    @property
    def paid(self) -> Decimal:
        return _money(self.paid_cents)


@dataclass(frozen=True)
class ReportResult:
    dimension: str
    start: datetime
    end: datetime
    periods: tuple[ReportPeriod, ...]
    details: tuple[ReportDetail, ...]

    @property
    def dimension_label(self) -> str:
        return DIMENSION_LABELS[self.dimension]

    @property
    def vehicle_count(self) -> int:
        return sum(item.vehicle_count for item in self.periods)

    @property
    def receivable_cents(self) -> int:
        return sum(item.receivable_cents for item in self.periods)

    @property
    def received_cents(self) -> int:
        return sum(item.received_cents for item in self.periods)

    @property
    def authorized_count(self) -> int:
        return sum(item.authorized_count for item in self.periods)

    @property
    def authorized_uncollected_cents(self) -> int:
        return sum(item.authorized_uncollected_cents for item in self.periods)

    @property
    def receivable(self) -> Decimal:
        return _money(self.receivable_cents)

    @property
    def received(self) -> Decimal:
        return _money(self.received_cents)

    @property
    def authorized_uncollected(self) -> Decimal:
        return _money(self.authorized_uncollected_cents)


@dataclass
class _PeriodAccumulator:
    key: str
    label: str
    start: datetime
    end: datetime
    vehicle_count: int = 0
    receivable_cents: int = 0
    received_cents: int = 0
    authorized_count: int = 0
    authorized_uncollected_cents: int = 0

    def add(self, fee_cents: int, paid_cents: int, authorized: bool) -> None:
        self.vehicle_count += 1
        self.receivable_cents += fee_cents
        self.received_cents += paid_cents
        if authorized:
            self.authorized_count += 1
            self.authorized_uncollected_cents += fee_cents

    def freeze(self) -> ReportPeriod:
        return ReportPeriod(
            key=self.key,
            label=self.label,
            start=self.start,
            end=self.end,
            vehicle_count=self.vehicle_count,
            receivable_cents=self.receivable_cents,
            received_cents=self.received_cents,
            authorized_count=self.authorized_count,
            authorized_uncollected_cents=self.authorized_uncollected_cents,
        )


class ReportService:
    def __init__(self, database: Database, *, local_timezone=None):
        self.database = database
        self.local_timezone = local_timezone or datetime.now().astimezone().tzinfo

    def query(
        self,
        actor: UserSession,
        start: datetime,
        end: datetime,
        dimension: str,
    ) -> ReportResult:
        if dimension not in DIMENSION_LABELS:
            raise ValueError("统计维度无效")
        start_text = _utc_text(start)
        end_text = _utc_text(end)
        if end <= start:
            raise ValueError("统计结束时间必须晚于开始时间")

        with self.database.connect() as connection:
            require_admin(actor, connection)
            rows = connection.execute(
                """
                SELECT record_id, plate_no, vehicle_type, entry_time, exit_time,
                       COALESCE(fee_cents, 0) AS fee_cents,
                       paid_cents, payment_status, COALESCE(release_type, '') AS release_type
                FROM parking_record
                WHERE exit_time IS NOT NULL
                  AND entry_time >= ? AND entry_time < ?
                ORDER BY entry_time, record_id
                """,
                (start_text, end_text),
            ).fetchall()

        periods: dict[str, _PeriodAccumulator] = {}
        details: list[ReportDetail] = []
        for row in rows:
            entry_time = _parse_utc(row["entry_time"]).astimezone(self.local_timezone)
            exit_time = _parse_utc(row["exit_time"]).astimezone(self.local_timezone)
            key, label, period_start, period_end = self._period_for(entry_time, dimension)
            accumulator = periods.setdefault(
                key,
                _PeriodAccumulator(key, label, period_start, period_end),
            )
            fee_cents = int(row["fee_cents"])
            paid_cents = int(row["paid_cents"])
            authorized = row["payment_status"] == "authorized"
            accumulator.add(fee_cents, paid_cents, authorized)
            details.append(
                ReportDetail(
                    record_id=int(row["record_id"]),
                    plate_no=row["plate_no"],
                    vehicle_type=row["vehicle_type"],
                    entry_time=entry_time,
                    exit_time=exit_time,
                    fee_cents=fee_cents,
                    paid_cents=paid_cents,
                    payment_status=row["payment_status"],
                    release_type=row["release_type"],
                )
            )

        result_periods = tuple(
            item.freeze() for item in sorted(periods.values(), key=lambda item: item.start)
        )
        return ReportResult(
            dimension=dimension,
            start=start,
            end=end,
            periods=result_periods,
            details=tuple(details),
        )

    def _period_for(
        self, value: datetime, dimension: str
    ) -> tuple[str, str, datetime, datetime]:
        tz = self.local_timezone
        day_start = datetime.combine(value.date(), datetime.min.time(), tzinfo=tz)
        if dimension == "day":
            return value.strftime("%Y-%m-%d"), value.strftime("%Y-%m-%d"), day_start, day_start + timedelta(days=1)
        if dimension == "week":
            iso_year, iso_week, _ = value.isocalendar()
            period_start = day_start - timedelta(days=value.weekday())
            key = f"{iso_year}-W{iso_week:02d}"
            return key, key, period_start, period_start + timedelta(days=7)
        if dimension == "month":
            period_start = datetime(value.year, value.month, 1, tzinfo=tz)
            if value.month == 12:
                period_end = datetime(value.year + 1, 1, 1, tzinfo=tz)
            else:
                period_end = datetime(value.year, value.month + 1, 1, tzinfo=tz)
            key = value.strftime("%Y-%m")
            return key, key, period_start, period_end
        if dimension == "quarter":
            quarter = (value.month - 1) // 3 + 1
            first_month = (quarter - 1) * 3 + 1
            period_start = datetime(value.year, first_month, 1, tzinfo=tz)
            if quarter == 4:
                period_end = datetime(value.year + 1, 1, 1, tzinfo=tz)
            else:
                period_end = datetime(value.year, first_month + 3, 1, tzinfo=tz)
            key = f"{value.year}-Q{quarter}"
            return key, key, period_start, period_end
        period_start = datetime(value.year, 1, 1, tzinfo=tz)
        period_end = datetime(value.year + 1, 1, 1, tzinfo=tz)
        key = str(value.year)
        return key, key, period_start, period_end
