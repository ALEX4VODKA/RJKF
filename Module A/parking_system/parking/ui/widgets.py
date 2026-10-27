# -*- coding: utf-8 -*-
"""通用控件：卡片、车牌牌面、指标卡、状态胶囊、置信度条、浮动提示。"""
from PyQt5.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import (QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt5.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit, QSizePolicy,
    QStyledItemDelegate, QVBoxLayout, QWidget,
)

from . import icons
from . import theme as T


# ------------------------------------------------------------------ 卡片
class Card(QFrame):
    """带标题的卡片容器。"""

    def __init__(self, title: str = "", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(T.PAD, 14, T.PAD, T.PAD)
        self._outer.setSpacing(12)

        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self._title_row = QHBoxLayout()
        self._title_row.setSpacing(8)

        if title:
            bar = QFrame()
            bar.setFixedSize(3, 12)
            bar.setStyleSheet(f"background:{T.PRIMARY}; border-radius:1px;")
            self._title_row.addWidget(bar)
            self.title_label = QLabel(title.upper())
            self.title_label.setObjectName("cardTitle")
            self._title_row.addWidget(self.title_label)
            self._title_row.addStretch(1)
            self.header.addLayout(self._title_row)
            self.hint_label = QLabel(hint)
            self.hint_label.setObjectName("cardHint")
            self.header.addWidget(self.hint_label, 0, Qt.AlignRight)
            head_host = QWidget()
            head_host.setLayout(self.header)
            head_host.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self._outer.addWidget(head_host)
        else:
            self.hint_label = QLabel("")

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self._outer.addLayout(self.body, 1)

    def add(self, widget, stretch: int = 0):
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout, stretch: int = 0):
        self.body.addLayout(layout, stretch)


# ------------------------------------------------------------------ 车牌
class PlateBadge(QWidget):
    """按真实车牌比例绘制的牌面，蓝牌/黄牌/绿牌三种。"""

    def __init__(self, plate: str = "", kind: str = "blue", height: int = 56, parent=None):
        super().__init__(parent)
        self._plate = plate
        self._kind = kind
        self._h = height
        self.setFixedHeight(height)
        self.setFixedWidth(int(height * 3.4))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._font_family = "Microsoft YaHei UI"

    def set_plate(self, plate: str, kind: str = None):
        self._plate = plate
        if kind:
            self._kind = kind
        self.update()

    def sizeHint(self):
        return QSize(int(self._h * 3.3), self._h)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(1, 1, w - 2, h - 2)

        bg, fg, edge = {
            "blue": (T.PLATE_BLUE, "#FFFFFF", "#8FB0FF"),
            "yellow": (T.PLATE_YELLOW, "#1A1205", "#FFE29A"),
            "green": (T.PLATE_GREEN, "#FFFFFF", "#9FE6C2"),
        }.get(self._kind, (T.PLATE_BLUE, "#FFFFFF", "#8FB0FF"))

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(bg).lighter(112))
        grad.setColorAt(1.0, QColor(bg).darker(108))
        p.setBrush(grad)
        p.setPen(QPen(QColor(edge).darker(160), 1.2))
        p.drawRoundedRect(rect, 8, 8)

        # 内描边（真实车牌的白色细框）
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(edge), 1.0))
        p.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 5, 5)

        if not self._plate:
            p.setPen(QColor(fg))
            f = QFont(self._font_family, max(9, int(h * 0.20)))
            p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, "等待识别")
            p.end()
            return

        f = QFont(self._font_family)
        f.setBold(True)
        size = int(h * 0.42)
        while size > 8:
            f.setPixelSize(size)
            f.setLetterSpacing(QFont.AbsoluteSpacing, size * 0.10)
            if QFontMetrics(f).horizontalAdvance(self._plate) <= w - 22:
                break
            size -= 1
        p.setFont(f)
        p.setPen(QColor(fg))
        p.drawText(rect.adjusted(0, 0, 0, int(-h * 0.02)), Qt.AlignCenter, self._plate)
        p.end()


