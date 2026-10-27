# -*- coding: utf-8 -*-
"""整界面 3D 自检：启动主窗口，确认 3D 场景就绪，并截取三张画面。

用法（用装了 PyQtWebEngine 的 Python 执行）：
    python tools/selftest_webgl.py [输出目录]

成功时打印 "WEBGL PASS"，生成 webgl_wide.png / webgl_in.png / webgl_lower.png。
无 GPU 的环境可先设 QTWEBENGINE_CHROMIUM_FLAGS="--use-gl=swiftshader"。
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from PyQt5.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

from parking.services.mock_service import MockService  # noqa: E402
from parking.ui import theme as T  # noqa: E402
from parking.ui.main_window import MainWindow  # noqa: E402


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def wait_ready(anim, timeout_ms=25000):
    waited = 0
    while waited < timeout_ms:
        if getattr(anim, "_ready", False):
            return True
        spin(200)
        waited += 200
    return False


def snapshot(anim, path):
    box = {}

    loop = QEventLoop()

    def done(data):
        box["data"] = data
        loop.quit()

    anim.snapshot(done)
    QTimer.singleShot(5000, loop.quit)
    loop.exec_()
    data = box.get("data")
    if not data:
        print(f"[snapshot] 空：{path}")
        return False
    open(path, "wb").write(data)
    print(f"[snapshot] {path} ({len(data) // 1024} KB)")
    return True


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "docs")
    os.makedirs(out, exist_ok=True)

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet(T.qss())

    win = MainWindow(MockService(), os.path.join(BASE_DIR, "resources", "anim"), "webgl")
    win.resize(1440, 900)
    # WebEngine 窗口移出可见屏幕后可能不分配可截图的绘制表面。
    win.move(40, 40)
    win.show()
    spin(400)

    anim = win.scene._animator
    ready = wait_ready(anim)
    print(f"[scene] animator={type(anim).__name__} ready={ready} "
          f"mode={getattr(anim, '_mode', '-')}")
    if not ready:
        print("WEBGL FAIL（3D 未就绪，检查 PyQtWebEngine / 显卡）")
        return 1

    ok = snapshot(anim, os.path.join(out, "webgl_wide.png"))
    if not ok:
        print("WEBGL FAIL")
        return 1

    win._on_entry()
    spin(1600)
    print("[state]", win.scene.pill_in.text(), "|", win.scene.state_label.text())
    ok &= snapshot(anim, os.path.join(out, "webgl_in.png"))
    spin(1800)

    win._on_lower()
    spin(900)
    print("[state]", win.scene.pill_in.text(), "|", win.scene.state_label.text())
    ok &= snapshot(anim, os.path.join(out, "webgl_lower.png"))

    print("WEBGL", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
