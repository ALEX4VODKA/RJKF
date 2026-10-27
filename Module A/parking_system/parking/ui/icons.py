# -*- coding: utf-8 -*-
"""纯代码绘制的线性图标，避免依赖外部图片资源。"""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

_ICONS = {
    "camera", "gate", "car", "wallet", "clock", "search", "close",
    "min", "max", "chevron", "alert", "check", "refresh", "layers",
}


def paint_icon(p: QPainter, name: str, rect: QRectF, color: QColor, width: float = 1.6):
    if name not in _ICONS:
        return
    p.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cx, cy = x + w / 2, y + h / 2

    if name == "camera":
        p.drawRoundedRect(QRectF(x + w * 0.06, y + h * 0.26, w * 0.88, h * 0.56), 3, 3)
        p.drawEllipse(QRectF(cx - w * 0.16, cy - h * 0.08, w * 0.32, h * 0.32))
        p.drawLine(QPointF(x + w * 0.28, y + h * 0.26), QPointF(x + w * 0.36, y + h * 0.12))
        p.drawLine(QPointF(x + w * 0.36, y + h * 0.12), QPointF(x + w * 0.64, y + h * 0.12))
        p.drawLine(QPointF(x + w * 0.64, y + h * 0.12), QPointF(x + w * 0.72, y + h * 0.26))
    elif name == "gate":
        p.drawLine(QPointF(x + w * 0.18, y + h * 0.10), QPointF(x + w * 0.18, y + h * 0.92))
        p.drawLine(QPointF(x + w * 0.18, y + h * 0.28), QPointF(x + w * 0.86, y + h * 0.28))
        p.drawLine(QPointF(x + w * 0.30, y + h * 0.28), QPointF(x + w * 0.42, y + h * 0.62))
        p.drawLine(QPointF(x + w * 0.52, y + h * 0.28), QPointF(x + w * 0.64, y + h * 0.62))
        p.drawLine(QPointF(x + w * 0.74, y + h * 0.28), QPointF(x + w * 0.86, y + h * 0.62))
    elif name == "car":
        path = QPainterPath()
        path.moveTo(x + w * 0.10, y + h * 0.66)
        path.lineTo(x + w * 0.20, y + h * 0.44)
        path.lineTo(x + w * 0.34, y + h * 0.32)
        path.lineTo(x + w * 0.68, y + h * 0.32)
        path.lineTo(x + w * 0.82, y + h * 0.46)
        path.lineTo(x + w * 0.90, y + h * 0.66)
        p.drawPath(path)
        p.drawLine(QPointF(x + w * 0.10, y + h * 0.66), QPointF(x + w * 0.90, y + h * 0.66))
        p.drawEllipse(QRectF(x + w * 0.20, y + h * 0.60, w * 0.16, h * 0.16))
        p.drawEllipse(QRectF(x + w * 0.64, y + h * 0.60, w * 0.16, h * 0.16))
    elif name == "wallet":
        p.drawRoundedRect(QRectF(x + w * 0.10, y + h * 0.26, w * 0.80, h * 0.52), 3, 3)
        p.drawLine(QPointF(x + w * 0.10, y + h * 0.42), QPointF(x + w * 0.90, y + h * 0.42))
        p.drawEllipse(QRectF(x + w * 0.62, y + h * 0.55, w * 0.12, h * 0.12))
    elif name == "clock":
        p.drawEllipse(QRectF(x + w * 0.10, y + h * 0.10, w * 0.80, h * 0.80))
        p.drawLine(QPointF(cx, cy - h * 0.24), QPointF(cx, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx + w * 0.20, cy + h * 0.12))
    elif name == "search":
        p.drawEllipse(QRectF(x + w * 0.12, y + h * 0.12, w * 0.56, h * 0.56))
        p.drawLine(QPointF(x + w * 0.62, y + h * 0.62), QPointF(x + w * 0.88, y + h * 0.88))
    elif name == "close":
        p.drawLine(QPointF(x + w * 0.28, y + h * 0.28), QPointF(x + w * 0.72, y + h * 0.72))
        p.drawLine(QPointF(x + w * 0.72, y + h * 0.28), QPointF(x + w * 0.28, y + h * 0.72))
    elif name == "min":
        p.drawLine(QPointF(x + w * 0.28, y + h * 0.55), QPointF(x + w * 0.72, y + h * 0.55))
    elif name == "max":
        p.drawRect(QRectF(x + w * 0.30, y + h * 0.30, w * 0.40, h * 0.40))
    elif name == "chevron":
        p.drawLine(QPointF(x + w * 0.38, y + h * 0.26), QPointF(x + w * 0.62, y + h * 0.50))
        p.drawLine(QPointF(x + w * 0.62, y + h * 0.50), QPointF(x + w * 0.38, y + h * 0.74))
    elif name == "alert":
        path = QPainterPath()
        path.moveTo(cx, y + h * 0.12)
        path.lineTo(x + w * 0.92, y + h * 0.84)
        path.lineTo(x + w * 0.08, y + h * 0.84)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(cx, y + h * 0.40), QPointF(cx, y + h * 0.60))
        p.drawPoint(QPointF(cx, y + h * 0.72))
    elif name == "check":
        p.drawLine(QPointF(x + w * 0.22, y + h * 0.52), QPointF(x + w * 0.42, y + h * 0.72))
        p.drawLine(QPointF(x + w * 0.42, y + h * 0.72), QPointF(x + w * 0.80, y + h * 0.30))
    elif name == "refresh":
        p.drawArc(QRectF(x + w * 0.14, y + h * 0.14, w * 0.72, h * 0.72), 40 * 16, 280 * 16)
        p.drawLine(QPointF(x + w * 0.72, y + h * 0.12), QPointF(x + w * 0.78, y + h * 0.34))
        p.drawLine(QPointF(x + w * 0.78, y + h * 0.34), QPointF(x + w * 0.56, y + h * 0.30))
    elif name == "layers":
        p.drawLine(QPointF(cx, y + h * 0.16), QPointF(x + w * 0.88, y + h * 0.40))
        p.drawLine(QPointF(x + w * 0.88, y + h * 0.40), QPointF(cx, y + h * 0.64))
        p.drawLine(QPointF(cx, y + h * 0.64), QPointF(x + w * 0.12, y + h * 0.40))
        p.drawLine(QPointF(x + w * 0.12, y + h * 0.40), QPointF(cx, y + h * 0.16))
        p.drawLine(QPointF(x + w * 0.12, y + h * 0.62), QPointF(cx, y + h * 0.84))
        p.drawLine(QPointF(cx, y + h * 0.84), QPointF(x + w * 0.88, y + h * 0.62))
    p.restore()


def icon_pixmap(name: str, size: int = 16, color: str = "#A9BFD2", ratio: float = 2.0) -> QPixmap:
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    paint_icon(p, name, QRectF(0, 0, size, size), QColor(color))
    p.end()
    return pm
