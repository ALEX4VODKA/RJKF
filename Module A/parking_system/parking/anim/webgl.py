# -*- coding: utf-8 -*-
"""实时 3D 实现：QtWebEngine 里跑 three.js，加载 Blender 导出的 glTF。

工作方式：
    信号 → 镜头飞到该道闸的机位（focus）→ 播放对应动画（action）→ 播完回调

资源约定（都放在 resources/model/ 下）：
    parking.glb                       Blender 导出的场景（glTF 2.0 二进制）
    动画名  gate_in_open / gate_in_close / gate_out_open / gate_out_close
    机位空物体 cam_in / cam_out / cam_wide（可选，没有就自动取景）

没有 glb 时，viewer 会自动搭一个演示场景（立柱 + 闸杆），
所以前面几天不导出模型也能先看效果。
"""
import base64
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PyQt5.QtCore import QObject, QTimer, QUrl, pyqtSignal, pyqtSlot

from .base import LOWER, RAISE, GateAnimator

try:
    from PyQt5.QtWebChannel import QWebChannel
    from PyQt5.QtWebEngineWidgets import (
        QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineView,
    )
    HAS_WEBENGINE = True
except Exception:  # pragma: no cover - 没装 WebEngine 时由工厂降级
    HAS_WEBENGINE = False
    QWebEngineView = object
    QWebEnginePage = QWebEngineProfile = object


if HAS_WEBENGINE:
    class _WebGLView(QWebEngineView):
        """只在控件获得真实绘制表面后通知加载页面。"""

        first_visible = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._first_visible_emitted = False
            self._show_scheduled = False

        def showEvent(self, event):
            super().showEvent(event)
            if not self._first_visible_emitted and not self._show_scheduled:
                self._show_scheduled = True
                QTimer.singleShot(0, self._emit_first_visible)

        def _emit_first_visible(self):
            self._show_scheduled = False
            if self.isVisible() and not self._first_visible_emitted:
                self._first_visible_emitted = True
                self.first_visible.emit()
else:  # pragma: no cover - 仅用于缺少 PyQtWebEngine 的降级环境
    _WebGLView = object


