from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from parking.billing import FeeRuleSnapshot, calculate_fee


TZ = timezone(timedelta(hours=8))
RULE = FeeRuleSnapshot(
    rule_id=1,
    version=1,
    vehicle_type="小型车",
    free_minutes=15,
    first_hours=2,
    first_price=Decimal("5.00"),
    extra_price=Decimal("3.00"),
    day_cap=Decimal("30.00"),
)


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (10, "0.00"),
        (100, "5.00"),
        (200, "11.00"),
        (480, "23.00"),
        (720, "30.00"),
    ],
)
def test_same_day_billing_baselines(minutes, expected):
    started = datetime(2026, 10, 28, 8, 0, tzinfo=TZ)
    result = calculate_fee(started, started + timedelta(minutes=minutes), RULE)
    assert result.total == Decimal(expected)
    assert len(result.daily) == 1


def test_cross_day_baseline_is_capped_per_natural_day():
    started = datetime(2026, 10, 28, 10, 0, tzinfo=TZ)
    ended = datetime(2026, 10, 29, 12, 0, tzinfo=TZ)
    result = calculate_fee(started, ended, RULE)

    assert result.total == Decimal("60.00")
    assert [item.duration_minutes for item in result.daily] == [840, 720]
    assert [item.charged for item in result.daily] == [
        Decimal("30.00"),
        Decimal("30.00"),
    ]


def test_extra_time_rounds_up_but_elapsed_seconds_round_down():
    started = datetime(2026, 10, 28, 8, 0, 30, tzinfo=TZ)
    ended = started + timedelta(minutes=135, seconds=59)
    result = calculate_fee(started, ended, RULE)
    assert result.duration_minutes == 135
    assert result.daily[0].extra_hours == 0
    assert result.total == Decimal("5.00")


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(15, "0.00"), (16, "5.00"), (135, "5.00"), (136, "8.00")],
)
def test_free_and_first_period_boundaries(minutes, expected):
    started = datetime(2026, 10, 28, 8, 0, tzinfo=TZ)
    result = calculate_fee(started, started + timedelta(minutes=minutes), RULE)
    assert result.total == Decimal(expected)


def test_midnight_and_year_boundary_split_into_separate_days():
    started = datetime(2026, 12, 31, 23, 50, tzinfo=TZ)
    ended = datetime(2027, 1, 1, 0, 20, tzinfo=TZ)
    result = calculate_fee(started, ended, RULE)
    assert [item.billing_date for item in result.daily] == [
        date(2026, 12, 31),
        date(2027, 1, 1),
    ]
    assert [item.charged for item in result.daily] == [
        Decimal("0.00"),
        Decimal("5.00"),
    ]
    assert result.total == Decimal("5.00")


def test_existing_daily_due_uses_only_remaining_cap():
    started = datetime(2026, 10, 28, 8, 0, tzinfo=TZ)
    result = calculate_fee(
        started,
        started + timedelta(hours=12),
        RULE,
        prior_daily_due={date(2026, 10, 28): Decimal("25.00")},
    )
    assert result.total == Decimal("5.00")
    assert result.daily[0].prior_daily_due == Decimal("25.00")
    assert result.resulting_daily_due[date(2026, 10, 28)] == Decimal("30.00")


def test_existing_day_can_use_its_first_period_cap():
    started = datetime(2026, 10, 28, 8, 0, tzinfo=TZ)
    result = calculate_fee(
        started,
        started + timedelta(hours=12),
        RULE,
        prior_daily_due={date(2026, 10, 28): Decimal("30.00")},
        daily_cap_limits={date(2026, 10, 28): Decimal("40.00")},
    )
    assert result.total == Decimal("10.00")


@pytest.mark.parametrize(
    ("started", "ended"),
    [
        (datetime(2026, 10, 28, 8, 0), datetime(2026, 10, 28, 9, 0)),
        (
            datetime(2026, 10, 28, 8, 0, tzinfo=TZ),
            datetime(2026, 10, 28, 8, 0, tzinfo=TZ),
        ),
    ],
)
def test_invalid_time_range_is_rejected(started, ended):
    with pytest.raises(ValueError):
        calculate_fee(started, ended, RULE)
