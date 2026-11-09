# -*- coding: utf-8 -*-
"""程序入口：初始化主题、创建主窗口。

运行： python app.py
可选环境变量：ANIM_MODE=auto|webgl|video|sequence|placeholder
"""
import os
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path

# Windows 上必须在 PyQt5 的原生 DLL 之前加载 ONNX Runtime，否则
# HyperLPR3 首次推理可能报 DLL 初始化失败。
import onnxruntime as _onnxruntime  # noqa: F401

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from parking.config import RuntimePaths, application_directory
from parking.data import Database
from parking.defense_demo import (
    default_defense_path,
    install_packaged_demo,
    packaged_template_path,
    prepare_defense_demo,
)
from parking.recognition import LicenseRecognizer
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService
from parking.services.report_service import ReportService
from parking.services.rule_service import RuleService
from parking.ui import theme as T
from parking.ui.auth_dialog import AuthDialog
from parking.ui.defense_demo_dialog import DefenseDemoDialog
from parking.ui.main_window import MainWindow
from parking.ui.widgets import brand_pixmap

RESOURCE_DIR = Path(__file__).resolve().parent
BASE_DIR = str(RESOURCE_DIR)
ANIM_DIR = str(RESOURCE_DIR / "resources" / "anim")


def _application_dir() -> Path:
    """返回可写的程序目录；打包后是 exe 所在目录。"""
    return application_directory(RESOURCE_DIR)


def _runtime_paths() -> RuntimePaths:
    paths = RuntimePaths.from_environment(_application_dir())
    paths.ensure_directories()
    # QtWebEngine 的缓存必须放在可写目录，不能落入 PyInstaller 的 _internal。
    os.environ.setdefault("PARKING_WEBENGINE_DIR", str(paths.root / ".webengine"))
    return paths


def _app_icon() -> QIcon:
    return QIcon(brand_pixmap(64))


def _defense_mode_enabled() -> bool:
    return "--defense-mode" in sys.argv or os.environ.get("PARKING_DEFENSE_MODE") == "1"


def _configure_defense_runtime() -> None:
    """为源码或便携包准备隔离演示库与共享离线模型。"""
    if not _defense_mode_enabled() or os.environ.get("PARKING_DATA_DIR"):
        return
    application_dir = _application_dir()
    target = default_defense_path(application_dir)
    template = packaged_template_path(application_dir)
    if template.is_file():
        install_packaged_demo(template, target)
    else:
        prepare_defense_demo(application_dir, output=target)
    os.environ["PARKING_DATA_DIR"] = str(target.parent)
    model_home = application_dir / "runtime" / ".hyperlpr3"
    if model_home.is_dir():
        os.environ.setdefault("PARKING_RECOGNITION_MODEL_DIR", str(model_home))


def verify_installation() -> int:
    """无界面验证打包资源、QtWebEngine 与离线识别模型。"""
    runtime_paths = _runtime_paths()
    report_path = runtime_paths.root / "package-verification.json"
    report = {
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "failed",
        "application_dir": str(_application_dir()),
        "resource_dir": str(RESOURCE_DIR),
    }
    try:
        required_assets = (
            RESOURCE_DIR / "viewer" / "index.html",
            RESOURCE_DIR / "viewer" / "lib" / "three.min.js",
            RESOURCE_DIR / "viewer" / "lib" / "GLTFLoader.js",
            RESOURCE_DIR / "resources" / "model" / "parking.glb",
        )
        missing = [str(path) for path in required_assets if not path.is_file()]
        if missing:
            raise RuntimeError("缺少打包资源：" + "；".join(missing))

        from parking.anim.webgl import HAS_WEBENGINE

        if not HAS_WEBENGINE:
            raise RuntimeError("PyQtWebEngine 未能加载")
        LicenseRecognizer(runtime_paths.root).prepare()
        report.update(
            status="ok",
            webengine=True,
            recognition_model="ready",
        )
        exit_code = 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        exit_code = 1

    try:
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return exit_code


def _record_startup_error() -> None:
    """窗口版无法输出 stderr 时，把未处理异常留在可写运行目录。"""
    try:
        paths = _runtime_paths()
        (paths.root / "startup-error.log").write_text(
            f"{datetime.now().astimezone().isoformat(timespec='seconds')}\n"
            f"{traceback.format_exc()}",
            encoding="utf-8",
        )
    except OSError:
        pass


def main():
    _configure_defense_runtime()
    runtime_paths = _runtime_paths()
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
        report_service=ReportService(database),
        defense_mode=_defense_mode_enabled(),
    )
    win.setWindowIcon(_app_icon())
    win.show()
    if _defense_mode_enabled():
        win._defense_guide = DefenseDemoDialog(win)
        win._defense_guide.show()

    return app.exec_()


if __name__ == "__main__":
    if "--verify-installation" in sys.argv:
        sys.exit(verify_installation())
    try:
        sys.exit(main())
    except Exception:
        _record_startup_error()
        raise
