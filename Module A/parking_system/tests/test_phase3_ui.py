import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt5.QtWidgets import QApplication, QDialog, QInputDialog

from parking.data import Database
from parking.recognition import PlateCandidate, RecognitionResult
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService
from parking.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


def test_recognition_result_drives_entry_and_exit_and_persists_photos(
    qt_app, tmp_path, monkeypatch
):
    database = Database(tmp_path / "phase3-ui.sqlite3")
    database.initialize()
    auth = AuthService(database)
    admin = auth.bootstrap_admin("admin", "StrongPass123")
    service = ParkingService(database, admin)
    project_dir = os.path.dirname(os.path.dirname(__file__))
    window = MainWindow(
        service,
        os.path.join(project_dir, "resources", "anim"),
        "placeholder",
        user_session=admin,
        auth_service=auth,
        recognizer=object(),
    )

    entry = RecognitionResult(
        plate="陕B99999",
        confidence=0.96,
        kind="yellow",
        box=(10, 20, 100, 60),
        photo_path="entry-capture.jpg",
        frame_index=0,
        elapsed_ms=120,
        candidates=(
            PlateCandidate("陕B99999", 0.96, "yellow", (1, 2, 80, 40)),
            PlateCandidate("陕A24680", 0.94, "blue", (10, 20, 100, 60)),
        ),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda _parent, _title, _label, items, _current, _editable: (items[1], True),
    )
    window._recognition_succeeded("entry", entry)

    with database.connect() as connection:
        stored = connection.execute(
            """
            SELECT record_id, entry_source, entry_photo
            FROM parking_record WHERE plate_no = ?
            """,
            ("陕A24680",),
        ).fetchone()
    assert stored["entry_source"] == "recognition"
    assert stored["entry_photo"] == "entry-capture.jpg"

    window.scene._fallback_timer.stop()
    window.scene._on_finished("raise")
    window._on_lower()
    window.scene._fallback_timer.stop()
    window.scene._on_finished("lower")

    monkeypatch.setattr(QDialog, "exec_", lambda _dialog: QDialog.Rejected)
    exit_result = RecognitionResult(
        plate="陕A24680",
        confidence=0.92,
        kind="blue",
        box=(8, 18, 98, 58),
        photo_path="exit-capture.jpg",
        frame_index=24,
        elapsed_ms=150,
    )
    window._recognition_succeeded("exit", exit_result)

    with database.connect() as connection:
        stored = connection.execute(
            "SELECT exit_photo FROM parking_record WHERE record_id = ?",
            (stored["record_id"],),
        ).fetchone()
    assert stored["exit_photo"] == "exit-capture.jpg"
    window._tick.stop()
    window._refresh.stop()
    window.close()
