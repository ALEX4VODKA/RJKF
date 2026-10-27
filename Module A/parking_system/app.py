# -*- coding: utf-8 -*-
"""程序入口：初始化主题、创建主窗口。

运行： python app.py
可选环境变量：ANIM_MODE=auto|webgl|video|sequence|placeholder
"""
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from parking.services.mock_service import MockService
from parking.ui import theme as T
from parking.ui.main_window import MainWindow
from parking.ui.widgets import brand_pixmap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANIM_DIR = os.path.join(BASE_DIR, "resources", "anim")


def _app_icon() -> QIcon:
    return QIcon(brand_pixmap(64))


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # QtWebEngine 要求：必须在 QApplication 创建前开启共享 GL 上下文
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("智慧停车 · 出入口控制台")
    app.setStyle("Fusion")
    app.setStyleSheet(T.qss())
    app.setWindowIcon(_app_icon())

    win = MainWindow(MockService(), ANIM_DIR, os.environ.get("ANIM_MODE", "auto"))
    win.setWindowIcon(_app_icon())
    win.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
