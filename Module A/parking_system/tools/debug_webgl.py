# -*- coding: utf-8 -*-
"""WebEngine 调试：打开 viewer，打印加载状态与 JS 报错。"""
import os
import sys

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--single-process --no-sandbox --disable-gpu --disable-gpu-compositing")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from PyQt5.QtCore import QEventLoop, Qt, QTimer, QUrl  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

from PyQt5.QtWebChannel import QWebChannel  # noqa: E402
from PyQt5.QtWebEngineWidgets import (  # noqa: E402
    QWebEnginePage, QWebEngineProfile, QWebEngineView,
)

from parking.anim.webgl import _AssetServer, _Bridge  # noqa: E402


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[js:{level}] {message}  ({os.path.basename(source)}:{line})")


def main():
    app = QApplication(sys.argv[:1])

    server = _AssetServer.get(BASE_DIR)
    url = QUrl(f"http://127.0.0.1:{server.port}/viewer/index.html")
    print("url =", url.toString())

    profile = QWebEngineProfile("parking-debug", app)
    base = os.path.join(BASE_DIR, ".webengine")
    os.makedirs(base, exist_ok=True)
    profile.setCachePath(os.path.join(base, "cache"))
    profile.setPersistentStoragePath(os.path.join(base, "data"))

    view = QWebEngineView()
    page = Page(profile, view)
    view.setPage(page)

    channel = QWebChannel(page)
    bridge = _Bridge()
    channel.registerObject("bridge", bridge)
    page.setWebChannel(channel)
    bridge.ready.connect(lambda m: print("[bridge] ready:", m))
    bridge.error.connect(lambda m: print("[bridge] error:", m))

    page.loadFinished.connect(lambda ok: print("[load] finished:", ok))
    view.load(url)
    view.resize(960, 540)
    view.show()
    spin(6000)

    for js in ("document.title", "typeof THREE", "typeof DSHParking",
               "document.getElementById('loading').textContent"):
        out = {}
        page.runJavaScript(js, lambda v, out=out: out.setdefault("v", v))
        spin(250)
        print(f"  {js} = {out.get('v')!r}")

    print("done")


if __name__ == "__main__":
    main()
