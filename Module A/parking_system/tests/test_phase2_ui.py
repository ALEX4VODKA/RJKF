import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt5.QtWidgets import QApplication, QWidget

from parking.anim.base import GateAnimator, RAISE
from parking.data import Database
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService
from parking.ui.exit_dialog import ExitDialog
from parking.ui.main_window import MainWindow
from parking.ui.scene_panel import ScenePanel


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


def _context(tmp_path):
    database = Database(tmp_path / "phase2-ui.sqlite3")
    database.initialize()
    auth = AuthService(database)
    admin = auth.bootstrap_admin("admin", "StrongPass123")
    return database, auth, admin, ParkingService(database, admin)


def test_exit_dialog_does_not_show_success_before_service_confirms(qt_app, tmp_path):
    _database, _auth, _admin, service = _context(tmp_path)
    entered = datetime.now().astimezone()
    service.enter_vehicle("陕A24680", "小型车", "blue", at=entered)
    bill = service.bill("陕A24680", at=entered + timedelta(hours=3))
    dialog = ExitDialog(bill)

    dialog._on_pay()

    assert dialog.pill.text() == "待缴费"
    assert dialog.btn_pay.text() == "处理中…"
    dialog.operation_failed("模拟写库失败")
    assert dialog.btn_pay.isEnabled()
    dialog.close()


def test_main_window_real_flow_registers_before_raise_and_exits_after_lower(
    qt_app, tmp_path
):
    database, auth, admin, service = _context(tmp_path)
    project_dir = os.path.dirname(os.path.dirname(__file__))
    window = MainWindow(
        service,
        os.path.join(project_dir, "resources", "anim"),
        "placeholder",
        user_session=admin,
        auth_service=auth,
    )

    window._on_entry("陕A13579", None, "blue", "小型车")
    with database.connect() as connection:
        stored = connection.execute(
            "SELECT entry_time, exit_time FROM parking_record WHERE plate_no = ?",
            ("陕A13579",),
        ).fetchone()
        assert stored is not None
        assert stored["exit_time"] is None

    window.scene._fallback_timer.stop()
    window.scene._on_finished("raise")
    window._on_lower()
    window.scene._fallback_timer.stop()
    window.scene._on_finished("lower")

    entered_at = datetime.fromisoformat(stored["entry_time"].replace("Z", "+00:00"))
    bill = service.bill("陕A13579", at=entered_at + timedelta(hours=3))
    window._after_pay(bill.plate, bill)
    assert service.present_vehicles()[0].status == "等待通过"

    window.scene._fallback_timer.stop()
    window.scene._on_finished("raise")
    window._on_lower()
    assert service.present_vehicles()[0].status == "等待落杆"
    window.scene._fallback_timer.stop()
    window.scene._on_finished("lower")

    assert service.present_vehicles() == []
    window._tick.stop()
    window._refresh.stop()
    window.close()


def test_scene_reload_retries_failed_gate_animation(qt_app, monkeypatch):
    created = []

    class FakeAnimator(GateAnimator):
        def __init__(self):
            super().__init__()
            self.widget = QWidget()
            self.triggered = []

        def surface(self):
            return self.widget

        def trigger(self, gate, direction):
            self.triggered.append((gate, direction))

        def stop(self):
            pass

        def mode_name(self):
            return "测试 3D"

    def fake_create(*_args, **_kwargs):
        animator = FakeAnimator()
        created.append(animator)
        return animator

    monkeypatch.setattr("parking.ui.scene_panel.create_animator", fake_create)
    panel = ScenePanel("unused", "auto")
    assert len(created) == 1

    panel.show()
    qt_app.processEvents()
    qt_app.processEvents()
    panel.raise_gate("in")
    created[0].failed.emit("模拟超时")

    assert panel.pill_in.text() == "入口 · 动画失败"
    assert panel._retry_operation == ("in", RAISE)

    panel._load()

    assert created[1].triggered == [("in", RAISE)]
    created[1].finished.emit(RAISE)
    assert panel.pill_in.text() == "入口 · 已抬起"
    assert panel._retry_operation is None
    panel.close()
