# -*- coding: utf-8 -*-
"""两门联动自测：进场走入口道闸、出场走出口道闸，互不串台。

用法： python tools/selftest_flow.py
不弹窗（离屏），打印每一步的断言结果。没有 WebEngine 时走模拟动画。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from PyQt5.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt5.QtGui import QFontDatabase  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from parking.services.mock_service import MockService  # noqa: E402
from parking.ui import theme as T  # noqa: E402
from parking.ui.main_window import MainWindow  # noqa: E402


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def wait(cond, timeout_ms=6000, step=100):
    waited = 0
    while waited < timeout_ms:
        if cond():
            return True
        spin(step)
        waited += step
    return False


def main():
    app = QApplication(sys.argv[:1])
    for name in ("msyh.ttc", "msyhbd.ttc", "bahnschrift.ttf", "consola.ttf"):
        path = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
    app.setStyle("Fusion")
    app.setStyleSheet(T.qss())

    svc = MockService()
    # 业务流程测试固定使用占位动画；实时 3D 由 selftest_webgl.py 单独验证。
    win = MainWindow(svc, os.path.join(BASE_DIR, "resources", "anim"), "placeholder")
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(("PASS  " if cond else "FAIL  ") + name)

    before = len(svc.present_vehicles())

    # 1) 进场：入口道闸动，出口不动
    win._on_entry()
    wait(lambda: "已抬起" in win.scene.pill_in.text())
    check("进场后在场车辆 +1", len(svc.present_vehicles()) == before + 1)
    check("入口道闸已抬起", "已抬起" in win.scene.pill_in.text())
    check("出口道闸仍待机", "待机" in win.scene.pill_out.text())
    check("落杆按钮已启用", win.btn_lower.isEnabled())

    # 2) 入口落杆
    win._on_lower()
    win.scene._on_stage("action")          # 模拟动画进入动作阶段
    check("落杆时提示为「落杆中」", "落杆中" in win.scene.pill_in.text())
    wait(lambda: "待机" in win.scene.pill_in.text())
    check("入口落杆完成", "待机" in win.scene.pill_in.text())

    # 3) 出场：出口道闸动
    plate = svc.present_vehicles()[0].plate
    bill = svc.bill(plate)
    win._after_pay(plate, bill)
    win._after_release(plate, "")
    wait(lambda: "已抬起" in win.scene.pill_out.text())
    check("出口道闸已抬起", "已抬起" in win.scene.pill_out.text())
    check("车辆已从在场列表移除", not any(v.plate == plate for v in svc.present_vehicles()))
    check("入口道闸未受影响", "待机" in win.scene.pill_in.text())

    win.scene.lower_gate("out")
    wait(lambda: "待机" in win.scene.pill_out.text())
    check("出口落杆完成", "待机" in win.scene.pill_out.text())

    failed = [n for n, ok in results if not ok]
    print("\nRESULT", "PASS" if not failed else f"FAIL ({len(failed)})")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
