from datetime import datetime, timedelta, timezone

from parking.report_pdf import export_report_pdf
from parking.services.report_service import ReportDetail, ReportPeriod, ReportResult


CN_TZ = timezone(timedelta(hours=8))


def _result(detail_count=80):
    start = datetime(2026, 1, 1, tzinfo=CN_TZ)
    details = tuple(
        ReportDetail(
            record_id=index + 1,
            plate_no=f"陕A{index:05d}",
            vehicle_type="小型车",
            entry_time=start + timedelta(hours=index * 3),
            exit_time=start + timedelta(hours=index * 3 + 2),
            fee_cents=500,
            paid_cents=0 if index % 10 == 0 else 500,
            payment_status="authorized" if index % 10 == 0 else "paid",
            release_type="authorized" if index % 10 == 0 else "auto",
        )
        for index in range(detail_count)
    )
    authorized = sum(item.payment_status == "authorized" for item in details)
    period = ReportPeriod(
        key="2026-01",
        label="2026-01",
        start=start,
        end=datetime(2026, 2, 1, tzinfo=CN_TZ),
        vehicle_count=detail_count,
        receivable_cents=detail_count * 500,
        received_cents=(detail_count - authorized) * 500,
        authorized_count=authorized,
        authorized_uncollected_cents=authorized * 500,
    )
    return ReportResult(
        dimension="month",
        start=start,
        end=datetime(2026, 2, 1, tzinfo=CN_TZ),
        periods=(period,),
        details=details,
    )


def test_pdf_export_supports_chinese_empty_and_multi_page_reports(tmp_path):
    multi = export_report_pdf(
        _result(),
        tmp_path / "多页停车统计.pdf",
        generated_at=datetime(2026, 10, 30, 12, tzinfo=CN_TZ),
    )
    empty_result = ReportResult(
        dimension="day",
        start=datetime(2026, 1, 1, tzinfo=CN_TZ),
        end=datetime(2026, 1, 2, tzinfo=CN_TZ),
        periods=(),
        details=(),
    )
    empty = export_report_pdf(empty_result, tmp_path / "空统计.pdf")

    assert multi.read_bytes().startswith(b"%PDF-")
    assert empty.read_bytes().startswith(b"%PDF-")
    assert multi.stat().st_size > empty.stat().st_size > 1000
