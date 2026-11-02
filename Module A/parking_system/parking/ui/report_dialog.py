"""管理员统计查询与 PDF 导出窗口。"""

from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path

from PyQt5.QtCore import QDate, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from parking.report_pdf import ReportExportError, export_report_pdf
from parking.services.report_service import DIMENSION_LABELS
from . import theme as T


class ReportDialog(QDialog):
    def __init__(self, service, actor, parent=None):
        super().__init__(parent)
        self.service = service
        self.actor = actor
        self.result = None
        self.last_pdf: Path | None = None
        self.setWindowTitle("停车统计与 PDF 报表")
        self.resize(1080, 660)
        self.setMinimumSize(900, 560)
        self._build()
        self._query()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("停车统计与 PDF 报表")
        title.setStyleSheet(f"color:{T.TEXT}; font-size:20px; font-weight:700;")
        layout.addWidget(title)

        controls = QHBoxLayout()
        today = datetime.now(self.service.local_timezone).date()
        self.start_date = QDateEdit(QDate(today.year, today.month, today.day).addDays(-30))
        self.end_date = QDateEdit(QDate(today.year, today.month, today.day).addDays(1))
        for editor in (self.start_date, self.end_date):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("yyyy-MM-dd")
        self.dimension = QComboBox()
        for key, label in DIMENSION_LABELS.items():
            self.dimension.addItem(label, key)
        self.dimension.setCurrentIndex(self.dimension.findData("day"))
        self.btn_query = QPushButton("查询")
        self.btn_query.setObjectName("primary")
        self.btn_export = QPushButton("导出 PDF")
        self.btn_export.setObjectName("ghost")
        self.btn_open = QPushButton("打开 PDF")
        self.btn_open.setObjectName("ghost")
        self.btn_print = QPushButton("打印 PDF")
        self.btn_print.setObjectName("ghost")
        controls.addWidget(QLabel("起始（含）"))
        controls.addWidget(self.start_date)
        controls.addWidget(QLabel("结束（不含）"))
        controls.addWidget(self.end_date)
        controls.addWidget(QLabel("维度"))
        controls.addWidget(self.dimension)
        controls.addWidget(self.btn_query)
        controls.addStretch(1)
        controls.addWidget(self.btn_export)
        controls.addWidget(self.btn_open)
        controls.addWidget(self.btn_print)
        layout.addLayout(controls)

        self.summary = QLabel("—")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            f"color:{T.TEXT_SUB}; background:{T.PANEL_HI}; border:1px solid {T.LINE};"
            "padding:10px 12px; border-radius:6px;"
        )
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["统计周期", "车次", "应收（元）", "实收（元）", "授权车次", "授权未收（元）"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.hint = QLabel("正式统计仅包含已离场记录，并按进场时间归属所选区间。")
        self.hint.setStyleSheet(f"color:{T.MUTED};")
        layout.addWidget(self.hint)

        self.btn_query.clicked.connect(self._query)
        self.btn_export.clicked.connect(self._export)
        self.btn_open.clicked.connect(self._open)
        self.btn_print.clicked.connect(self._print)
        self._update_file_actions()

    def _range(self):
        start_day = self.start_date.date().toPyDate()
        end_day = self.end_date.date().toPyDate()
        tz = self.service.local_timezone
        return (
            datetime.combine(start_day, time.min, tzinfo=tz),
            datetime.combine(end_day, time.min, tzinfo=tz),
        )

    def _query(self) -> bool:
        start, end = self._range()
        try:
            self.result = self.service.query(
                self.actor, start, end, self.dimension.currentData()
            )
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "查询失败", str(exc))
            return False

        result = self.result
        self.summary.setText(
            f"车次 {result.vehicle_count}　应收 {result.receivable:.2f} 元　"
            f"实收 {result.received:.2f} 元　授权放行 {result.authorized_count} 车次　"
            f"授权未收 {result.authorized_uncollected:.2f} 元"
        )
        self.table.setRowCount(len(result.periods))
        for row, item in enumerate(result.periods):
            values = (
                item.label,
                str(item.vehicle_count),
                f"{item.receivable:.2f}",
                f"{item.received:.2f}",
                str(item.authorized_count),
                f"{item.authorized_uncollected:.2f}",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.hint.setText(
            "该区间没有已离场记录。" if not result.details else f"明细共 {len(result.details)} 条；PDF 将包含完整明细。"
        )
        return True

    def _export(self) -> None:
        if not self._query() or self.result is None:
            return
        start, end = self._range()
        suggested = (
            Path.home()
            / f"停车统计_{start:%Y%m%d}_{end:%Y%m%d}_{self.dimension.currentData()}.pdf"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出停车统计 PDF", str(suggested), "PDF 文件 (*.pdf)"
        )
        if not filename:
            return
        try:
            self.last_pdf = export_report_pdf(self.result, filename)
        except (OSError, ReportExportError) as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self._update_file_actions()
        QMessageBox.information(self, "导出成功", f"PDF 已保存：\n{self.last_pdf}")

    def _update_file_actions(self) -> None:
        available = self.last_pdf is not None and self.last_pdf.is_file()
        self.btn_open.setEnabled(available)
        self.btn_print.setEnabled(available)

    def _open(self) -> None:
        if self.last_pdf is None or not self.last_pdf.is_file():
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_pdf))):
            QMessageBox.warning(self, "打开失败", "无法调用系统 PDF 阅读器")

    def _print(self) -> None:
        if self.last_pdf is None or not self.last_pdf.is_file():
            return
        try:
            if os.name != "nt":
                raise OSError("当前系统不支持调用默认 PDF 打印命令")
            os.startfile(str(self.last_pdf), "print")
        except OSError as exc:
            QMessageBox.warning(self, "打印失败", str(exc))
