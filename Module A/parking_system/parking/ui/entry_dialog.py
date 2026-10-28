"""Phase 2 人工进场登记窗口。"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from parking.services.parking_service import ParkingError, normalize_plate


COLOR_OPTIONS = (
    ("蓝牌", "blue"),
    ("绿牌", "green"),
    ("黄牌", "yellow"),
    ("白牌", "white"),
    ("黑牌", "black"),
    ("其他", "other"),
)


class EntryDialog(QDialog):
    def __init__(self, vehicle_types: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("人工进场登记")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        hint = QLabel("请核对车牌、收费车型和车牌颜色。登记成功后才会抬杆。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.plate_edit = QLineEdit()
        self.plate_edit.setPlaceholderText("例如：陕A12345")
        self.plate_edit.setMaxLength(16)
        form.addRow("车牌号", self.plate_edit)

        self.vehicle_type = QComboBox()
        self.vehicle_type.addItems(vehicle_types)
        form.addRow("收费车型", self.vehicle_type)

        self.plate_color = QComboBox()
        for label, value in COLOR_OPTIONS:
            self.plate_color.addItem(label, value)
        form.addRow("车牌颜色", self.plate_color)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("登记并抬杆")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.plate_edit.returnPressed.connect(self._accept)
        self.plate_edit.setFocus(Qt.OtherFocusReason)

    def _accept(self):
        if self.vehicle_type.count() == 0:
            QMessageBox.warning(self, "无法登记", "当前没有已生效的收费标准")
            return
        try:
            self.plate_edit.setText(normalize_plate(self.plate_edit.text()))
        except ParkingError as exc:
            QMessageBox.warning(self, "车牌格式错误", str(exc))
            return
        self.accept()

    @property
    def values(self) -> tuple[str, str, str]:
        return (
            self.plate_edit.text(),
            self.vehicle_type.currentText(),
            self.plate_color.currentData(),
        )
