"""界面与业务服务共享的数据对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class VehicleRow:
    record_id: int
    plate: str
    kind: str
    enter_time: datetime
    status: str = "在场"

    @property
    def duration_min(self) -> int:
        now = (
            datetime.now(self.enter_time.tzinfo)
            if self.enter_time.tzinfo is not None
            else datetime.now()
        )
        return max(0, int((now - self.enter_time).total_seconds() // 60))


@dataclass
class Bill:
    record_id: int
    plate: str
    kind: str
    enter_time: datetime
    exit_time: datetime
    minutes: int
    free_minutes: int
    first_hours: int
    first_price: Decimal
    extra_price: Decimal
    day_cap: Decimal
    billable_minutes: int = 0
    extra_hours: int = 0
    total: Decimal = Decimal("0.00")
    capped: bool = False
    payment_status: str = "unpaid"
    release_status: str = "not_released"
    entry_photo: str | None = None
    exit_photo: str | None = None
    lines: list[tuple[str, str]] = field(default_factory=list)
