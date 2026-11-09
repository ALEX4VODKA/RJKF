"""答辩演示数据准备与需求追踪清单。

本模块只操作由自己生成的独立演示库。它不替换真实识别结果：FR-1
仍由 ``LicenseRecognizer`` 对操作员选取的本地图片或视频执行推理。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import os
from pathlib import Path
import shutil
import tempfile

from parking.data import Database
from parking.demo_data import DEFAULT_SEED, generate_demo_database
from parking.services.admin_service import AuthService
from parking.services.parking_service import ParkingService


DEMO_USERNAME = "test"
DEMO_PASSWORD = "1"
DEMO_RUNTIME_NAME = "defense_demo"
PACKAGED_TEMPLATE_NAME = "demo-template"


@dataclass(frozen=True)
class DefenseDemoSummary:
    database_path: Path
    report_start_date: date
    open_plates: tuple[str, ...]


# These are shown in the UI as the operator's concise run book.  The rows are
# intentionally tied to the requirement report rather than internal class names.
DEMO_GUIDE_ROWS = (
    ("FR-1 / TC-01", "选择真实车牌图片或视频", "识别出车牌与置信度；失败后可人工补录。"),
    ("FR-2 / TC-01", "完成识别进场或点“人工进场”", "登记、保存抓拍、入口 3D 抬杆，车辆通过后落杆。"),
    ("FR-3 / FR-4 / TC-02", "人工出场输入 陕A90002", "显示车牌、时长、照片位与 11.00 元账单；模拟缴费后出口抬杆。"),
    ("FR-3 / TC-03", "人工出场输入 陕A90003", "10 分钟免费，0.00 元可放行。"),
    ("FR-5 / TC-04", "人工出场输入 陕A90004", "未缴费不能放行，界面提示先缴费。"),
    ("FR-5 / TC-05", "人工出场输入 陕A90005", "管理员填写原因并验证后授权放行；报表单列授权金额。"),
    ("FR-3 / TC-09", "人工出场输入 陕A90009", "已冻结的 26 小时跨天账单为 60.00 元，明细显示两日封顶。"),
    ("FR-6 / TC-10", "收费标准 → 修改规则 → 新车进出场", "新规则即时用于新记录；既有账单保持其规则快照。"),
    ("FR-7 / TC-11", "统计报表 → 选择日/周/月/季/年", "最近 30 天已有可查询数据，车次与金额来自 SQLite。"),
    ("FR-8 / TC-12", "统计报表 → 导出 PDF → 打开/打印", "生成可保存、打开和调用系统打印的 PDF。"),
    ("异常 / TC-06～08", "重复进场、未知车牌、模糊图片", "分别提示已在场、无进场记录、三次识别后转人工，不中断程序。"),
)


def default_defense_path(project_root: str | Path) -> Path:
    return (Path(project_root).resolve() / "runtime" / DEMO_RUNTIME_NAME / "parking.sqlite3")


def packaged_template_path(application_root: str | Path) -> Path:
    return (Path(application_root).resolve() / PACKAGED_TEMPLATE_NAME / "parking.sqlite3")


def install_packaged_demo(template: str | Path, output: str | Path) -> Path:
    """原子复制随便携包交付的演示库模板。"""
    source = Path(template).resolve()
    target = Path(output).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"演示库模板不存在：{source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="parking_defense_", suffix=".sqlite3", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(target) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def _local_now(value: datetime | None) -> datetime:
    current = value or datetime.now().astimezone()
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("答辩演示时间必须包含时区信息")
    return current


def _cross_day_cutoff(now: datetime) -> datetime:
    """返回已过去的 26 小时固定计费截止点，确保两个自然日均可触发封顶。"""
    candidate = datetime.combine(now.date(), time(14, 0), tzinfo=now.tzinfo)
    if candidate >= now:
        candidate -= timedelta(days=1)
    return candidate


def prepare_defense_demo(
    project_root: str | Path,
    *,
    output: str | Path | None = None,
    now: datetime | None = None,
) -> DefenseDemoSummary:
    """重建受管的演示库，并预置答辩时可直接查询的在场车辆。

    历史数据覆盖最近一年，故报表默认的最近 30 天即有数据。每次重建
    使用相同随机种子；相对当前时间的开放记录用于现场交互。
    """
    root = Path(project_root).resolve()
    target = Path(output).resolve() if output is not None else default_defense_path(root)
    current = _local_now(now)
    report_start = current.date() - timedelta(days=364)
    generate_demo_database(
        target,
        project_root=root,
        seed=DEFAULT_SEED,
        start_date=report_start,
        plate_count=240,
        record_count=1000,
        admin_username=DEMO_USERNAME,
        admin_password=DEMO_PASSWORD,
    )

    database = Database(target)
    admin = AuthService(database).authenticate(DEMO_USERNAME, DEMO_PASSWORD)
    service = ParkingService(database, admin, local_timezone=current.tzinfo)

    def enter(plate: str, entered_at: datetime):
        return service.enter_vehicle(plate, "小型车", "blue", source="demo", at=entered_at)

    enter("陕A90002", current - timedelta(hours=3, minutes=20))
    enter("陕A90003", current - timedelta(minutes=10))

    unpaid = enter("陕A90004", current - timedelta(hours=3, minutes=20))
    service.bill(unpaid.plate, at=current)

    authorized = enter("陕A90005", current - timedelta(hours=3, minutes=20))
    service.bill(authorized.plate, at=current)

    cutoff = _cross_day_cutoff(current)
    cross_day = enter("陕A90009", cutoff - timedelta(hours=26))
    service.bill(cross_day.plate, at=cutoff)

    return DefenseDemoSummary(
        database_path=target,
        report_start_date=report_start,
        open_plates=("陕A90002", "陕A90003", "陕A90004", "陕A90005", "陕A90009"),
    )
