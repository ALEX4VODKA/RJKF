# -*- coding: utf-8 -*-
"""生成界面截图，用于自检和写文档。

用法：
    python tools/screenshot.py [输出目录]
不弹窗口（离屏渲染），生成 main.png 与 exit.png。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from PyQt5.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PyQt5.QtGui import QFontDatabase  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from parking.services.mock_service import MockService  # noqa: E402
from parking.ui import theme as T  # noqa: E402
from parking.ui.exit_dialog import ExitDialog  # noqa: E402
from parking.ui.main_window import MainWindow  # noqa: E402


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "docs")
    os.makedirs(out, exist_ok=True)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv[:1])
    # 离屏渲染时 Qt 找不到系统字体目录，显式加载界面用到的几款字体
    for name in ("msyh.ttc", "msyhbd.ttc", "bahnschrift.ttf", "consola.ttf"):
        path = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
    app.setStyle("Fusion")
    app.setStyleSheet(T.qss())

    svc = MockService()
    win = MainWindow(svc, os.path.join(BASE_DIR, "resources", "anim"), "auto")
    win.resize(1440, 900)
    win.show()
    app.processEvents()
    win.grab().save(os.path.join(out, "main.png"))
    print("saved", os.path.join(out, "main.png"))

    # 进场识别 + 抬杆完成
    win._on_entry()
    app.processEvents()
    loop = QEventLoop()
    QTimer.singleShot(1400, loop.quit)
    loop.exec_()
    app.processEvents()
    win.grab().save(os.path.join(out, "main_entry.png"))
    print("saved", os.path.join(out, "main_entry.png"))

    # 出场结算
    bill = svc.bill("陕A·3W8Q1")
    dlg = ExitDialog(bill, win)
    dlg.show()
    app.processEvents()
    dlg.grab().save(os.path.join(out, "exit.png"))
    print("saved", os.path.join(out, "exit.png"))

    # 缴费后的状态
    dlg._on_pay()
    app.processEvents()
    dlg.grab().save(os.path.join(out, "exit_paid.png"))
    print("saved", os.path.join(out, "exit_paid.png"))


if __name__ == "__main__":
    main()
