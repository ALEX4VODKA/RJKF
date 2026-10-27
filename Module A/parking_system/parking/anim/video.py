# -*- coding: utf-8 -*-
"""MP4 实现：用 QtMultimedia 播放 Blender 导出的抬杆/落杆视频。

支持「镜头归位」前导片：
    gate_in_focus.mp4  → 收到抬杆信号时先播它（镜头从全景飞到摄像机位）
    播完自动接 gate_in_up.mp4，两段之间无缝，不需要人工切换。
"""
import os

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QSizePolicy

from ..ui import theme as T
from .base import LOWER, RAISE, GateAnimator

try:
    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
    from PyQt5.QtMultimediaWidgets import QVideoWidget
    HAS_QTMM = True
except Exception:  # pragma: no cover - 缺少多媒体模块时由工厂降级
    HAS_QTMM = False


class VideoAnimator(GateAnimator):
    def __init__(self, up_file: str, down_file: str, focus_file: str = None, parent=None):
        super().__init__(parent)
        self._files = {RAISE: up_file, LOWER: down_file}
        self._focus_file = focus_file if focus_file and os.path.exists(focus_file) else None
        self._direction = None
        self._stage = "action"
        self._busy = False

        self._w = QVideoWidget()
        self._w.setStyleSheet(f"background:{T.BG0};")
        self._w.setAspectRatioMode(Qt.KeepAspectRatioByExpanding)
        self._w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self._player.setVideoOutput(self._w)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.error.connect(self._on_error)

    # ------------------------------------------------------------------
    def surface(self):
        return self._w

    def has_prelude(self) -> bool:
        return bool(self._focus_file)

    def play(self, direction: str):
        if self._focus_file and direction == RAISE:
            self._stage = "focus"
            self._direction = direction
            self._busy = True
            self._start(self._focus_file)
            self.stage.emit("focus")
            self.started.emit(direction)
            return

        self._stage = "action"
        self._direction = direction
        path = self._files.get(direction)
        if not path or not os.path.exists(path):
            self.failed.emit(f"找不到动画文件：{path}")
            return
        self._busy = True
        self._start(path)
        self.stage.emit("action")
        self.started.emit(direction)

    def _start(self, path: str):
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(path))))
        self._player.play()

    def _on_status(self, status):
        if status != QMediaPlayer.EndOfMedia:
            return

        # 前导片播完 → 立刻接抬杆动作
        if self._stage == "focus":
            self._player.pause()
            self._stage = "action"
            path = self._files.get(RAISE)
            if path and os.path.exists(path):
                self._start(path)
                self.stage.emit("action")
                return
            self._busy = False
            self.finished.emit(RAISE)
            return

        self._player.pause()          # 停在最后一帧，闸杆保持抬起
        if self._busy:
            self._busy = False
            self.finished.emit(self._direction)

    def _on_error(self, *_args):
        if self._busy:
            self._busy = False
            self.failed.emit("视频解码失败，请改用序列帧或占位模式")

    def stop(self):
        self._player.stop()
        self._busy = False
        self._stage = "action"

    def is_busy(self) -> bool:
        return self._busy

    def mode_name(self) -> str:
        return "MP4 动画"

    def describe(self) -> str:
        base = os.path.basename(self._files.get(RAISE, ""))
        return base + ("（含镜头归位）" if self._focus_file else "")
