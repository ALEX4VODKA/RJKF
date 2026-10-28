# -*- coding: utf-8 -*-
"""程序入口：初始化主题、创建主窗口。

运行： python app.py
可选环境变量：ANIM_MODE=auto|webgl|video|sequence|placeholder
"""
import os
import sys
from pathlib import Path

# Windows 上必须在 PyQt5 的原生 DLL 之前加载 ONNX Runtime，否则
# HyperLPR3 首次推理可能报 DLL 初始化失败。
import onnxruntime as _onnxruntime  # noqa: F401

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from parking.config import RuntimePaths
from parking.data import Database
from parking.recognition import LicenseRecognizer
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService
from parking.services.rule_service import RuleService
from parking.ui import theme as T
from parking.ui.auth_dialog import AuthDialog
from parking.ui.main_window import MainWindow
from parking.ui.widgets import brand_pixmap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANIM_DIR = os.path.join(BASE_DIR, "resources", "anim")


def _app_icon() -> QIcon:
    return QIcon(brand_pixmap(64))


def main():
    runtime_paths = RuntimePaths.from_environment(Path(BASE_DIR))
    runtime_paths.ensure_directories()
    database = Database(runtime_paths.database)
    database_existed = runtime_paths.database.exists()
    database.initialize()
    if database_existed:
        database.backup_daily(runtime_paths.backups)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # QtWebEngine 要求：必须在 QApplication 创建前开启共享 GL 上下文
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("智慧停车 · 出入口控制台")
    app.setStyle("Fusion")
    app.setStyleSheet(T.qss())
    app.setWindowIcon(_app_icon())

    auth_service = AuthService(database)
    auth_dialog = AuthDialog(auth_service, bootstrap=not auth_service.has_accounts())
    if auth_dialog.exec_() != AuthDialog.Accepted or auth_dialog.session is None:
        return 0
    if not database_existed:
        database.backup_daily(runtime_paths.backups)

    win = MainWindow(
        ParkingService(database, auth_dialog.session),
        ANIM_DIR,
        os.environ.get("ANIM_MODE", "auto"),
        rule_service=RuleService(database),
        user_session=auth_dialog.session,
        auth_service=auth_service,
        recognizer=LicenseRecognizer(
            runtime_paths.root,
            threshold=float(os.environ.get("PARKING_RECOGNITION_THRESHOLD", "0.80")),
            max_attempts=int(os.environ.get("PARKING_RECOGNITION_ATTEMPTS", "3")),
        ),
    )
    win.setWindowIcon(_app_icon())
    win.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
