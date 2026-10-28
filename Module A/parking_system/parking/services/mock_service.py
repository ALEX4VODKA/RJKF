# -*- coding: utf-8 -*-
"""界面联调用的假服务。

组长把真实的 EntryService / ExitService 接进来时，只要实现同样的四个方法，
界面代码一行都不用改：
    present_vehicles() -> list[VehicleRow]
    stats()            -> dict
    recognize()        -> (plate, confidence, kind)
    bill(plate)        -> Bill
"""
import random
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from parking.models import Bill, VehicleRow


PLATES = [
    ("陕A·8K3M9", "blue"), ("陕A·6T2F7", "blue"), ("陕A·D9527", "green"),
    ("陕A·3W8Q1", "blue"), ("陕A·F2066", "yellow"), ("陕A·9C4L2", "blue"),
    ("陕A·1B7N5", "blue"), ("陕A·5H0R8", "green"),
]


class MockService:
    """演示用数据源，时间按当前时刻生成，保证「已停时长」一直在走。"""

    FREE_MINUTES = 15
    FIRST_HOURS = 2
    FIRST_PRICE = Decimal("5.00")
    EXTRA_PRICE = Decimal("3.00")
    DAY_CAP = Decimal("30.00")

    def __init__(self):
        now = datetime.now()
        self._rows = [
            VehicleRow(1, "陕A·8K3M9", "blue", now - timedelta(minutes=42)),
            VehicleRow(2, "陕A·6T2F7", "blue", now - timedelta(hours=1, minutes=18)),
            VehicleRow(3, "陕A·D9527", "green", now - timedelta(hours=2, minutes=5)),
            VehicleRow(4, "陕A·3W8Q1", "blue", now - timedelta(hours=3, minutes=27)),
            VehicleRow(5, "陕A·F2066", "yellow", now - timedelta(hours=4, minutes=12)),
            VehicleRow(6, "陕A·9C4L2", "blue", now - timedelta(hours=5, minutes=48)),
            VehicleRow(7, "陕A·1B7N5", "blue", now - timedelta(hours=7, minutes=3)),
            VehicleRow(8, "陕A·5H0R8", "green", now - timedelta(hours=11, minutes=36)),
        ]
        self._cursor = 0
        self._today_count = 86
        self._today_income = Decimal("1284.00")
        self._capacity = 50

    # ------------------------------------------------------------------
    def present_vehicles(self):
        return list(self._rows)

    def stats(self):
        present = len(self._rows)
        return {
            "present": present,
            "today_count": self._today_count,
            "today_income": self._today_income,
            "free_spaces": max(0, self._capacity - present),
            "capacity": self._capacity,
        }

    def recognize(self):
        """模拟一次识别：轮换车牌并跳过已在场的，返回 (车牌, 置信度, 牌色)。"""
        used = {r.plate for r in self._rows}
        for _ in range(len(PLATES)):
            plate, kind = PLATES[self._cursor % len(PLATES)]
            self._cursor += 1
            if plate not in used:
                return plate, round(random.uniform(0.86, 0.98), 3), kind
        plate = f"陕A·{random.randint(1000, 9999)}"
        return plate, round(random.uniform(0.86, 0.98), 3), "blue"

    # ------------------------------------------------------------------
    def _calc(self, minutes: int):
        """与需求文档 1.3.3 一致的计费实现（演示版）。"""
        if minutes <= self.FREE_MINUTES:
            return Decimal("0.00"), 0, False, minutes
        billable = minutes - self.FREE_MINUTES
        first_limit = self.FIRST_HOURS * 60
        if billable <= first_limit:
            fee = self.FIRST_PRICE
            extra_hours = 0
        else:
            over = billable - first_limit
            extra_hours = -(-over // 60)            # 向上取整
            fee = self.FIRST_PRICE + self.EXTRA_PRICE * extra_hours
        capped = fee > self.DAY_CAP
        fee = min(fee, self.DAY_CAP)
        return fee.quantize(Decimal("0.01"), ROUND_HALF_UP), extra_hours, capped, billable

    def bill(self, plate: str) -> Bill:
        row = next((r for r in self._rows if r.plate == plate), None)
        now = datetime.now()
        enter = row.enter_time if row else now - timedelta(hours=1, minutes=40)
        kind = row.kind if row else "blue"
        minutes = int((now - enter).total_seconds() // 60)
        total, extra_hours, capped, billable = self._calc(minutes)
        bill = Bill(
            record_id=row.record_id if row else 0,
            plate=plate, kind=kind, enter_time=enter, exit_time=now, minutes=minutes,
            free_minutes=self.FREE_MINUTES, first_hours=self.FIRST_HOURS,
            first_price=self.FIRST_PRICE, extra_price=self.EXTRA_PRICE,
            day_cap=self.DAY_CAP, billable_minutes=billable,
            extra_hours=extra_hours, total=total, capped=capped,
        )
        bill.lines = self._lines(bill)
        return bill

    @staticmethod
    def _lines(bill: Bill):
        used = min(bill.minutes, bill.free_minutes)
        lines = [
            ("停放时长", f"{bill.minutes // 60} 小时 {bill.minutes % 60} 分"),
            ("免费时长抵扣", f"{used} 分钟"),
            ("计费时长", f"{bill.billable_minutes} 分钟"),
            ("首时段", f"{bill.first_hours} 小时 · {bill.first_price} 元"),
        ]
        if bill.extra_hours:
            lines.append(("超时", f"{bill.extra_hours} 小时 × {bill.extra_price} 元"))
        if bill.capped:
            lines.append(("日封顶", f"已按封顶 {bill.day_cap} 元计收"))
        return lines

    # ------------------------------------------------------------------
    def add_entry(self, plate: str, kind: str = "blue"):
        """入口抬杆后调用：新增一条在场记录。"""
        if any(r.plate == plate for r in self._rows):
            return
        next_id = max((row.record_id for row in self._rows), default=0) + 1
        self._rows.insert(0, VehicleRow(next_id, plate, kind, datetime.now()))
        self._today_count += 1

    def exit_vehicle(self, plate: str):
        """出口抬杆后调用：车辆离场，从在场列表移除。"""
        self._rows = [r for r in self._rows if r.plate != plate]

    def pay(self, plate: str, amount=None):
        """记账，不移除在场记录——车辆要等出口抬杆后才离场。"""
        if amount is None:
            amount = self.bill(plate).total
        self._today_income += amount
