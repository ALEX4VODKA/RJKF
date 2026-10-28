"""管理员停车历史查询。"""

from decimal import Decimal

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


PAYMENT_TEXT = {
    "unbilled": "未结算",
    "unpaid": "待缴费",
    "paid": "已缴费",
    "authorized": "授权放行",
}
RELEASE_TEXT = {
    "not_released": "未放行",
    "released": "等待通过",
    "passed": "等待落杆",
}


class ParkingHistoryDialog(QDialog):
    def __init__(self, service, actor, parent=None):
        super().__init__(parent)
        self.setWindowTitle("停车历史记录")
        self.resize(1080, 620)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["记录", "车牌", "车型", "进场时间", "计费截止", "应收", "缴费", "放行", "离场时间"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.table)

        rows = service.list_history(actor)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            fee = Decimal(row["fee_cents"] or 0) / 100
            values = (
                str(row["record_id"]),
                row["plate_no"],
                row["vehicle_type"],
                self._time(row["entry_time"]),
                self._time(row["billing_cutoff_at"]),
                f"{fee:.2f}",
                PAYMENT_TEXT.get(row["payment_status"], row["payment_status"]),
                RELEASE_TEXT.get(row["release_status"], row["release_status"]),
                self._time(row["exit_time"]),
            )
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(value))

    @staticmethod
    def _time(value: str | None) -> str:
        return value.replace("T", " ").replace("Z", "") if value else "—"
