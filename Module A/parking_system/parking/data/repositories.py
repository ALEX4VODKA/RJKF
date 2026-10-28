"""P1-A 所需的基础仓储；业务层通过仓储访问 SQL。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须包含时区信息")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class VehicleRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert(
        self,
        plate_no: str,
        vehicle_type: str,
        plate_color: str,
        owner_name: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO vehicle (plate_no, vehicle_type, plate_color, owner_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(plate_no) DO UPDATE SET
                vehicle_type = excluded.vehicle_type,
                plate_color = excluded.plate_color,
                owner_name = COALESCE(excluded.owner_name, vehicle.owner_name),
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            (plate_no, vehicle_type, plate_color, owner_name),
        )

    def get(self, plate_no: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM vehicle WHERE plate_no = ?", (plate_no,)
        ).fetchone()


class FeeRuleRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def get(self, rule_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM fee_rule WHERE rule_id = ?", (rule_id,)
        ).fetchone()

    def latest_for(self, vehicle_type: str, at: datetime) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM fee_rule
            WHERE vehicle_type = ? AND active = 1 AND effective_at <= ?
            ORDER BY effective_at DESC, version DESC
            LIMIT 1
            """,
            (vehicle_type, _utc_text(at)),
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM fee_rule ORDER BY vehicle_type, version DESC"
            ).fetchall()
        )

    def history_for(self, vehicle_type: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT * FROM fee_rule
                WHERE vehicle_type = ?
                ORDER BY version DESC
                """,
                (vehicle_type,),
            ).fetchall()
        )

    def insert(
        self,
        *,
        vehicle_type: str,
        version: int,
        free_minutes: int,
        first_hours: int,
        first_price_cents: int,
        extra_price_cents: int,
        day_cap_cents: int,
        effective_at: str,
        created_by: int,
        supersedes_rule_id: int | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO fee_rule (
                vehicle_type, version, free_minutes, first_hours,
                first_price_cents, extra_price_cents, day_cap_cents,
                effective_at, supersedes_rule_id, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vehicle_type,
                version,
                free_minutes,
                first_hours,
                first_price_cents,
                extra_price_cents,
                day_cap_cents,
                effective_at,
                supersedes_rule_id,
                created_by,
            ),
        )
        return int(cursor.lastrowid)

    def deactivate_vehicle_type(self, vehicle_type: str) -> int:
        cursor = self.connection.execute(
            """
            UPDATE fee_rule SET active = 0
            WHERE vehicle_type = ? AND active = 1
            """,
            (vehicle_type,),
        )
        return int(cursor.rowcount)


class RecordRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_open(
        self,
        plate_no: str,
        rule_id: int,
        entry_time: datetime,
        *,
        entry_photo: str | None = None,
        entry_source: str = "manual",
    ) -> int:
        vehicle = self.connection.execute(
            "SELECT vehicle_type, plate_color FROM vehicle WHERE plate_no = ?",
            (plate_no,),
        ).fetchone()
        if vehicle is None:
            raise ValueError(f"车辆不存在：{plate_no}")

        rule = self.connection.execute(
            "SELECT * FROM fee_rule WHERE rule_id = ?", (rule_id,)
        ).fetchone()
        if rule is None:
            raise ValueError(f"收费规则不存在：{rule_id}")
        if rule["vehicle_type"] != vehicle["vehicle_type"]:
            raise ValueError("收费规则车型与车辆车型不一致")

        cursor = self.connection.execute(
            """
            INSERT INTO parking_record (
                plate_no, vehicle_type, plate_color, entry_time, entry_photo,
                entry_source, fee_rule_id, rule_free_minutes, rule_first_hours,
                rule_first_price_cents, rule_extra_price_cents, rule_day_cap_cents
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plate_no,
                vehicle["vehicle_type"],
                vehicle["plate_color"],
                _utc_text(entry_time),
                entry_photo,
                entry_source,
                rule_id,
                rule["free_minutes"],
                rule["first_hours"],
                rule["first_price_cents"],
                rule["extra_price_cents"],
                rule["day_cap_cents"],
            ),
        )
        return int(cursor.lastrowid)

    def find_open(self, plate_no: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT * FROM parking_record
            WHERE plate_no = ? AND exit_time IS NULL
            ORDER BY record_id DESC LIMIT 1
            """,
            (plate_no,),
        ).fetchone()

    def list_present(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT * FROM parking_record
                WHERE exit_time IS NULL
                ORDER BY entry_time DESC, record_id DESC
                """
            ).fetchall()
        )


class AdminRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM admin").fetchone()[0])

    def create(
        self,
        username: str,
        password_hash: str,
        salt: str,
        role: str,
        *,
        must_change_password: bool = False,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO admin (
                username, password_hash, salt, role, must_change_password
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, password_hash, salt, role, int(must_change_password)),
        )
        return int(cursor.lastrowid)

    def find_by_username(self, username: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM admin WHERE username = ?", (username,)
        ).fetchone()

    def get(self, admin_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM admin WHERE admin_id = ?", (admin_id,)
        ).fetchone()

    def record_login_failure(
        self, admin_id: int, fail_count: int, locked_until: str | None
    ) -> None:
        self.connection.execute(
            """
            UPDATE admin
            SET fail_count = ?, locked_until = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE admin_id = ?
            """,
            (fail_count, locked_until, admin_id),
        )

    def record_login_success(self, admin_id: int) -> None:
        self.connection.execute(
            """
            UPDATE admin
            SET fail_count = 0, locked_until = NULL,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE admin_id = ?
            """,
            (admin_id,),
        )

    def update_password(
        self, admin_id: int, password_hash: str, salt: str
    ) -> None:
        self.connection.execute(
            """
            UPDATE admin
            SET password_hash = ?, salt = ?, must_change_password = 0,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE admin_id = ?
            """,
            (password_hash, salt, admin_id),
        )


class AuditRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def insert(
        self,
        action: str,
        *,
        admin_id: int | None = None,
        target: str | None = None,
        before_value: str | None = None,
        after_value: str | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO operation_log (
                admin_id, action, target, before_value, after_value
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_id, action, target, before_value, after_value),
        )
        return int(cursor.lastrowid)

    def list_recent(self, limit: int = 100) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT * FROM operation_log
                ORDER BY log_id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )
