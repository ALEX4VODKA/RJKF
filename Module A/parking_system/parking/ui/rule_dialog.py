"""收费标准管理界面。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from PyQt5.QtCore import QDateTime, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from parking.services.admin_service import UserSession
from parking.services.rule_service import FeeRuleVersion, RuleDraft, RuleService
from . import theme as T


class RuleEditDialog(QDialog):
    def __init__(self, rule: FeeRuleVersion | None = None, parent=None):
        super().__init__(parent)
        self.rule = rule
        self.setWindowTitle("新增收费标准" if rule is None else "版本化修改收费标准")
        self.setMinimumWidth(460)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        title = QLabel(self.windowTitle())
        title.setStyleSheet(f"color:{T.TEXT}; font-size:18px; font-weight:700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.vehicle_type = QLineEdit(self.rule.vehicle_type if self.rule else "")
        self.vehicle_type.setReadOnly(self.rule is not None)
        self.free_minutes = QSpinBox()
        self.free_minutes.setRange(0, 120)
        self.free_minutes.setValue(self.rule.free_minutes if self.rule else 15)
        self.first_hours = QSpinBox()
        self.first_hours.setRange(1, 24)
        self.first_hours.setValue(self.rule.first_hours if self.rule else 2)
        self.first_price = self._money_spin(self.rule.first_price if self.rule else Decimal("5.00"))
        self.extra_price = self._money_spin(self.rule.extra_price if self.rule else Decimal("3.00"))
        self.day_cap = self._money_spin(self.rule.day_cap if self.rule else Decimal("30.00"))
        self.effective_at = QDateTimeEdit()
        self.effective_at.setCalendarPopup(True)
        effective = datetime.now().astimezone()
        if self.rule is not None:
            effective = max(effective, self.rule.effective_at.astimezone())
        self.effective_at.setDateTime(QDateTime.fromPyDateTime(effective.replace(tzinfo=None)))
        self.effective_at.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        form.addRow("车型", self.vehicle_type)
        form.addRow("免费时长（分钟）", self.free_minutes)
        form.addRow("首时段（小时）", self.first_hours)
        form.addRow("首时段价格（元）", self.first_price)
        form.addRow("超时单价（元/小时）", self.extra_price)
        form.addRow("日封顶（元）", self.day_cap)
        form.addRow("生效时间", self.effective_at)
        layout.addLayout(form)

        hint = QLabel("修改会生成新版本；已经进场和历史记录继续使用原规则快照。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{T.MUTED};")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存")
        buttons.button(QDialogButtonBox.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Cancel).setObjectName("ghost")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _money_spin(value: Decimal) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setRange(0.01, 99999.99)
        spin.setValue(float(value))
        spin.setSuffix(" 元")
        return spin

    def draft(self) -> RuleDraft:
        effective = self.effective_at.dateTime().toPyDateTime()
        if effective.tzinfo is None:
            effective = effective.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return RuleDraft(
            vehicle_type=self.vehicle_type.text(),
            free_minutes=self.free_minutes.value(),
            first_hours=self.first_hours.value(),
            first_price=Decimal(str(self.first_price.value())),
            extra_price=Decimal(str(self.extra_price.value())),
            day_cap=Decimal(str(self.day_cap.value())),
            effective_at=effective,
        )


class RuleManagerDialog(QDialog):
    def __init__(
        self,
        service: RuleService,
        actor: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.service = service
        self.actor = actor
        self._rules: dict[int, FeeRuleVersion] = {}
        self.setWindowTitle("收费标准管理")
        self.resize(1080, 560)
        self.setMinimumSize(900, 480)
        self._build()
        self._reload()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("收费标准管理")
        title.setStyleSheet(f"color:{T.TEXT}; font-size:20px; font-weight:700;")
        head.addWidget(title)
        head.addStretch(1)
        self.btn_add = QPushButton("新增车型规则")
        self.btn_add.setObjectName("primary")
        self.btn_edit = QPushButton("版本化修改")
        self.btn_edit.setObjectName("ghost")
        self.btn_disable = QPushButton("停用车型规则")
        self.btn_disable.setObjectName("danger")
        head.addWidget(self.btn_add)
        head.addWidget(self.btn_edit)
        head.addWidget(self.btn_disable)
        layout.addLayout(head)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["车型", "版本", "免费分钟", "首时段", "首价", "超时价", "日封顶", "生效时间", "状态"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        hint = QLabel("停用会使该车型所有版本不再用于后续进场，但不会删除历史规则或停车记录。")
        hint.setStyleSheet(f"color:{T.MUTED};")
        layout.addWidget(hint)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText("关闭")
        close.button(QDialogButtonBox.Close).setObjectName("ghost")
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self.btn_add.clicked.connect(self._add)
        self.btn_edit.clicked.connect(self._edit)
        self.btn_disable.clicked.connect(self._deactivate)
        self.table.doubleClicked.connect(lambda _index: self._edit())

    def _reload(self) -> None:
        rules = self.service.list_rules(self.actor)
        self._rules = {rule.rule_id: rule for rule in rules}
        latest_versions = {}
        for rule in rules:
            latest_versions[rule.vehicle_type] = max(
                latest_versions.get(rule.vehicle_type, 0), rule.version
            )
        self.table.setRowCount(len(rules))
        for row_index, rule in enumerate(rules):
            if not rule.active:
                status = "停用"
            elif rule.version == latest_versions[rule.vehicle_type]:
                status = "启用·最新"
            else:
                status = "历史版本"
            values = [
                rule.vehicle_type,
                f"v{rule.version}",
                str(rule.free_minutes),
                f"{rule.first_hours} 小时",
                f"{rule.first_price:.2f}",
                f"{rule.extra_price:.2f}",
                f"{rule.day_cap:.2f}",
                rule.effective_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, rule.rule_id)
                self.table.setItem(row_index, column, item)
        if rules:
            self.table.selectRow(0)

    def _selected(self) -> FeeRuleVersion | None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条收费规则")
            return None
        rule_id = self.table.item(row, 0).data(Qt.UserRole)
        return self._rules.get(rule_id)

    def _add(self) -> None:
        dialog = RuleEditDialog(parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        try:
            self.service.create_rule(self.actor, dialog.draft())
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._reload()

    def _edit(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        dialog = RuleEditDialog(selected, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        try:
            self.service.update_rule(self.actor, selected.rule_id, dialog.draft())
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._reload()

    def _deactivate(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        answer = QMessageBox.question(
            self,
            "确认停用",
            f"确认停用“{selected.vehicle_type}”的全部收费规则版本？\n"
            "历史停车记录不会被删除。",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.deactivate_rule(self.actor, selected.rule_id)
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "停用失败", str(exc))
            return
        self._reload()
