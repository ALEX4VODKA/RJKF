# -*- coding: utf-8 -*-
"""3D 视图单测：只验证 viewer（three.js）本身，不经过主窗口。

检查：
    1. 页面加载 + WebChannel 桥接成功
    2. 没有 parking.glb 时自动搭演示场景
    3. trigger('in','open') 依次收到 focus / action / finished
    4. 能截出非空的 3D 画面

用法（需要装了 PyQtWebEngine 的 Python）：
    python tools/viewer_test.py [输出目录]
"""
import json
import os
import sys

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--single-process --no-sandbox --use-gl=swiftshader --disable-crash-reporter")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from PyQt5.QtCore import QEventLoop, Qt, QTimer, QUrl  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

from PyQt5.QtWebChannel import QWebChannel  # noqa: E402
from PyQt5.QtWebEngineWidgets import (  # noqa: E402
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineView,
)

from parking.anim.webgl import _AssetServer, _Bridge  # noqa: E402


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def eval_js(page, script, timeout_ms=3000):
    """等待一次 JavaScript 回调，避免固定 sleep 在模型较大时产生误判。"""
    loop = QEventLoop()
    result = {"done": False, "value": None}

    def finished(value):
        result["done"] = True
        result["value"] = value
        loop.quit()

    page.runJavaScript(script, finished)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec_()
    return result["value"] if result["done"] else None


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        if level >= 2:
            print(f"[js] {message} ({os.path.basename(source)}:{line})")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "docs")
    size = sys.argv[2] if len(sys.argv) > 2 else "960x540"
    vw, vh = (int(x) for x in size.lower().split("x"))
    os.makedirs(out, exist_ok=True)

    app = QApplication(sys.argv[:1])

    profile = QWebEngineProfile("parking-viewer-test", app)
    base = os.path.join(BASE_DIR, ".webengine")
    os.makedirs(base, exist_ok=True)
    profile.setCachePath(os.path.join(base, "cache"))
    profile.setPersistentStoragePath(os.path.join(base, "data"))

    server = _AssetServer.get(BASE_DIR)
    url = QUrl(f"http://127.0.0.1:{server.port}/viewer/index.html")

    view = QWebEngineView()
    page = Page(profile, view)
    view.setPage(page)
    s = view.settings()
    s.setAttribute(QWebEngineSettings.WebGLEnabled, True)

    events = []
    bridge = _Bridge()
    bridge.ready.connect(lambda m: events.append(("ready", m)))
    bridge.stage_changed.connect(lambda g, st: events.append(("stage", g, st)))
    bridge.anim_finished.connect(lambda g, a: events.append(("finished", g, a)))
    bridge.error.connect(lambda m: events.append(("error", m)))

    channel = QWebChannel(page)
    channel.registerObject("bridge", bridge)
    page.setWebChannel(channel)

    view.resize(vw, vh)
    view.load(url)
    view.show()

    ok = True
    waited = 0
    while waited < 20000 and not any(e[0] == "ready" for e in events):
        spin(200)
        waited += 200
    ready = [e for e in events if e[0] == "ready"]
    print("ready:", ready)
    ok &= bool(ready)

    if ok:
        metrics_value = eval_js(
            page,
            "JSON.stringify((function(){"
            "var c=document.querySelector('canvas'),r=c.getBoundingClientRect();"
            "return {innerWidth:window.innerWidth,innerHeight:window.innerHeight,"
            "dpr:window.devicePixelRatio,rectWidth:r.width,rectHeight:r.height,"
            "bufferWidth:c.width,bufferHeight:c.height};})())"
        )
        layout = json.loads(metrics_value or "{}")
        print("layout:", layout)
        ok &= abs(layout.get("rectWidth", 0) - layout.get("innerWidth", -10)) <= 2
        ok &= abs(layout.get("rectHeight", 0) - layout.get("innerHeight", -10)) <= 2
        expected_w = layout.get("innerWidth", 0) * min(layout.get("dpr", 1), 2)
        expected_h = layout.get("innerHeight", 0) * min(layout.get("dpr", 1), 2)
        ok &= abs(layout.get("bufferWidth", 0) - expected_w) <= 2
        ok &= abs(layout.get("bufferHeight", 0) - expected_h) <= 2

        # 触发入口抬杆
        page.runJavaScript("DSHParking.trigger('in','open')")
        waited = 0
        while waited < 8000 and not any(e[0] == "finished" for e in events):
            spin(200)
            waited += 200
        print("events:", events)
        ok &= ("stage", "in", "focus") in events
        ok &= ("stage", "in", "action") in events
        ok &= ("finished", "in", "open") in events

        url_data = eval_js(page, "DSHParking.snapshot()", 5000) or ""
        if "," in url_data:
            import base64
            raw = base64.b64decode(url_data.split(",", 1)[1])
            path = os.path.join(out, f"webgl_scene_{vw}x{vh}.png")
            open(path, "wb").write(raw)
            print(f"snapshot -> {path} ({len(raw)//1024} KB)")
            ok &= len(raw) > 8000
        else:
            print("snapshot empty")
            ok = False

        # canvas.toDataURL 会截取完整绘图缓冲区；额外截取实际控件，防止高 DPI
        # 下 canvas 的 CSS 尺寸被放大后在 QWebEngineView 内发生裁切。
        view_path = os.path.join(out, f"webgl_view_{vw}x{vh}.png")
        grabbed = view.grab()
        saved = grabbed.save(view_path, "PNG")
        print(f"view -> {view_path} ({grabbed.width()}x{grabbed.height()})")
        ok &= saved and grabbed.width() > 0 and grabbed.height() > 0

    print("VIEWER", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
