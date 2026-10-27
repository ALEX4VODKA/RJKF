# -*- coding: utf-8 -*-
"""道闸动画接口：业务只依赖这个类，具体实现可以换成 MP4、序列帧或占位。"""
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget

RAISE = "raise"
LOWER = "lower"


class GateAnimator(QObject):
    """所有动画实现的统一接口。

    信号：
        started(direction)   开始播放
        finished(direction)  播放结束（抬杆到位 / 落杆到位）
        failed(reason)       资源缺失或解码失败
    """

    started = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    stage = pyqtSignal(str)      # "focus" 镜头归位中 / "action" 正在播放动作
    meta_changed = pyqtSignal()  # 资源状态变化（例如 WebGL 模型加载完成）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shared = False

    # 是否共用了旧的单文件资源（两个道闸播同一段动画）
    def set_shared(self, value: bool = True):
        self._shared = value

    def is_shared(self) -> bool:
        return self._shared

    def surface(self) -> QWidget:
        """返回用于嵌入界面的显示控件。"""
        raise NotImplementedError

    def play(self, direction: str):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def is_busy(self) -> bool:
        return False

    def mode_name(self) -> str:
        return "未知"

    def describe(self) -> str:
        """给界面显示的资源说明。"""
        return ""
