"""收费规则校验、版本化修改、停用与审计。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from decimal import Decimal

from parking.billing import FeeRuleSnapshot, money
from parking.data import AuditRepository, Database, FeeRuleRepository
from parking.services.admin_service import UserSession, require_admin


@dataclass(frozen=True)
class RuleDraft:
    vehicle_type: str
    free_minutes: int
    first_hours: int
    first_price: Decimal
    extra_price: Decimal
    day_cap: Decimal
    effective_at: datetime


@dataclass(frozen=True)
class FeeRuleVersion:
    rule_id: int
    vehicle_type: str
    version: int
    free_minutes: int
    first_hours: int
    first_price: Decimal
    extra_price: Decimal
    day_cap: Decimal
    effective_at: datetime
    active: bool
    supersedes_rule_id: int | None

    def snapshot(self) -> FeeRuleSnapshot:
        return FeeRuleSnapshot(
            rule_id=self.rule_id,
            version=self.version,
            vehicle_type=self.vehicle_type,
            free_minutes=self.free_minutes,
            first_hours=self.first_hours,
            first_price=self.first_price,
            extra_price=self.extra_price,
            day_cap=self.day_cap,
        )


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cents(value: Decimal) -> int:
    return int(money(value) * 100)


def _amount(cents: int) -> Decimal:
    return money(Decimal(cents) / 100)


def _from_row(row) -> FeeRuleVersion:
    return FeeRuleVersion(
        rule_id=row["rule_id"],
        vehicle_type=row["vehicle_type"],
        version=row["version"],
        free_minutes=row["free_minutes"],
        first_hours=row["first_hours"],
        first_price=_amount(row["first_price_cents"]),
        extra_price=_amount(row["extra_price_cents"]),
        day_cap=_amount(row["day_cap_cents"]),
        effective_at=_parse_time(row["effective_at"]),
        active=bool(row["active"]),
        supersedes_rule_id=row["supersedes_rule_id"],
    )


def _audit_value(rule: FeeRuleVersion | RuleDraft) -> str:
    data = asdict(rule)
    data["first_price"] = str(data["first_price"])
    data["extra_price"] = str(data["extra_price"])
    data["day_cap"] = str(data["day_cap"])
    data["effective_at"] = data["effective_at"].isoformat()
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


class RuleService:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _validated(draft: RuleDraft, now: datetime) -> RuleDraft:
        vehicle_type = draft.vehicle_type.strip()
        if not vehicle_type or len(vehicle_type) > 20:
            raise ValueError("车型名称不能为空且不能超过 20 个字符")
        if draft.effective_at.tzinfo is None or draft.effective_at.utcoffset() is None:
            raise ValueError("生效时间必须包含时区信息")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("当前时间必须包含时区信息")
        local_now = now.astimezone()
        day_start = datetime.combine(local_now.date(), time.min, tzinfo=local_now.tzinfo)
        if draft.effective_at.astimezone(local_now.tzinfo) < day_start:
            raise ValueError("生效时间不能早于当天零点")
        snapshot = FeeRuleSnapshot(
            vehicle_type=vehicle_type,
            free_minutes=draft.free_minutes,
            first_hours=draft.first_hours,
            first_price=draft.first_price,
            extra_price=draft.extra_price,
            day_cap=draft.day_cap,
        )
        return RuleDraft(
            vehicle_type=vehicle_type,
            free_minutes=snapshot.free_minutes,
            first_hours=snapshot.first_hours,
            first_price=snapshot.first_price,
            extra_price=snapshot.extra_price,
            day_cap=snapshot.day_cap,
            effective_at=draft.effective_at,
        )

    def list_rules(self, actor: UserSession) -> list[FeeRuleVersion]:
        require_admin(actor)
        with self.database.connect() as connection:
            require_admin(actor, connection)
            return [_from_row(row) for row in FeeRuleRepository(connection).list_all()]

    def create_rule(
        self,
        actor: UserSession,
        draft: RuleDraft,
        *,
        now: datetime | None = None,
    ) -> FeeRuleVersion:
        require_admin(actor)
        current = now or datetime.now().astimezone()
        valid = self._validated(draft, current)
        with self.database.transaction() as connection:
            require_admin(actor, connection)
            rules = FeeRuleRepository(connection)
            history = rules.history_for(valid.vehicle_type)
            if any(bool(row["active"]) for row in history):
                raise ValueError("该车型已有启用规则，请使用“版本化修改”")
            version = max((int(row["version"]) for row in history), default=0) + 1
            supersedes = history[0]["rule_id"] if history else None
            rule_id = rules.insert(
                vehicle_type=valid.vehicle_type,
                version=version,
                free_minutes=valid.free_minutes,
                first_hours=valid.first_hours,
                first_price_cents=_cents(valid.first_price),
                extra_price_cents=_cents(valid.extra_price),
                day_cap_cents=_cents(valid.day_cap),
                effective_at=_utc_text(valid.effective_at),
                created_by=actor.admin_id,
                supersedes_rule_id=supersedes,
            )
            created = _from_row(rules.get(rule_id))
            AuditRepository(connection).insert(
                "fee_rule.create",
                admin_id=actor.admin_id,
                target=f"fee_rule:{rule_id}",
                after_value=_audit_value(created),
            )
        return created

    def update_rule(
        self,
        actor: UserSession,
        rule_id: int,
        draft: RuleDraft,
        *,
        now: datetime | None = None,
    ) -> FeeRuleVersion:
        require_admin(actor)
        current = now or datetime.now().astimezone()
        valid = self._validated(draft, current)
        with self.database.transaction() as connection:
            require_admin(actor, connection)
            rules = FeeRuleRepository(connection)
            selected_row = rules.get(rule_id)
            if selected_row is None:
                raise ValueError("收费规则不存在")
            selected = _from_row(selected_row)
            if not selected.active:
                raise ValueError("已停用规则不能修改，请新增规则")
            if valid.vehicle_type != selected.vehicle_type:
                raise ValueError("版本化修改不能改变车型")

            history = rules.history_for(selected.vehicle_type)
            if history[0]["rule_id"] != selected.rule_id:
                raise ValueError("只能基于该车型的最新版本进行修改")
            active_effective = [
                _parse_time(row["effective_at"])
                for row in history
                if bool(row["active"])
            ]
            if active_effective and valid.effective_at.astimezone(timezone.utc) < max(
                active_effective
            ):
                raise ValueError("新版本生效时间不能早于现有最新版本")
            version = max(int(row["version"]) for row in history) + 1
            new_id = rules.insert(
                vehicle_type=valid.vehicle_type,
                version=version,
                free_minutes=valid.free_minutes,
                first_hours=valid.first_hours,
                first_price_cents=_cents(valid.first_price),
                extra_price_cents=_cents(valid.extra_price),
                day_cap_cents=_cents(valid.day_cap),
                effective_at=_utc_text(valid.effective_at),
                created_by=actor.admin_id,
                supersedes_rule_id=selected.rule_id,
            )
            created = _from_row(rules.get(new_id))
            AuditRepository(connection).insert(
                "fee_rule.update",
                admin_id=actor.admin_id,
                target=f"fee_rule:{new_id}",
                before_value=_audit_value(selected),
                after_value=_audit_value(created),
            )
        return created

    def deactivate_rule(self, actor: UserSession, rule_id: int) -> int:
        require_admin(actor)
        with self.database.transaction() as connection:
            require_admin(actor, connection)
            rules = FeeRuleRepository(connection)
            row = rules.get(rule_id)
            if row is None:
                raise ValueError("收费规则不存在")
            selected = _from_row(row)
            changed = rules.deactivate_vehicle_type(selected.vehicle_type)
            if changed == 0:
                raise ValueError("该车型规则已经停用")
            AuditRepository(connection).insert(
                "fee_rule.deactivate",
                admin_id=actor.admin_id,
                target=f"vehicle_type:{selected.vehicle_type}",
                before_value=json.dumps(
                    {"active_versions": changed}, ensure_ascii=False
                ),
                after_value=json.dumps({"active": False}),
            )
        return changed
