# -*- coding: utf-8 -*-
"""单个实时 3D 场景面板：一个 WebGL 页面，镜头在入口 / 出口之间飞。"""
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout,
)

from ..anim import RAISE, create_animator
from . import icons
from . import theme as T
from .widgets import Pill


class ScenePanel(QFrame):
    """实时 3D 场景（入口 / 出口共用一台镜头）。

    信号：
        raised(gate)        抬杆动画结束
        lowered(gate)       落杆动画结束
        open_changed(bool)  是否有闸杆处于抬起状态（用于启用「落杆」按钮）
    """

    raised = pyqtSignal(str)
    lowered = pyqtSignal(str)
    open_changed = pyqtSignal(bool)

    def __init__(self, anim_dir: str, mode: str = "auto", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._anim_dir = anim_dir
        self._mode = mode
        self._animator = None
        self._pending_gate = None
        self._pending_direction = None
        self._open_gate = None
        self._fallback_timer = QTimer(self)
        self._fallback_timer.setSingleShot(True)
        self._fallback_timer.timeout.connect(self._fallback_done)

        self._build()
        self._load()

    # ------------------------------------------------------------------ UI
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(T.PAD, 14, T.PAD, 14)
        outer.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(9)
        bar = QFrame()
        bar.setFixedSize(3, 12)
        bar.setStyleSheet(f"background:{T.PRIMARY}; border-radius:1px;")
        head.addWidget(bar)
        title = QLabel("实时 3D 场景")
        title.setObjectName("cardTitle")
        head.addWidget(title)

        self.pill_in = Pill("入口 · 待机", "idle")
        self.pill_out = Pill("出口 · 待机", "idle")
        head.addWidget(self.pill_in)
        head.addWidget(self.pill_out)
        head.addStretch(1)

        self.camera_hint = QLabel("加载中…")
        self.camera_hint.setObjectName("cardHint")
        head.addWidget(self.camera_hint)

        self.btn_reload = QToolButton()
        self.btn_reload.setIcon(QIcon(icons.icon_pixmap("refresh", 13, T.DIM)))
        self.btn_reload.setToolTip("重新加载 3D 场景")
        self.btn_reload.setCursor(Qt.PointingHandCursor)
        self.btn_reload.setStyleSheet(
            f"QToolButton{{border:none; background:transparent; padding:2px;}}"
            f"QToolButton:hover{{background:{T.PANEL_HI}; border-radius:6px;}}"
        )
        self.btn_reload.clicked.connect(self._load)
        head.addWidget(self.btn_reload)
        outer.addLayout(head)

        self.frame = QFrame()
        self.frame.setObjectName("sceneFrame")
        self.frame.setStyleSheet(
            f"QFrame#sceneFrame{{background:#E8EFF7; border:1px solid {T.LINE};"
            f" border-radius:10px;}}"
        )
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._holder = QVBoxLayout(self.frame)
        self._holder.setContentsMargins(1, 1, 1, 1)
        outer.addWidget(self.frame, 1)

        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.state_label = QLabel("等待车辆")
        self.state_label.setObjectName("cardHint")
        foot.addWidget(self.state_label)
        foot.addStretch(1)
        self.zoom_hint = QLabel("镜头随操作自动切换")
        self.zoom_hint.setObjectName("cardHint")
        foot.addWidget(self.zoom_hint)
        outer.addLayout(foot)

    # ------------------------------------------------------------------ 资源
    def _load(self):
        if self._animator is not None:
            try:
                self._animator.stop()
            except Exception:
                pass
            w = self._animator.surface()
            self._holder.removeWidget(w)
            w.setParent(None)
            self._animator = None

        self._animator = create_animator(self._anim_dir, self._mode, 30, gate="in")
        self._animator.stage.connect(self._on_stage)
        self._animator.finished.connect(self._on_finished)
        self._animator.meta_changed.connect(self._refresh_meta)
        self._animator.failed.connect(lambda msg: self.state_label.setText("3D 不可用：" + msg))

        self._holder.addWidget(self._animator.surface())
        self._refresh_meta()
        self.open_changed.emit(False)

    def _refresh_meta(self):
        if not self._animator:
            return
        self.camera_hint.setText(self._animator.mode_name())

    # ------------------------------------------------------------------ 控制
    def raise_gate(self, gate: str):
        self._pending_gate = gate
        self._pending_direction = RAISE
        self._set_pill(gate, "抬杆中…", "warn")
        self.state_label.setText(f"{'入口' if gate == 'in' else '出口'}道闸抬杆中…")

        if self._animator is not None and hasattr(self._animator, "trigger"):
            try:
                self._animator.trigger(gate, RAISE)
                return
            except Exception:
                pass
        # 没有实时 3D 时：走 1.2 秒的模拟，保证业务流程可演示
        self._fallback_timer.start(1200)

    def lower_current(self):
        if self._open_gate:
            self.lower_gate(self._open_gate)

    def lower_gate(self, gate: str):
        self._pending_gate = gate
        self._pending_direction = "lower"
        self._set_pill(gate, "落杆中…", "warn")
        self.state_label.setText(f"{'入口' if gate == 'in' else '出口'}道闸落杆中…")
        self.open_changed.emit(False)      # 落杆过程中禁用按钮，避免重复点击
        if self._animator is not None and hasattr(self._animator, "trigger"):
            try:
                self._animator.trigger(gate, "lower")
                return
            except Exception:
                pass
        self._fallback_timer.start(900)

    def has_open_gate(self) -> bool:
        return self._open_gate is not None

    # ------------------------------------------------------------------ 槽
    def _on_stage(self, stage: str):
        gate = self._pending_gate or "in"
        name = "入口" if gate == "in" else "出口"
        verb = "落杆" if self._pending_direction == "lower" else "抬杆"
        if stage == "focus":
            self._set_pill(gate, "镜头归位…", "info")
            self.state_label.setText(f"镜头正在对准{name}道闸…")
        else:
            self._set_pill(gate, f"{verb}中…", "warn")
            self.state_label.setText(f"{name}道闸{verb}中…")

    def _on_finished(self, direction: str):
        gate = self._pending_gate or "in"
        name = "入口" if gate == "in" else "出口"
        if direction == RAISE:
            self._set_pill(gate, "已抬起", "ok")
            self._open_gate = gate
            self.state_label.setText(f"{name}道闸已抬起 · 车辆通过后请落杆")
            self.open_changed.emit(True)
            self.raised.emit(gate)
        else:
            self._set_pill(gate, "待机", "idle")
            self._open_gate = None
            self.state_label.setText("闸杆已落下 · 等待下一辆车")
            self.open_changed.emit(False)
            self.lowered.emit(gate)

    def _fallback_done(self):
        self._on_finished(self._pending_direction or RAISE)

    def _set_pill(self, gate: str, text: str, kind: str):
        pill = self.pill_in if gate == "in" else self.pill_out
        name = "入口" if gate == "in" else "出口"
        pill.set_kind(kind, f"{name} · {text}")