# ------------------------------------------------------------------ 本地静态服务
class _QuietHandler(SimpleHTTPRequestHandler):
    """只服务 parking_system 目录，不打印访问日志。"""

    def log_message(self, *_args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class _AssetServer:
    """127.0.0.1 上的临时静态服务器，给 WebEngine 提供 http:// 源。

    file:// 下 Chromium 不允许 XHR 读取本地 glb，所以起一个只监听回环地址的
    小服务；进程退出即消失，不对外开放。
    """

    _lock = threading.Lock()
    _instance = None

    def __init__(self, root: str):
        handler = partial(_QuietHandler, directory=root)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.root = root
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @classmethod
    def get(cls, root: str):
        with cls._lock:
            if cls._instance is None or cls._instance.root != root:
                cls._instance = cls(root)
            return cls._instance


# ------------------------------------------------------------------ 浏览器配置
_profile_instance = None


def _profile(app_root: str):
    """独立的 WebEngine 配置，缓存与数据都放在工程目录下。

    默认配置会写到 %LOCALAPPDATA%，在受限环境里会创建失败；
    指定路径后行为可预测，也方便打包时一起清理。
    """
    global _profile_instance
    if _profile_instance is not None:
        return _profile_instance

    from PyQt5.QtWidgets import QApplication
    profile = QWebEngineProfile("parking-viewer", QApplication.instance())
    base = os.path.join(app_root, ".webengine")
    os.makedirs(base, exist_ok=True)
    profile.setCachePath(os.path.join(base, "cache"))
    profile.setPersistentStoragePath(os.path.join(base, "data"))
    try:
        profile.setHttpCacheType(QWebEngineProfile.NoCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
    except Exception:
        pass
    _profile_instance = profile
    return profile


# ------------------------------------------------------------------ 桥
class _Bridge(QObject):
    ready = pyqtSignal(str)
    stage_changed = pyqtSignal(str, str)
    anim_finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    @pyqtSlot(str)
    def onReady(self, mode):
        self.ready.emit(mode)

    @pyqtSlot(str, str)
    def onStage(self, gate, stage):
        self.stage_changed.emit(gate, stage)

    @pyqtSlot(str, str)
    def onFinished(self, gate, action):
        self.anim_finished.emit(gate, action)

    @pyqtSlot(str)
    def onError(self, message):
        self.error.emit(message)


# ------------------------------------------------------------------ 实现
class WebGLAnimator(GateAnimator):
    GATE_ACTION = {RAISE: "open", LOWER: "close"}

    def __init__(self, app_root: str, gate: str = "in", parent=None):
        super().__init__(parent)
        self._gate = gate
        self._ready = False
        self._pending = None
        self._busy = False
        self._direction = None
        self._load_started = False

        server = _AssetServer.get(app_root)
        self._url = QUrl(f"http://127.0.0.1:{server.port}/viewer/index.html")

        self._view = _WebGLView()
        self._view.setMinimumSize(160, 90)
        self._page = QWebEnginePage(_profile(app_root), self._view)
        self._view.setPage(self._page)
        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)

        self._channel = QWebChannel(self._page)
        self._bridge = _Bridge()
        self._channel.registerObject("bridge", self._bridge)
        self._page.setWebChannel(self._channel)

        self._bridge.ready.connect(self._on_ready)
        self._bridge.stage_changed.connect(self._on_stage)
        self._bridge.anim_finished.connect(self._on_finished)
        self._bridge.error.connect(lambda msg: (self._init_timer.stop(), self.failed.emit(msg)))

        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_timeout)

        # 初始化保护：10 秒还没 ready（浏览器未起来 / WebGL 不可用）就让上层降级
        self._init_timer = QTimer(self)
        self._init_timer.setSingleShot(True)
        self._init_timer.timeout.connect(self._on_init_timeout)
        self._view.first_visible.connect(self._start_load)

    # ------------------------------------------------------------------
    def surface(self):
        return self._view

    def trigger(self, gate: str, direction: str):
        """指定道闸抬杆 / 落杆：镜头先飞到该门机位，再播动画。"""
        action = self.GATE_ACTION.get(direction)
        if action is None:
            return
        self._gate = gate
        self.play(direction)

    def play(self, direction: str):
        action = self.GATE_ACTION.get(direction)
        if action is None:
            return
        self._direction = direction
        if not self._ready:
            self._pending = (direction, action)
            return
        self._busy = True
        self.stage.emit("focus")
        self.started.emit(direction)
        self._call(f"DSHParking.trigger('{self._gate}','{action}')")
        self._watchdog.start(8000)

    def _call(self, js: str):
        self._page.runJavaScript(js)

    def _start_load(self):
        if self._load_started:
            return
        self._load_started = True
        self._init_timer.start(30000)
        self._view.load(self._url)

    # ------------------------------------------------------------------
    def _on_init_timeout(self):
        if not self._ready:
            self.failed.emit("3D 初始化超时（浏览器未就绪或 WebGL 不可用）")

    def _on_ready(self, mode: str):
        self._init_timer.stop()
        self._ready = True
        self._mode = mode
        # 页面可能在控件刚显示时完成加载；主动同步一次真实视口，避免首帧沿用
        # 隐藏阶段的默认尺寸，表现为首次空白、手动刷新后才正常。
        self._call("window.dispatchEvent(new Event('resize'))")
        self._view.update()
        self.meta_changed.emit()
        if self._pending:
            direction, action = self._pending
            self._pending = None
            self._busy = True
            self.stage.emit("focus")
            self.started.emit(direction)
            self._call(f"DSHParking.trigger('{self._gate}','{action}')")
            self._watchdog.start(8000)

    def _on_stage(self, _gate: str, stage: str):
        self.stage.emit(stage)

    def _on_finished(self, _gate: str, _action: str):
        self._watchdog.stop()
        self._busy = False
        if self._direction:
            self.finished.emit(self._direction)
            self._direction = None

    def _on_timeout(self):
        if self._busy:
            self._busy = False
            self.failed.emit("3D 动画超时（浏览器未回调）")

    def stop(self):
        self._init_timer.stop()
        self._watchdog.stop()
        self._busy = False
        self._pending = None

    def is_busy(self) -> bool:
        return self._busy

    def mode_name(self) -> str:
        return "实时 3D" if getattr(self, "_mode", "demo") == "model" else "实时 3D · 演示模型"

    def describe(self) -> str:
        return "three.js / WebGL" if self._ready else "正在加载 3D…"

    # ------------------------------------------------------------------
    def snapshot(self, callback):
        """截一张 3D 画面（dataURL → PNG 字节），用于文档和自检。"""
        def done(data_url):
            if not data_url or "," not in str(data_url):
                callback(None)
                return
            payload = str(data_url).split(",", 1)[1]
            callback(base64.b64decode(payload))

        self._page.runJavaScript("DSHParking.snapshot()", done)
