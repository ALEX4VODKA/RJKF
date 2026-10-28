# -*- coding: utf-8 -*-
"""出场缴费界面：账单明细 + 进出场照片 + 缴费 / 放行。"""
from datetime import datetime

from PyQt5.QtCore import QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PyQt5.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from . import icons
from . import theme as T
from .widgets import Pill, PlateBadge, toast


class PhotoTile(QWidget):
    """16:9 的照片位：没有图片时显示占位，接入真实抓拍只需 set_image(path)。"""

    def __init__(self, title: str, stamp: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._stamp = stamp
        self._pix = None
        self.setMinimumSize(260, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, path: str):
        from PyQt5.QtGui import QPixmap
        pm = QPixmap(path)
        if not pm.isNull():
            self._pix = pm
            self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(T.LINE), 1))
        p.setBrush(QColor("#F5F8FC"))
        p.drawRoundedRect(r, 10, 10)

        if self._pix is not None:
            p.save()
            path = QRectF(r)
            p.setClipRect(path)
            scaled = self._pix.scaled(int(r.width()), int(r.height()),
                                      Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(int(r.left()), int(r.top()), scaled)
            p.restore()
            p.setPen(QPen(QColor(T.LINE), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 10, 10)
            return

        cx, cy = int(r.center().x()), int(r.center().y())
        icons.paint_icon(p, "camera", QRectF(cx - 13, cy - 26, 26, 26), QColor("#C3D3E3"))
        p.setPen(QColor(T.DIM))
        f = QFont(T.FONT_UI)
        f.setPixelSize(12)
        p.setFont(f)
        p.drawText(QRectF(r.left(), cy + 2, r.width(), 18), Qt.AlignHCenter, self._title + "占位")

        if self._stamp:
            p.setPen(QColor(T.DIM))
            f2 = QFont("Consolas")
            f2.setPixelSize(11)
            p.setFont(f2)
            p.drawText(QRectF(r.left(), cy + 24, r.width(), 16), Qt.AlignHCenter, self._stamp)
        p.end()


class ExitDialog(QDialog):
    """出场结算窗口。

    信号：
        paid()                              请求模拟缴费
        released(reason)                    请求正常/免费放行
        authorize_requested(user,pwd,reason) 请求管理员授权放行
    """

    paid = pyqtSignal()
    released = pyqtSignal(str)
    authorize_requested = pyqtSignal(str, str, str)

    def __init__(self, bill, parent=None):
        super().__init__(parent)
        self.bill = bill
        self._is_paid = bill.payment_status == "paid"
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._drag_pos = None
        self._build()
        self._sync_state()

    # ------------------------------------------------------------------ UI
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setObjectName("dialogCard")
        self.card.setStyleSheet(
            f"QFrame#dialogCard{{background:{T.PANEL}; border:1px solid {T.LINE};"
            f" border-radius:16px;}}"
        )
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ---------------- 标题栏
        head = QWidget()
        head.setFixedHeight(64)
        head.setStyleSheet(
            f"background:{T.PANEL_HI}; border-top-left-radius:16px; border-top-right-radius:16px;"
        )
        h = QHBoxLayout(head)
        h.setContentsMargins(22, 0, 14, 0)
        h.setSpacing(10)
        title = QLabel("出场结算")
        title.setStyleSheet(f"color:{T.TEXT}; font-size:16px; font-weight:700; letter-spacing:1px;")
        h.addWidget(title)
        self.pill = Pill("待缴费", "warn")
        h.addWidget(self.pill)
        h.addStretch(1)

        btn_close = QPushButton()
        btn_close.setObjectName("linkBtn")
        btn_close.setIcon(QIcon(icons.icon_pixmap("close", 14, T.MUTED)))
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        h.addWidget(btn_close)
        lay.addWidget(head)

        # ---------------- 主体
        body = QHBoxLayout()
        body.setContentsMargins(22, 18, 22, 8)
        body.setSpacing(18)

        # 左：照片
        left = QVBoxLayout()
        left.setSpacing(8)
        self.tile_in = PhotoTile("进场照片", self._fmt(self.bill.enter_time))
        self.tile_out = PhotoTile("出场照片", self._fmt(self.bill.exit_time))
        left.addWidget(self.tile_in, 1)
        left.addWidget(self.tile_out, 1)
        body.addLayout(left, 5)

        # 右：账单
        right = QVBoxLayout()
        right.setSpacing(12)

        plate_row = QHBoxLayout()
        plate_row.setSpacing(12)
        self.badge = PlateBadge(self.bill.plate, self.bill.kind, 54)
        plate_row.addWidget(self.badge)
        meta = QVBoxLayout()
        meta.setSpacing(2)
        lb = QLabel(f"进场 {self._fmt(self.bill.enter_time)}")
        lb.setStyleSheet(f"color:{T.MUTED}; font-size:12px;")
        lb2 = QLabel(f"出场 {self._fmt(self.bill.exit_time)}")
        lb2.setStyleSheet(f"color:{T.MUTED}; font-size:12px;")
        meta.addWidget(lb)
        meta.addWidget(lb2)
        plate_row.addLayout(meta)
        plate_row.addStretch(1)
        right.addLayout(plate_row)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{T.LINE_SOFT};")
        right.addWidget(line)

        cap2 = QLabel("计费明细")
        cap2.setStyleSheet(f"color:{T.MUTED}; font-size:11px; letter-spacing:1px;")
        right.addWidget(cap2)

        for name, value in self.bill.lines:
            row = QHBoxLayout()
            n = QLabel(name)
            n.setStyleSheet(f"color:{T.MUTED}; font-size:12px;")
            v = QLabel(str(value))
            v.setStyleSheet(f"color:{T.TEXT_SUB}; font-size:12px; font-family:'{T.FONT_NUM}';")
            row.addWidget(n)
            row.addStretch(1)
            row.addWidget(v)
            right.addLayout(row)

        right.addStretch(1)

        total_box = QFrame()
        total_box.setObjectName("cardFlat")
        tb = QVBoxLayout(total_box)
        tb.setContentsMargins(16, 12, 16, 12)
        tb.setSpacing(2)
        cap = QLabel("应收金额")
        cap.setStyleSheet(f"color:{T.MUTED}; font-size:11px; letter-spacing:1px;")
        tb.addWidget(cap)
        amt_row = QHBoxLayout()
        amt_row.setSpacing(4)
        self.amount = QLabel(f"{self.bill.total:.2f}")
        self.amount.setStyleSheet(
            f"color:{T.PRIMARY}; font-family:'{T.FONT_NUM}'; font-size:38px; font-weight:700;"
        )
        cur = QLabel("元")
        cur.setStyleSheet(f"color:{T.MUTED}; font-size:14px;")
        amt_row.addWidget(self.amount)
        amt_row.addWidget(cur, 0, Qt.AlignBottom)
        amt_row.addStretch(1)
        tb.addLayout(amt_row)
        right.addWidget(total_box)

        self.rule = QLabel(
            f"计费规则：免费 {self.bill.free_minutes} 分钟 · 首 {self.bill.first_hours} 小时 "
            f"{self.bill.first_price} 元 · 超时 {self.bill.extra_price} 元/小时 · 封顶 {self.bill.day_cap} 元"
        )
        self.rule.setStyleSheet(f"color:{T.DIM}; font-size:11px;")
        self.rule.setWordWrap(True)
        right.addWidget(self.rule)

        body.addLayout(right, 6)
        lay.addLayout(body, 1)

        # ---------------- 底部按钮
        foot = QHBoxLayout()
        foot.setContentsMargins(22, 8, 22, 18)
        foot.setSpacing(10)
        self.tip = QLabel("未缴费车辆禁止自动放行，确需放行须由管理员授权并记录原因")
        self.tip.setStyleSheet(f"color:{T.DIM}; font-size:11px;")
        foot.addWidget(self.tip)
        foot.addStretch(1)

        self.btn_manual = QPushButton("授权放行")
        self.btn_manual.setObjectName("ghost")
        self.btn_manual.setCursor(Qt.PointingHandCursor)
        self.btn_manual.setFixedHeight(44)
        self.btn_manual.clicked.connect(self._on_manual)
        foot.addWidget(self.btn_manual)

        self.btn_pay = QPushButton("模拟缴费")
        self.btn_pay.setObjectName("primary")
        self.btn_pay.setCursor(Qt.PointingHandCursor)
        self.btn_pay.setFixedHeight(44)
        self.btn_pay.setMinimumWidth(150)
        self.btn_pay.clicked.connect(self._on_pay)
        foot.addWidget(self.btn_pay)

        self.btn_release = QPushButton("抬杆放行")
        self.btn_release.setObjectName("primary")
        self.btn_release.setCursor(Qt.PointingHandCursor)
        self.btn_release.setFixedHeight(44)
        self.btn_release.setMinimumWidth(150)
        self.btn_release.setEnabled(False)
        self.btn_release.clicked.connect(self._on_release)
        foot.addWidget(self.btn_release)

        lay.addLayout(foot)
        self.resize(920, 600)

    # ------------------------------------------------------------------ 逻辑
    @staticmethod
    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _on_pay(self):
        self.btn_pay.setEnabled(False)
        self.btn_pay.setText("处理中…")
        self.paid.emit()

    def mark_paid(self, *, notify: bool = True):
        self._is_paid = True
        self.pill.set_kind("ok", "已缴费")
        self.amount.setStyleSheet(
            f"color:{T.TEXT}; font-family:'{T.FONT_NUM}'; font-size:38px; font-weight:700;"
        )
        self.btn_pay.setEnabled(False)
        self.btn_pay.setText("已缴费")
        self.btn_release.setEnabled(True)
        self.btn_manual.setEnabled(False)
        self.tip.setText("缴费完成，可抬杆放行")
        if notify:
            toast(self, f"{self.bill.plate} 缴费 {self.bill.total:.2f} 元", "ok")

    def operation_failed(self, message: str):
        self.btn_pay.setEnabled(not self._is_paid and self.bill.total > 0)
        self.btn_pay.setText("模拟缴费")
        self.btn_release.setEnabled(self._is_paid or self.bill.total == 0)
        toast(self, message, "warn")

    def _sync_state(self):
        if self.bill.entry_photo:
            self.tile_in.set_image(self.bill.entry_photo)
        if self.bill.exit_photo:
            self.tile_out.set_image(self.bill.exit_photo)
        if self.bill.release_status in {"released", "passed"}:
            self.pill.set_kind("ok", "已放行")
            self.btn_pay.setEnabled(False)
            self.btn_manual.setEnabled(False)
            self.btn_release.setEnabled(False)
            self.tip.setText("已获得放行，可在主界面继续车辆通过流程")
        elif self._is_paid:
            self.mark_paid(notify=False)
        elif self.bill.total == 0:
            self.pill.set_kind("ok", "免费")
            self.btn_pay.setEnabled(False)
            self.btn_pay.setText("无需缴费")
            self.btn_release.setEnabled(True)
            self.btn_release.setText("免费放行")
            self.btn_manual.setEnabled(False)
            self.tip.setText("本次费用为 0 元，可直接放行")

    def _on_manual(self):
        username, ok = QInputDialog.getText(
            self, "管理员验证", "管理员用户名："
        )
        if not ok or not username.strip():
            return
        password, ok = QInputDialog.getText(
            self, "管理员验证", "管理员密码：", QLineEdit.Password
        )
        if not ok or not password:
            return
        reason, ok = QInputDialog.getText(
            self, "授权放行", "未缴费车辆放行原因（将写入审计日志）：",
            text="设备故障，人工核对后放行",
        )
        if not ok or not reason.strip():
            return
        self.authorize_requested.emit(username.strip(), password, reason.strip())

    def _on_release(self):
        self.released.emit("")

    # ------------------------------------------------------------------ 拖动
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.pos().y() < 64:
            self._drag_pos = ev.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPos() - self._drag_pos)
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None
        super().mouseReleaseEvent(ev)