# ------------------------------------------------------------------ 指标卡
class StatCard(QFrame):
    """图标 + 标题 + 数值 + 单位。"""

    def __init__(self, title: str, value: str = "0", unit: str = "",
                 icon: str = "car", accent: str = T.ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFlat")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._icon = QLabel()
        self._icon.setPixmap(icons.icon_pixmap(icon, 14, accent))
        self._icon.setFixedSize(14, 14)
        top.addWidget(self._icon)
        self._title = QLabel(title)
        self._title.setObjectName("muted")
        top.addWidget(self._title)
        top.addStretch(1)
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._value = QLabel(value)
        self._value.setObjectName("value")
        row.addWidget(self._value)
        self._unit = QLabel(unit)
        self._unit.setObjectName("unit")
        row.addWidget(self._unit, 0, Qt.AlignBottom)
        row.addStretch(1)
        lay.addLayout(row)

    def set_value(self, text: str):
        self._value.setText(text)


# ------------------------------------------------------------------ 胶囊
class Pill(QLabel):
    """状态胶囊：ok / warn / danger / info / idle。"""

    STYLES = {
        "ok": (T.ACCENT, T.ACCENT_SOFT),
        "warn": (T.AMBER, T.AMBER_SOFT),
        "danger": (T.RED, T.RED_SOFT),
        "info": (T.PRIMARY, T.PRIMARY_SOFT),
        "idle": (T.MUTED, "#F1F4F8"),
    }

    def __init__(self, text: str = "", kind: str = "idle", parent=None):
        super().__init__(text, parent)
        self.set_kind(kind)

    def set_kind(self, kind: str, text: str = None):
        if text is not None:
            self.setText(text)
        color, bg = self.STYLES.get(kind, self.STYLES["idle"])
        self.setStyleSheet(
            f"color:{color}; background:{bg}; border:1px solid {color}33;"
            f"border-radius:9px; padding:2px 9px; font-size:11px;"
        )


# ------------------------------------------------------------------ 置信度
class ConfidenceBar(QWidget):
    def __init__(self, value: float = 0.0, parent=None):
        super().__init__(parent)
        self._v = value
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, v: float):
        self._v = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E8EDF3"))
        p.drawRoundedRect(r, 3, 3)
        if self._v > 0:
            color = T.ACCENT if self._v >= 0.8 else (T.AMBER if self._v >= 0.6 else T.RED)
            w = max(6.0, r.width() * self._v)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(0, 0, w, r.height()), 3, 3)
        p.end()


# ------------------------------------------------------------------ 时钟
class StatusDot(QWidget):
    def __init__(self, color: str = T.ACCENT, size: int = 8, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size + 6, size + 6)
        self._size = size

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center()
        glow = QColor(self._color)
        glow.setAlpha(50)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, self._size * 0.95, self._size * 0.95)
        p.setBrush(self._color)
        p.drawEllipse(c, self._size / 2, self._size / 2)
        p.end()


