import sqlite3
from contextlib import closing
from datetime import date

import pytest

from parking.demo_data import ABNORMAL_PLATES, default_demo_path, generate_demo_database
from parking.services.parking_service import ParkingError, normalize_plate


def _snapshot(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(
            """
            SELECT plate_no, entry_time, duration_minutes, fee_cents,
                   payment_status, exit_time
            FROM parking_record ORDER BY record_id
            """
        ).fetchall()


def test_default_demo_path_can_be_used_as_parking_data_dir(tmp_path):
    assert default_demo_path(tmp_path) == (tmp_path / "runtime" / "demo" / "parking.sqlite3")


def test_demo_generation_is_repeatable_and_does_not_stack(tmp_path):
    target = tmp_path / "demo.sqlite3"
    kwargs = dict(
        project_root=tmp_path,
        seed=42,
        start_date=date(2025, 1, 1),
        plate_count=20,
        record_count=50,
    )
    first = generate_demo_database(target, **kwargs)
    first_snapshot = _snapshot(target)
    second = generate_demo_database(target, **kwargs)
    second_snapshot = _snapshot(target)

    assert first.record_count == second.record_count == 50
    assert len(first_snapshot) == len(second_snapshot) == 50
    assert first_snapshot == second_snapshot
    assert first.scenario_counts == {name: 10 for name in first.scenario_counts}
    assert first.abnormal_plate_count == len(ABNORMAL_PLATES) >= 20


@pytest.mark.parametrize("plate", ABNORMAL_PLATES)
def test_abnormal_demo_plates_are_rejected(plate):
    with pytest.raises(ParkingError):
        normalize_plate(plate)


def test_demo_generator_refuses_business_database_and_unknown_existing_target(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("PARKING_DATA_DIR", raising=False)
    business = tmp_path / "runtime" / "parking.sqlite3"
    with pytest.raises(ValueError, match="实际业务"):
        generate_demo_database(business, project_root=tmp_path, record_count=1)

    unknown = tmp_path / "unknown.sqlite3"
    unknown.write_bytes(b"not a database")
    with pytest.raises(FileExistsError, match="不是本工具"):
        generate_demo_database(unknown, project_root=tmp_path, record_count=1)
