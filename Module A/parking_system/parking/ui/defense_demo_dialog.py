"""本地答辩模式的需求追踪与现场操作指引。"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from parking.defense_demo import DEMO_GUIDE_ROWS, DEMO_PASSWORD, DEMO_USERNAME

from . import theme as T


class DefenseDemoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("演示指引")
        self.resize(980, 610)
        self.setModal(False)

        layout = QVBoxLayout(self)
        title = QLabel("演示指引")
        title.setStyleSheet(f"color:{T.TEXT}; font-size:20px; font-weight:700;")
        layout.addWidget(title)

        intro = QLabel(
            f"独立演示库已重置；登录账号：{DEMO_USERNAME}，密码：{DEMO_PASSWORD}。"
            "真实图片/视频识别仍由 HyperLPR3 完成，人工输入仅用于异常补救或指定测试场景。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{T.TEXT_SUB}; background:{T.PANEL_HI}; border:1px solid {T.LINE}; padding:9px;")
        layout.addWidget(intro)

        table = QTableWidget(len(DEMO_GUIDE_ROWS), 3)
        table.setHorizontalHeaderLabels(["需求 / 用例", "现场操作", "可观察结果"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setWordWrap(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 265)
        for row, values in enumerate(DEMO_GUIDE_ROWS):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setItem(row, column, item)
            table.setRowHeight(row, 44)
        layout.addWidget(table, 1)

        note = QLabel("提示：每个抬杆步骤均需点击“车辆已通过 · 落杆”完成状态闭环，再开始下一辆车。")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{T.MUTED};")
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
