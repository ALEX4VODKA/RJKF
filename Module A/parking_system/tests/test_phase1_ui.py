import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

from parking.data import Database
from parking.services.admin_service import AuthService
from parking.services.rule_service import RuleService
from parking.ui.auth_dialog import AuthDialog
from parking.ui.rule_dialog import RuleManagerDialog


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


def test_bootstrap_dialog_creates_session(qt_app, tmp_path):
    database = Database(tmp_path / "ui-auth.sqlite3")
    database.initialize()
    dialog = AuthDialog(AuthService(database), bootstrap=True)
    dialog.username.setText("admin")
    dialog.password.setText("StrongPass123")
    dialog.confirm.setText("StrongPass123")

    dialog._submit()

    assert dialog.result() == QDialog.Accepted
    assert dialog.session is not None
    assert dialog.session.is_admin


def test_rule_manager_loads_persisted_rules(qt_app, tmp_path):
    database = Database(tmp_path / "ui-rules.sqlite3")
    database.initialize()
    admin = AuthService(database).bootstrap_admin("admin", "StrongPass123")
    dialog = RuleManagerDialog(RuleService(database), admin)

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "小型车"
    assert dialog.table.item(0, 8).text() == "启用·最新"
    dialog.close()
