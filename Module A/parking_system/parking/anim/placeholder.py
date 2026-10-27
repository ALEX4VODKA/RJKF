# -*- coding: utf-8 -*-
"""占位动画：在没有接入 Blender 资源时，先把位置、比例和交互留出来。

播放时只用一条扫描线模拟“动画进行中”，不伪造抬杆画面，
便于答辩时说明哪些是模拟、哪些是真实资源。
"""
from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import QSizePolicy, QWidget

from ..ui import theme as T
from .base import RAISE, GateAnimator


class PlaceholderSurface(QWidget):
    """预留画布（自适应尺寸），带警示条纹与虚线框，一眼能看出是待接入区域。"""

    clicked = pyqtSignal()

    def __init__(self, hint: str = "", parent=None):
        super().__init__(parent)
        self._hint = hint
        self._phase = 0.0
        self._busy = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setMinimumSize(180, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.ArrowCursor)

    # ------------------------------------------------------------------
    def start_scan(self):
        self._busy = True
        self._phase = 0.0
        self._timer.start(16)

    def stop_scan(self):
        self._busy = False
        self._timer.stop()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def set_hint(self, hint: str):
        self._hint = hint
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        compact = h < 150

        # 背景
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#F7FAFD"))
        grad.setColorAt(1.0, QColor("#EEF4FA"))
        p.fillRect(self.rect(), grad)

        # 顶部 / 底部警示条纹
        self._hazard(p, QRectF(0, 0, w, 4))
        self._hazard(p, QRectF(0, h - 4, w, 4))

        # 淡网格
        p.setPen(QPen(QColor("#E3ECF5"), 1))
        step = 40
        x = 8
        while x < w - 8:
            p.drawLine(QPointF(x, 8), QPointF(x, h - 8))
            x += step
        y = 8
        while y < h - 8:
            p.drawLine(QPointF(8, y), QPointF(w - 8, y))
            y += step

        # 中央虚线框
        inset = 12 if compact else 24
        box = QRectF(inset, inset, w - inset * 2, h - inset * 2)
        pen = QPen(QColor("#C9D7E5"), 1.2, Qt.DashLine)
        pen.setDashPattern([6, 6])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(box, 10, 10)

        cx = w / 2
        cy = h / 2

        # 道闸线稿（画面较小时省略，避免压住文字）
        if not compact:
            icon_w = 56 if h < 200 else 68
            icon_rect = QRectF(cx - icon_w / 2, cy - icon_w - 4, icon_w, icon_w)
            glow = QRadialGradient(QPointF(cx, cy - 34), 90)
            glow.setColorAt(0.0, QColor(46, 230, 200, 20))
            glow.setColorAt(1.0, QColor(46, 230, 200, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(cx, cy - 34), 100, 78)

            post_x = icon_rect.left() + 9
            arm_y = icon_rect.top() + 11
            p.setPen(QPen(QColor("#8FA9C2"), 2.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(post_x, icon_rect.bottom() - 4), QPointF(post_x, icon_rect.top() + 2))
            p.drawLine(QPointF(post_x, arm_y), QPointF(icon_rect.right() - 2, arm_y))
            p.setPen(QPen(QColor("#B9CBDC"), 1.3))
            for i in range(4):
                x0 = post_x + 10 + i * 11
                p.drawLine(QPointF(x0, arm_y + 3), QPointF(x0 + 8, arm_y + 14))
            p.setPen(QPen(QColor("#8FA9C2"), 2.0))
            p.drawLine(QPointF(post_x - 8, icon_rect.bottom() - 4),
                       QPointF(post_x + 8, icon_rect.bottom() - 4))

        # 文案
        ty = cy - (18 if compact else 4)
        p.setPen(QColor("#5E7387"))
        f = QFont(T.FONT_UI)
        f.setPixelSize(12 if compact else 13)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(16, ty, w - 32, 18), Qt.AlignHCenter | Qt.AlignTop, "道闸动画预留位")

        p.setPen(QColor("#93A6B8"))
        f2 = QFont("Consolas")
        f2.setPixelSize(9 if compact else 10)
        p.setFont(f2)
        p.drawText(QRectF(16, ty + 19, w - 32, 32),
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self._hint)

        # 扫描线
        if self._busy:
            y = 24 + (h - 48) * self._phase
            g2 = QLinearGradient(0, y - 20, 0, y + 20)
            g2.setColorAt(0.0, QColor(46, 230, 200, 0))
            g2.setColorAt(0.5, QColor(46, 230, 200, 70))
            g2.setColorAt(1.0, QColor(46, 230, 200, 0))
            p.fillRect(QRectF(24, y - 20, w - 48, 40), g2)
            p.setPen(QPen(QColor(46, 230, 200, 160), 1))
            p.drawLine(QPointF(24, y), QPointF(w - 24, y))

        # 角标（画面较小时省略，避免与提示文字重叠）
        if h < 190:
            p.end()
            return
        p.setPen(QColor("#AFC0D0"))
        f3 = QFont("Consolas")
        f3.setPixelSize(10)
        p.setFont(f3)
        p.drawText(QRectF(30, h - 34, 200, 16), Qt.AlignLeft | Qt.AlignVCenter, "3D VIEWPORT")
        p.drawText(QRectF(w - 230, h - 34, 200, 16), Qt.AlignRight | Qt.AlignVCenter,
                   "READY TO PLUG IN")
        p.end()

    @staticmethod
    def _hazard(p: QPainter, rect: QRectF):
        p.save()
        p.setClipRect(rect)
        p.fillRect(rect, QColor("#F0F5FA"))
        p.setPen(QPen(QColor("#DCE6F0"), 6))
        step = 18
        x = -rect.height()
        while x < rect.width() + rect.height():
            p.drawLine(QPointF(x, rect.top()), QPointF(x + rect.height() + 8, rect.bottom() + 8))
            x += step
        p.restore()


class PlaceholderAnimator(GateAnimator):
    """资源未就绪时的实现：保留交互节奏，播放结束信号照常发出。"""

    def __init__(self, hint: str = "", duration_ms: int = 900, prelude_ms: int = 600,
                 has_prelude: bool = False, parent=None):
        super().__init__(parent)
        self._surface = PlaceholderSurface(hint)
        self._duration = duration_ms
        self._prelude = prelude_ms
        self._has_prelude = has_prelude
        self._stage = "action"
        self._direction = None
        self._busy = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

    def surface(self):
        return self._surface

    def play(self, direction: str):
        if self._busy:
            return
        self._direction = direction
        self._busy = True
        self._surface.start_scan()
        if direction == RAISE and self._has_prelude:
            self._stage = "focus"
            self.stage.emit("focus")
            self.started.emit(direction)
            self._timer.start(self._prelude)
        else:
            self._stage = "action"
            self.stage.emit("action")
            self.started.emit(direction)
            self._timer.start(self._duration)

    def _tick(self):
        if self._stage == "focus":
            self._stage = "action"
            self.stage.emit("action")
            self._timer.start(self._duration)
            return
        self._busy = False
        self._surface.stop_scan()
        self.finished.emit(self._direction)

    def _done(self):
        self._busy = False
        self._surface.stop_scan()
        self.finished.emit(self._direction)

    def stop(self):
        self._timer.stop()
        self._busy = False
        self._surface.stop_scan()

    def is_busy(self) -> bool:
        return self._busy

    def mode_name(self) -> str:
        return "预留位"

    def has_prelude(self) -> bool:
        return self._has_prelude and self._stage == "focus"

    def describe(self) -> str:
        return "未接入资源"
