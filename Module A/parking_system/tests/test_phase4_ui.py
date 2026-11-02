import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt5.QtWidgets import QApplication

from parking.data import Database
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService
from parking.services.report_service import ReportService
from parking.ui.main_window import MainWindow
from parking.ui.report_dialog import ReportDialog


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


def test_admin_main_window_and_report_dialog_expose_phase4_controls(qt_app, tmp_path):
    database = Database(tmp_path / "phase4-ui.sqlite3")
    database.initialize()
    admin = AuthService(database).bootstrap_admin("admin", "StrongPass123")
    parking = ParkingService(database, admin)
    reports = ReportService(database)
    project_dir = os.path.dirname(os.path.dirname(__file__))
    window = MainWindow(
        parking,
        os.path.join(project_dir, "resources", "anim"),
        "placeholder",
        user_session=admin,
        report_service=reports,
    )
    assert window.btn_reports.text() == "统计报表"

    dialog = ReportDialog(reports, admin, window)
    assert dialog.table.columnCount() == 6
    assert dialog.result.vehicle_count == 0
    assert dialog.btn_open.isEnabled() is False
    dialog.close()
    window._tick.stop()
    window._refresh.stop()
    window.close()
