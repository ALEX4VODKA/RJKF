"""停车计费纯函数。

计费不访问数据库。调用方负责提供进出场时间、进场时锁定的规则快照，
以及同车在各自然日已经占用的封顶额度。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from typing import Mapping


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str) -> Decimal:
    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError("金额必须是有限数值")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeeRuleSnapshot:
    vehicle_type: str
    free_minutes: int
    first_hours: int
    first_price: Decimal
    extra_price: Decimal
    day_cap: Decimal
    rule_id: int | None = None
    version: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "first_price", money(self.first_price))
        object.__setattr__(self, "extra_price", money(self.extra_price))
        object.__setattr__(self, "day_cap", money(self.day_cap))
        if not 0 <= self.free_minutes <= 120:
            raise ValueError("免费时长必须为 0～120 分钟")
        if not 1 <= self.first_hours <= 24:
            raise ValueError("首时段必须为 1～24 小时")
        if self.first_price <= ZERO or self.extra_price <= ZERO:
            raise ValueError("首时段价格和超时单价必须大于 0")
        if self.day_cap < self.first_price:
            raise ValueError("日封顶金额不能低于首时段价格")


@dataclass(frozen=True)
class DailyCharge:
    billing_date: date
    period_start: datetime
    period_end: datetime
    duration_minutes: int
    free_minutes_used: int
    billable_minutes: int
    extra_hours: int
    fee_before_cap: Decimal
    prior_daily_due: Decimal
    day_cap: Decimal
    charged: Decimal
    capped: bool


@dataclass(frozen=True)
class BillingResult:
    started_at: datetime
    ended_at: datetime
    duration_minutes: int
    total: Decimal
    daily: tuple[DailyCharge, ...]
    resulting_daily_due: Mapping[date, Decimal]


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label}必须包含时区信息")


def _segment_fee(minutes: int, rule: FeeRuleSnapshot) -> tuple[Decimal, int, int, int]:
    free_used = min(minutes, rule.free_minutes)
    if minutes <= rule.free_minutes:
        return ZERO, free_used, 0, 0

    billable = minutes - rule.free_minutes
    first_limit = rule.first_hours * 60
    if billable <= first_limit:
        return rule.first_price, free_used, billable, 0

    over_minutes = billable - first_limit
    extra_hours = (over_minutes + 59) // 60
    fee = money(rule.first_price + rule.extra_price * extra_hours)
    return fee, free_used, billable, extra_hours


def calculate_fee(
    started_at: datetime,
    ended_at: datetime,
    rule: FeeRuleSnapshot,
    *,
    prior_daily_due: Mapping[date, Decimal] | None = None,
    daily_cap_limits: Mapping[date, Decimal] | None = None,
) -> BillingResult:
    """按自然日计算费用并应用同车每日累计封顶。

    自然日使用进场时间所在时区。每个分段的秒数向下取整为整分钟；
    超出首时段的不足一小时部分向上计为一小时。
    """

    _require_aware(started_at, "进场时间")
    _require_aware(ended_at, "计费截止时间")
    local_end = ended_at.astimezone(started_at.tzinfo)
    if local_end <= started_at:
        raise ValueError("计费截止时间必须晚于进场时间")

    accumulated = {
        day: money(amount) for day, amount in (prior_daily_due or {}).items()
    }
    caps = {day: money(amount) for day, amount in (daily_cap_limits or {}).items()}
    details: list[DailyCharge] = []
    cursor = started_at

    while cursor < local_end:
        next_midnight = datetime.combine(
            cursor.date() + timedelta(days=1), time.min, tzinfo=cursor.tzinfo
        )
        segment_end = min(local_end, next_midnight)
        minutes = int((segment_end - cursor).total_seconds() // 60)
        fee_before_cap, free_used, billable, extra_hours = _segment_fee(minutes, rule)

        day = cursor.date()
        prior = accumulated.get(day, ZERO)
        cap = caps.get(day, rule.day_cap)
        remaining = max(ZERO, money(cap - prior))
        charged = money(min(fee_before_cap, remaining))
        accumulated[day] = money(prior + charged)
        details.append(
            DailyCharge(
                billing_date=day,
                period_start=cursor,
                period_end=segment_end,
                duration_minutes=minutes,
                free_minutes_used=free_used,
                billable_minutes=billable,
                extra_hours=extra_hours,
                fee_before_cap=fee_before_cap,
                prior_daily_due=prior,
                day_cap=cap,
                charged=charged,
                capped=fee_before_cap > charged,
            )
        )
        cursor = segment_end

    total = money(sum((item.charged for item in details), ZERO))
    return BillingResult(
        started_at=started_at,
        ended_at=local_end,
        duration_minutes=sum(item.duration_minutes for item in details),
        total=total,
        daily=tuple(details),
        resulting_daily_due=MappingProxyType(dict(accumulated)),
    )
