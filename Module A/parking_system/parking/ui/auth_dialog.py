"""首次管理员初始化与后续登录对话框。"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from parking.services.admin_service import AuthenticationError, AuthService, UserSession
from . import theme as T


class AuthDialog(QDialog):
    def __init__(self, service: AuthService, *, bootstrap: bool, parent=None):
        super().__init__(parent)
        self.service = service
        self.bootstrap = bootstrap
        self.session: UserSession | None = None
        self.setModal(True)
        self.setWindowTitle("初始化管理员" if bootstrap else "系统登录")
        self.setMinimumWidth(420)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("首次运行 · 创建管理员" if self.bootstrap else "智慧停车 · 登录")
        title.setStyleSheet(f"color:{T.TEXT}; font-size:20px; font-weight:700;")
        layout.addWidget(title)

        hint = QLabel(
            "系统未发现账号，请设置首个管理员账号。"
            if self.bootstrap
            else "请输入账号和密码后继续。"
        )
        hint.setStyleSheet(f"color:{T.MUTED};")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        self.username = QLineEdit("admin" if self.bootstrap else "")
        self.username.setPlaceholderText("3～50 个字符，不含空格")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("至少 8 个字符")
        form.addRow("用户名", self.username)
        form.addRow("密码", self.password)
        self.confirm = None
        if self.bootstrap:
            self.confirm = QLineEdit()
            self.confirm.setEchoMode(QLineEdit.Password)
            self.confirm.setPlaceholderText("再次输入密码")
            form.addRow("确认密码", self.confirm)
        layout.addLayout(form)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color:{T.RED};")
        layout.addWidget(self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("创建并登录" if self.bootstrap else "登录")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Cancel).setObjectName("ghost")
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.password.returnPressed.connect(self._submit)
        if self.confirm is not None:
            self.confirm.returnPressed.connect(self._submit)

    def _submit(self) -> None:
        if self.confirm is not None and self.password.text() != self.confirm.text():
            self.error.setText("两次输入的密码不一致")
            return
        try:
            if self.bootstrap:
                self.session = self.service.bootstrap_admin(
                    self.username.text(), self.password.text()
                )
            else:
                self.session = self.service.authenticate(
                    self.username.text(), self.password.text()
                )
        except (AuthenticationError, ValueError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()
