"""本地账号认证、角色校验与失败锁定。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from parking.data import AdminRepository, AuditRepository, Database


PBKDF2_ITERATIONS = 100_000
MAX_LOGIN_FAILURES = 5
LOCK_MINUTES = 5


class AuthenticationError(ValueError):
    pass


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class UserSession:
    admin_id: int
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须包含时区信息")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _password_hash(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return base64.b64encode(digest).decode("ascii")


def _new_password(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    return _password_hash(password, salt), base64.b64encode(salt).decode("ascii")


def _verify_password(password: str, password_hash: str, salt_text: str) -> bool:
    salt = base64.b64decode(salt_text.encode("ascii"), validate=True)
    actual = _password_hash(password, salt)
    return hmac.compare_digest(actual, password_hash)


def require_admin(session: UserSession, connection=None) -> None:
    if not session.is_admin:
        raise AuthorizationError("当前操作仅管理员可执行")
    if connection is not None:
        row = AdminRepository(connection).get(session.admin_id)
        if (
            row is None
            or row["username"] != session.username
            or row["role"] != "admin"
        ):
            raise AuthorizationError("管理员身份校验失败，请重新登录")


class AuthService:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _validate_credentials(username: str, password: str) -> tuple[str, str]:
        username = username.strip()
        if not 3 <= len(username) <= 50 or any(ch.isspace() for ch in username):
            raise AuthenticationError("用户名须为 3～50 个不含空格的字符")
        if len(password) < 8:
            raise AuthenticationError("密码至少需要 8 个字符")
        return username, password

    def has_accounts(self) -> bool:
        with self.database.connect() as connection:
            return AdminRepository(connection).count() > 0

    def bootstrap_admin(self, username: str, password: str) -> UserSession:
        username, password = self._validate_credentials(username, password)
        password_hash, salt = _new_password(password)
        with self.database.transaction() as connection:
            admins = AdminRepository(connection)
            if admins.count() != 0:
                raise AuthenticationError("系统已经完成管理员初始化")
            admin_id = admins.create(username, password_hash, salt, "admin")
            AuditRepository(connection).insert(
                "account.bootstrap",
                admin_id=admin_id,
                target=f"admin:{admin_id}",
                after_value=json.dumps(
                    {"username": username, "role": "admin"}, ensure_ascii=False
                ),
            )
        return UserSession(admin_id, username, "admin")

    def authenticate(
        self, username: str, password: str, *, now: datetime | None = None
    ) -> UserSession:
        username = username.strip()
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("当前时间必须包含时区信息")

        error: AuthenticationError | None = None
        session: UserSession | None = None
        with self.database.transaction() as connection:
            admins = AdminRepository(connection)
            audit = AuditRepository(connection)
            row = admins.find_by_username(username)
            if row is None:
                audit.insert("login.failed", target=f"username:{username}")
                error = AuthenticationError("用户名或密码错误")
            else:
                locked_until = _parse_time(row["locked_until"])
                if locked_until and locked_until > current.astimezone(timezone.utc):
                    audit.insert(
                        "login.locked",
                        admin_id=row["admin_id"],
                        target=f"admin:{row['admin_id']}",
                    )
                    error = AuthenticationError("账号已锁定，请稍后再试")
                elif _verify_password(password, row["password_hash"], row["salt"]):
                    admins.record_login_success(row["admin_id"])
                    audit.insert(
                        "login.success",
                        admin_id=row["admin_id"],
                        target=f"admin:{row['admin_id']}",
                    )
                    session = UserSession(row["admin_id"], row["username"], row["role"])
                else:
                    expired_lock = locked_until is not None and locked_until <= current
                    fail_count = 1 if expired_lock else int(row["fail_count"]) + 1
                    new_lock = None
                    if fail_count >= MAX_LOGIN_FAILURES:
                        new_lock = _utc_text(current + timedelta(minutes=LOCK_MINUTES))
                    admins.record_login_failure(row["admin_id"], fail_count, new_lock)
                    audit.insert(
                        "login.failed",
                        admin_id=row["admin_id"],
                        target=f"admin:{row['admin_id']}",
                        after_value=json.dumps({"fail_count": fail_count}),
                    )
                    message = (
                        "登录失败次数过多，账号已锁定 5 分钟"
                        if new_lock
                        else "用户名或密码错误"
                    )
                    error = AuthenticationError(message)

        if error:
            raise error
        assert session is not None
        return session

    def create_account(
        self,
        actor: UserSession,
        username: str,
        password: str,
        role: str,
    ) -> UserSession:
        require_admin(actor)
        username, password = self._validate_credentials(username, password)
        if role not in {"admin", "operator"}:
            raise ValueError("角色必须为 admin 或 operator")
        password_hash, salt = _new_password(password)
        with self.database.transaction() as connection:
            require_admin(actor, connection)
            admin_id = AdminRepository(connection).create(
                username, password_hash, salt, role
            )
            AuditRepository(connection).insert(
                "account.create",
                admin_id=actor.admin_id,
                target=f"admin:{admin_id}",
                after_value=json.dumps(
                    {"username": username, "role": role}, ensure_ascii=False
                ),
            )
        return UserSession(admin_id, username, role)

    def change_password(
        self, actor: UserSession, old_password: str, new_password: str
    ) -> None:
        if len(new_password) < 8:
            raise AuthenticationError("新密码至少需要 8 个字符")
        with self.database.transaction() as connection:
            admins = AdminRepository(connection)
            row = admins.find_by_username(actor.username)
            if (
                row is None
                or row["admin_id"] != actor.admin_id
                or not _verify_password(
                    old_password, row["password_hash"], row["salt"]
                )
            ):
                raise AuthenticationError("当前密码错误")
            password_hash, salt = _new_password(new_password)
            admins.update_password(actor.admin_id, password_hash, salt)
            AuditRepository(connection).insert(
                "account.password_change",
                admin_id=actor.admin_id,
                target=f"admin:{actor.admin_id}",
            )

    def list_audit_events(self, actor: UserSession, limit: int = 100):
        require_admin(actor)
        if not 1 <= limit <= 1000:
            raise ValueError("审计查询条数必须为 1～1000")
        with self.database.connect() as connection:
            require_admin(actor, connection)
            return AuditRepository(connection).list_recent(limit)
