# -*- coding: utf-8 -*-
"""序列帧实现：把 Blender 渲染的 PNG 序列按固定帧率播放，兼容性最好。"""
import os

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy

from ..ui import theme as T
from .base import LOWER, RAISE, GateAnimator

_EXTS = (".png", ".jpg", ".jpeg")


def _frames_in(directory: str):
    if not os.path.isdir(directory):
        return []
    names = [n for n in os.listdir(directory) if n.lower().endswith(_EXTS)]
    names.sort()
    return [os.path.join(directory, n) for n in names]


class SequenceAnimator(GateAnimator):
    def __init__(self, up_dir: str, down_dir: str, fps: int = 30,
                 focus_dir: str = None, parent=None):
        super().__init__(parent)
        self._frames = {RAISE: _frames_in(up_dir), LOWER: _frames_in(down_dir)}
        self._dirs = {RAISE: up_dir, LOWER: down_dir}
        self._focus = _frames_in(focus_dir) if focus_dir else []
        self._boundary = 0
        self._stage = "action"
        self._fps = max(8, fps)
        self._index = 0
        self._direction = None
        self._busy = False

        self._w = QLabel()
        self._w.setAlignment(Qt.AlignCenter)
        self._w.setStyleSheet(f"background:{T.BG0};")
        self._w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._w.setScaledContents(False)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next)

        self._cache = {}

    # ------------------------------------------------------------------
    def surface(self):
        return self._w

    def has_prelude(self) -> bool:
        return bool(self._focus)

    def play(self, direction: str):
        action_frames = self._frames.get(direction) or []
        if not action_frames:
            self.failed.emit(f"序列帧为空：{self._dirs.get(direction)}")
            return

        # 抬杆前先播「镜头归位」帧
        if direction == RAISE and self._focus:
            self._playlist = self._focus + action_frames
            self._boundary = len(self._focus)
            self._stage = "focus"
        else:
            self._playlist = action_frames
            self._boundary = 0
            self._stage = "action"

        self._direction = direction
        self._index = 0
        self._busy = True
        self.stage.emit(self._stage)
        self.started.emit(direction)
        self._show(self._playlist[0])
        self._timer.start(max(10, int(1000 / self._fps)))

    def _show(self, path: str):
        pm = self._cache.get(path)
        if pm is None:
            pm = QPixmap(path)
            self._cache[path] = pm
        if pm.isNull():
            return
        target = self._w.size()
        self._w.setPixmap(pm.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def _next(self):
        self._index += 1
        if self._stage == "focus" and self._index >= self._boundary:
            self._stage = "action"
            self.stage.emit("action")
        if self._index >= len(self._playlist):
            self._timer.stop()
            self._busy = False
            self.finished.emit(self._direction)
            return
        self._show(self._playlist[self._index])

    def stop(self):
        self._timer.stop()
        self._busy = False

    def is_busy(self) -> bool:
        return self._busy

    def mode_name(self) -> str:
        return "序列帧"

    def describe(self) -> str:
        n = len(self._frames.get(RAISE) or [])
        extra = f" + 归位 {len(self._focus)} 帧" if self._focus else ""
        return f"{n} 帧 / {self._fps} fps{extra}"