class LiveClock(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setStyleSheet(
            f"color:{T.TEXT_SUB}; font-family:'{T.FONT_NUM}'; font-size:18px; letter-spacing:2px;"
        )
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(1000)
        self._tick()

    def _tick(self):
        from datetime import datetime
        now = datetime.now()
        week = "一二三四五六日"[now.weekday()]
        self.setText(f"{now:%H:%M:%S}   <span style='color:{T.MUTED};font-size:12px'>{now:%Y-%m-%d} 周{week}</span>")


# ------------------------------------------------------------------ 搜索框
class SearchBox(QLineEdit):
    def __init__(self, placeholder: str = "搜索车牌", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.addAction(QIcon(icons.icon_pixmap("search", 14, T.DIM)), QLineEdit.LeadingPosition)
        self.setFixedHeight(34)


# ------------------------------------------------------------------ 表格车牌列
class PlateDelegate(QStyledItemDelegate):
    """把「车牌」列画成小牌面，比纯文字更有辨识度。"""

    def paint(self, painter, option, index):
        plate = index.data(Qt.DisplayRole) or ""
        kind = index.data(Qt.UserRole) or "blue"
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(option.rect).adjusted(8, 8, -8, -8)
        h = min(rect.height(), 26)
        w = min(rect.width(), h * 3.5)
        plate_rect = QRectF(rect.left(), rect.top() + (rect.height() - h) / 2, w, h)

        bg = {"blue": T.PLATE_BLUE, "yellow": T.PLATE_YELLOW, "green": T.PLATE_GREEN}.get(kind, T.PLATE_BLUE)
        fg = "#1A1205" if kind == "yellow" else "#FFFFFF"
        painter.setPen(QPen(QColor(bg).darker(115), 1))
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(plate_rect, 5, 5)

        f = QFont(T.FONT_UI)
        f.setPixelSize(int(h * 0.52))
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        painter.setFont(f)
        painter.setPen(QColor(fg))
        painter.drawText(plate_rect, Qt.AlignCenter, plate)
        painter.restore()


# ------------------------------------------------------------------ 浮动提示
class Toast(QWidget):
    """窗口右下角的轻提示，自动淡出。

    定时器作为自己的子对象，控件销毁时定时器一起销毁，
    不会出现“控件已析构、定时器还在回调”的 RuntimeError。
    """

    def __init__(self, parent, text: str, kind: str = "ok"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        color = {"ok": T.ACCENT, "warn": T.AMBER, "error": T.RED, "info": T.PRIMARY}.get(kind, T.ACCENT)
        self.setStyleSheet(
            f"background:#FFFFFF; border:1px solid {color}66;"
            f"border-radius:10px; color:{T.TEXT}; font-size:13px;"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 18, 0)
        lay.setSpacing(9)
        ic = QLabel()
        ic.setPixmap(icons.icon_pixmap("check" if kind == "ok" else "alert", 14, color))
        ic.setFixedSize(14, 14)
        lay.addWidget(ic)
        lb = QLabel(text)
        lb.setStyleSheet(f"color:{T.TEXT}; font-size:13px;")
        lay.addWidget(lb)

        lb.ensurePolished()
        fm = QFontMetrics(lb.font())
        width = max(lb.sizeHint().width(), fm.horizontalAdvance(text)) + 16 + 14 + 9 + 22
        self.setFixedSize(width, 42)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

    def pop(self, duration: int = 1800):
        parent = self.parentWidget()
        if parent:
            self.move((parent.width() - self.width()) // 2, 108)
        self.show()
        self.raise_()

        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._timer.start(duration)

    def _fade_out(self):
        # 控件可能已被父窗口销毁，这里做一次防御
        try:
            effect = self._effect
        except RuntimeError:
            return
        if effect is None:
            return
        try:
            out = QPropertyAnimation(effect, b"opacity", self)
            out.setDuration(280)
            out.setStartValue(1.0)
            out.setEndValue(0.0)
            out.setEasingCurve(QEasingCurve.InCubic)
            out.finished.connect(self.deleteLater)
            out.start(QPropertyAnimation.DeleteWhenStopped)
            self._out = out
        except RuntimeError:
            self.close()


def toast(parent, text: str, kind: str = "ok"):
    t = Toast(parent, text, kind)
    t.pop()
    return t


# ------------------------------------------------------------------ 徽标
def _paint_brand(p: QPainter, s: int):
    """绘制品牌标记：渐变方块 + 停车「P」+ 轨道弧。"""
    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0.0, QColor(T.PRIMARY))
    grad.setColorAt(1.0, QColor("#2AA8FF"))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.30, s * 0.30)

    p.setPen(QPen(QColor("#052422"), s * 0.075, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(s * 0.34, s * 0.26), QPointF(s * 0.34, s * 0.74))
    path = QPainterPath()
    path.moveTo(s * 0.34, s * 0.27)
    path.lineTo(s * 0.56, s * 0.27)
    path.arcTo(QRectF(s * 0.40, s * 0.27, s * 0.36, s * 0.30), 90, -180)
    path.lineTo(s * 0.34, s * 0.42)
    p.drawPath(path)


def brand_pixmap(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    _paint_brand(p, size)
    p.end()
    return pm


class BrandMark(QWidget):
    """左上角品牌标记控件。"""

    def __init__(self, size: int = 34, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._size = size

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        _paint_brand(p, self._size)
        p.end()
