# -*- coding: utf-8 -*-
"""主界面：左操作 / 中 3D / 右数据 的三栏布局。"""
from datetime import datetime

from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import icons
from . import theme as T
from .exit_dialog import ExitDialog
from .rule_dialog import RuleManagerDialog
from .scene_panel import ScenePanel
from .widgets import (
    BrandMark, Card, ConfidenceBar, LiveClock, PlateBadge, PlateDelegate,
    SearchBox, StatCard, StatusDot, toast,
)

LEFT_W = 302
RIGHT_W = 382


class CaptureSurface(QWidget):
    """入口画面位：没有摄像头时显示取景框，接入真实帧用 set_frame(QImage)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix = None
        self.setMinimumHeight(110)

    def set_frame(self, image):
        self._pix = None if image is None or image.isNull() else QPixmap.fromImage(image)
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setPen(QPen(QColor(T.LINE), 1))
        p.setBrush(QColor("#F7FAFD"))
        p.drawRoundedRect(r, 10, 10)

        if self._pix is not None:
            p.save()
            p.setClipRect(r)
            scaled = self._pix.scaled(int(r.width()), int(r.height()),
                                      Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(int(r.left()), int(r.top()), scaled)
            p.restore()
            p.end()
            return

        p.setPen(QPen(QColor("#C3D3E3"), 1.4))
        L = 14
        for cx, cy, dx, dy in [
            (r.left() + 12, r.top() + 12, 1, 1),
            (r.right() - 12, r.top() + 12, -1, 1),
            (r.left() + 12, r.bottom() - 12, 1, -1),
            (r.right() - 12, r.bottom() - 12, -1, -1),
        ]:
            p.drawLine(int(cx), int(cy), int(cx + dx * L), int(cy))
            p.drawLine(int(cx), int(cy), int(cx), int(cy + dy * L))

        c = r.center()
        icons.paint_icon(p, "camera", QRectF(c.x() - 12, c.y() - 26, 24, 24), QColor("#B7C6D6"))
        p.setPen(QColor(T.DIM))
        f = QFont(T.FONT_UI)
        f.setPixelSize(11)
        p.setFont(f)
        p.drawText(QRectF(r.left(), c.y() - 2, r.width(), 18), Qt.AlignHCenter, "等待摄像机画面")
        p.end()


class MainWindow(QMainWindow):
    def __init__(
        self,
        service,
        anim_dir: str,
        anim_mode: str = "auto",
        *,
        rule_service=None,
        user_session=None,
    ):
        super().__init__()
        self.service = service
        self._anim_dir = anim_dir
        self._anim_mode = anim_mode
        self.rule_service = rule_service
        self.user_session = user_session
        self._pending_entry = None
        self._pending_exit = None
        self._last_event = "—"

        self.setWindowTitle("智慧停车 · 出入口控制台")
        self.resize(1440, 900)
        self.setMinimumSize(1200, 720)
        self._build()
        self._refresh_table()
        self._start_timers()
        self._log("控制台启动 · 等待车辆")

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_topbar())

        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(14)

        lay.addWidget(self._build_left(), 0)

        self.scene = ScenePanel(self._anim_dir, self._anim_mode)
        self.scene.raised.connect(self._on_gate_raised)
        self.scene.lowered.connect(self._on_gate_lowered)
        self.scene.open_changed.connect(self._on_open_changed)
        lay.addWidget(self.scene, 1)

        lay.addWidget(self._build_right(), 0)
        outer.addWidget(body, 1)

        self.status_hint = QLabel("系统就绪 · 演示模式")
        self.statusBar().addWidget(self.status_hint)
        user_text = (
            f"当前用户：{self.user_session.username} · " if self.user_session else ""
        )
        right = QLabel(user_text + "成员 A · 界面与动画模块 v2.1")
        right.setStyleSheet(f"color:{T.DIM}; font-size:11px;")
        self.statusBar().addPermanentWidget(right)
        self.statusBar().setFixedHeight(30)

    # ---------------- 顶栏
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(62)
        bar.setStyleSheet(f"background:{T.BG1}; border-bottom:1px solid {T.LINE};")
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 8, 22, 8)
        h.setSpacing(12)

        h.addWidget(BrandMark(34))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t1 = QLabel("智慧停车 · 出入口控制台")
        t1.setStyleSheet(f"color:{T.TEXT}; font-size:17px; font-weight:700; letter-spacing:1px;")
        t2 = QLabel("SMART PARKING  /  LIVE 3D CONSOLE")
        t2.setStyleSheet(f"color:{T.DIM}; font-size:10px; letter-spacing:2px;")
        titles.addWidget(t1)
        titles.addWidget(t2)
        h.addLayout(titles)
        h.addStretch(1)

        for label, color in (("数据库", T.ACCENT), ("识别服务", T.ACCENT), ("3D 场景", T.PRIMARY)):
            h.addWidget(StatusDot(color))
            lb = QLabel(label)
            lb.setStyleSheet(f"color:{T.MUTED}; font-size:11px;")
            h.addWidget(lb)
            h.addSpacing(6)

        h.addSpacing(10)
        if self.rule_service is not None:
            self.btn_rules = QPushButton("收费标准")
            self.btn_rules.setObjectName("ghost")
            self.btn_rules.setFixedHeight(34)
            self.btn_rules.setCursor(Qt.PointingHandCursor)
            self.btn_rules.clicked.connect(self._open_rule_manager)
            h.addWidget(self.btn_rules)
            h.addSpacing(4)
        self.clock = LiveClock()
        h.addWidget(self.clock)
        return bar

    def _open_rule_manager(self):
        if self.user_session is None or not self.user_session.is_admin:
            toast(self, "收费标准仅管理员可管理", "warn")
            return
        RuleManagerDialog(self.rule_service, self.user_session, self).exec_()

    # ---------------- 左：人工操作
    def _build_left(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(LEFT_W)
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        ops = Card("人工操作")
        self.btn_entry = QPushButton("进场登记")
        self.btn_entry.setObjectName("primary")
        self.btn_entry.setCursor(Qt.PointingHandCursor)
        self.btn_entry.setFixedHeight(50)
        self.btn_entry.clicked.connect(lambda: self._on_entry())
        ops.add(self.btn_entry)

        self.btn_exit = QPushButton("出场结算")
        self.btn_exit.setObjectName("ghost")
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setFixedHeight(46)
        self.btn_exit.clicked.connect(self._on_exit)
        ops.add(self.btn_exit)

        self.btn_lower = QPushButton("车辆已通过 · 落杆")
        self.btn_lower.setObjectName("ghost")
        self.btn_lower.setCursor(Qt.PointingHandCursor)
        self.btn_lower.setFixedHeight(42)
        self.btn_lower.setEnabled(False)
        self.btn_lower.clicked.connect(self._on_lower)
        ops.add(self.btn_lower)

        tip = QLabel("识别 → 抬杆 → 缴费 / 放行 → 落杆")
        tip.setObjectName("cardHint")
        tip.setWordWrap(True)
        ops.add(tip)
        lay.addWidget(ops, 0)

        rec = Card("入口识别", "CAM-01")
        self.capture = CaptureSurface()
        self.capture.setFixedHeight(148)
        rec.add(self.capture)

        self.plate = PlateBadge("", "blue", 46)
        rec.add(self.plate)

        conf_row = QHBoxLayout()
        cap = QLabel("置信度")
        cap.setObjectName("muted")
        self.conf_value = QLabel("—")
        self.conf_value.setStyleSheet(
            f"color:{T.MUTED}; font-family:'{T.FONT_NUM}'; font-size:12px;")
        conf_row.addWidget(cap)
        conf_row.addStretch(1)
        conf_row.addWidget(self.conf_value)
        rec.add_layout(conf_row)

        self.conf_bar = ConfidenceBar(0.0)
        rec.add(self.conf_bar)

        self.rec_hint = QLabel("点击「进场登记」开始识别")
        self.rec_hint.setObjectName("cardHint")
        self.rec_hint.setWordWrap(True)
        rec.add(self.rec_hint)
        rec.body.addStretch(1)

        mini = QHBoxLayout()
        mini.setSpacing(14)
        for title, value in (("识别成功率", "97.6%"), ("平均耗时", "0.8 s"), ("转人工", "2 次")):
            box = QVBoxLayout()
            box.setSpacing(0)
            v = QLabel(value)
            v.setStyleSheet(
                f"color:{T.TEXT}; font-family:'{T.FONT_NUM}'; font-size:15px; font-weight:600;")
            t = QLabel(title)
            t.setObjectName("cardHint")
            box.addWidget(v)
            box.addWidget(t)
            mini.addLayout(box)
        mini.addStretch(1)
        rec.add_layout(mini)
        lay.addWidget(rec, 1)
        return col

    # ---------------- 右：停车场数据
    def _build_right(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(RIGHT_W)
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.card_present = StatCard("在场车辆", "0", "辆", "car", T.PRIMARY)
        self.card_today = StatCard("今日车次", "0", "次", "layers", T.BLUE)
        self.card_income = StatCard("今日收入", "0.00", "元", "wallet", T.AMBER)
        self.card_free = StatCard("剩余车位", "0", "/ 50", "gate", T.ACCENT)
        grid.addWidget(self.card_present, 0, 0)
        grid.addWidget(self.card_today, 0, 1)
        grid.addWidget(self.card_income, 1, 0)
        grid.addWidget(self.card_free, 1, 1)
        lay.addLayout(grid, 0)

        card = Card("在场车辆", "")
        self.count_hint = card.hint_label
        self.search = SearchBox("搜索车牌 / 状态")
        self.search.textChanged.connect(self._filter_table)
        card.add(self.search)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["车牌", "进场", "已停", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setItemDelegateForColumn(0, PlateDelegate(self.table))
        self.table.verticalHeader().setDefaultSectionSize(36)
        hh = self.table.horizontalHeader()
        hh.setFixedHeight(32)
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 124)
        self.table.setColumnWidth(1, 78)
        self.table.setColumnWidth(2, 60)
        self.table.doubleClicked.connect(lambda _i: self._on_exit())
        card.add(self.table, 1)
        lay.addWidget(card, 1)

        ev = Card("最近事件")
        self.ev_labels = []
        for _ in range(3):
            lb = QLabel("—")
            lb.setObjectName("cardHint")
            lb.setWordWrap(True)
            ev.add(lb)
            self.ev_labels.append(lb)
        lay.addWidget(ev, 0)
        return col

    # ------------------------------------------------------------------ 数据
    def _start_timers(self):
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._refresh_durations)
        self._tick.start(1000)

        self._refresh = QTimer(self)
        self._refresh.timeout.connect(self._refresh_table)
        self._refresh.start(5000)

    def _refresh_table(self):
        rows = self.service.present_vehicles()
        stats = self.service.stats()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            item0 = QTableWidgetItem(r.plate)
            item0.setData(Qt.UserRole, r.kind)
            self.table.setItem(i, 0, item0)

            it1 = QTableWidgetItem(r.enter_time.strftime("%H:%M"))
            it1.setForeground(QColor(T.TEXT_SUB))
            self.table.setItem(i, 1, it1)

            mins = r.duration_min
            it2 = QTableWidgetItem(f"{mins // 60}h{mins % 60:02d}")
            it2.setForeground(QColor(T.TEXT))
            it2.setFont(self._num_font(12))
            self.table.setItem(i, 2, it2)

            it3 = QTableWidgetItem(r.status)
            it3.setForeground(QColor(T.ACCENT))
            self.table.setItem(i, 3, it3)

        self.count_hint.setText(f"共 {len(rows)} 辆")
        self.card_present.set_value(str(stats["present"]))
        self.card_today.set_value(str(stats["today_count"]))
        self.card_income.set_value(f"{stats['today_income']:.2f}")
        self.card_free.set_value(str(stats["free_spaces"]))

    def _refresh_durations(self):
        for i, r in enumerate(self.service.present_vehicles()):
            if i >= self.table.rowCount():
                break
            it = self.table.item(i, 2)
            if it:
                mins = r.duration_min
                it.setText(f"{mins // 60}h{mins % 60:02d}")

    def _filter_table(self, text: str):
        text = text.strip().lower()
        for i in range(self.table.rowCount()):
            match = True
            if text:
                match = any(
                    text in (self.table.item(i, c).text().lower() if self.table.item(i, c) else "")
                    for c in range(self.table.columnCount())
                )
            self.table.setRowHidden(i, not match)

    @staticmethod
    def _num_font(size: int) -> QFont:
        f = QFont(T.FONT_NUM)
        f.setPixelSize(size)
        return f

    # ------------------------------------------------------------------ 事件
    def _log(self, text: str):
        self._last_event = datetime.now().strftime("%H:%M:%S") + " · " + text
        self.status_hint.setText(self._last_event)
        if hasattr(self, "ev_labels"):
            for i in range(len(self.ev_labels) - 1, 0, -1):
                self.ev_labels[i].setText(self.ev_labels[i - 1].text())
            self.ev_labels[0].setText(self._last_event)

    # ------------------------------------------------------------------ 交互
    def _on_entry(self, plate=None, conf=None, kind=None):
        """进场：识别 → 抬杆。

        识别结果可以由外部传入（接入真实识别服务时直接调用
        `win._on_entry(plate, conf, kind)`），不传就现场调一次 service.recognize()。
        """
        if plate is None:
            plate, conf, kind = self.service.recognize()
        self._pending_entry = (plate, kind)
        self.plate.set_plate(plate, kind)
        self.conf_value.setText(f"{conf:.3f}")
        self.conf_bar.set_value(conf)
        self.rec_hint.setText("识别成功，入口道闸抬杆中")
        self._log(f"进场 · {plate} 识别成功 · 置信度 {conf:.3f}")
        toast(self, f"{plate} 识别成功 · 置信度 {conf:.3f}", "ok")
        self.scene.raise_gate("in")

    def _on_lower(self):
        self.scene.lower_current()

    def _on_open_changed(self, opened: bool):
        self.btn_lower.setEnabled(opened)
        self.btn_lower.setObjectName("primary" if opened else "ghost")
        self.btn_lower.style().unpolish(self.btn_lower)
        self.btn_lower.style().polish(self.btn_lower)

    def _on_gate_raised(self, gate: str):
        if gate == "in":
            if self._pending_entry:
                plate, kind = self._pending_entry
                self._pending_entry = None
                self.service.add_entry(plate, kind)
                self._refresh_table()
                self.rec_hint.setText("闸杆已抬起，车辆入场")
                self._log(f"入口抬杆 · {plate} 入场")
        else:
            plate = self._pending_exit
            self._pending_exit = None
            if plate:
                self.service.exit_vehicle(plate)
                self._refresh_table()
                self._log(f"出口抬杆 · {plate} 离场")

    def _on_gate_lowered(self, gate: str):
        self._log(f"{'入口' if gate == 'in' else '出口'}落杆 · 等待下一辆车")

    def _on_exit(self):
        row = self.table.currentRow()
        if row < 0:
            row = 0
        if self.table.rowCount() == 0:
            toast(self, "当前没有在场车辆", "warn")
            return
        plate = self.table.item(row, 0).text()
        bill = self.service.bill(plate)
        dlg = ExitDialog(bill, self)
        dlg.paid.connect(lambda: self._after_pay(plate, bill))
        dlg.released.connect(lambda reason: self._after_release(plate, reason))
        dlg.finished.connect(lambda _r: self._refresh_table())
        dlg.exec_()

    def _after_pay(self, plate: str, bill=None):
        if bill is not None:
            self.service.pay(plate, bill.total)
            self.card_income.set_value(f"{self.service.stats()['today_income']:.2f}")
            self._log(f"缴费 · {plate} {bill.total:.2f} 元")

    def _after_release(self, plate: str, reason: str):
        self._pending_exit = plate
        if reason:
            toast(self, f"{plate} 授权放行：{reason}", "warn")
            self._log(f"授权放行 · {plate}（{reason}）")
        else:
            toast(self, f"{plate} 已放行", "ok")
            self._log(f"放行 · {plate} 出口抬杆")
        self.scene.raise_gate("out")
