"""将停车统计结果导出为中文 A4 PDF。"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from parking.services.report_service import ReportResult


class ReportExportError(RuntimeError):
    """可直接显示给操作员的 PDF 导出错误。"""


def _chinese_font(font_path: str | Path | None = None) -> str:
    candidates = []
    if font_path is not None:
        candidates.append(Path(font_path))
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates.extend(
        (
            windows / "msyh.ttc",
            windows / "simhei.ttf",
            windows / "simsun.ttc",
        )
    )
    selected = next((path for path in candidates if path.is_file()), None)
    if selected is None:
        raise ReportExportError("未找到可用的中文字体（微软雅黑、黑体或宋体）")
    font_name = f"ParkingChinese-{selected.stem}"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(selected), subfontIndex=0))
        except Exception as exc:
            raise ReportExportError(f"中文字体加载失败：{selected}") from exc
    return font_name


def _table_style(font_name: str, *, header_background=colors.HexColor("#153B67")):
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, 0), 8.5),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), header_background),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C4D1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor("#F4F7FA"))),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def export_report_pdf(
    result: ReportResult,
    output: str | Path,
    *,
    generated_at: datetime | None = None,
    font_path: str | Path | None = None,
) -> Path:
    target = Path(output).resolve()
    if target.suffix.lower() != ".pdf":
        target = target.with_suffix(".pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    generated = generated_at or datetime.now().astimezone()
    font_name = _chinese_font(font_path)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#102A43"),
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "ChineseHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#153B67"),
        alignment=TA_LEFT,
        spaceBefore=8,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#334E68"),
    )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"{target.stem}_", suffix=".pdf", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#627D98"))
        canvas.drawString(
            document.leftMargin,
            10 * mm,
            f"生成时间：{generated.astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
        )
        canvas.drawRightString(
            A4[0] - document.rightMargin,
            10 * mm,
            f"第 {document.page} 页",
        )
        canvas.restoreState()

    try:
        document = SimpleDocTemplate(
            str(temporary),
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=18 * mm,
            title="停车收费统计报表",
            author="智慧停车收费系统",
        )
        story = [
            Paragraph("停车收费统计报表", title_style),
            Paragraph(
                f"查询区间：[ {result.start.astimezone().strftime('%Y-%m-%d %H:%M:%S')}，"
                f"{result.end.astimezone().strftime('%Y-%m-%d %H:%M:%S')} )<br/>"
                f"统计维度：{result.dimension_label}<br/>"
                "统计口径：仅汇总已离场记录，按进场时间归属；授权放行计入应收和未收，不计入实收。",
                body_style,
            ),
            Spacer(1, 7 * mm),
        ]

        summary = Table(
            [
                ["车次", "应收（元）", "实收（元）", "授权车次", "授权未收（元）"],
                [
                    str(result.vehicle_count),
                    f"{result.receivable:.2f}",
                    f"{result.received:.2f}",
                    str(result.authorized_count),
                    f"{result.authorized_uncollected:.2f}",
                ],
            ],
            colWidths=[28 * mm, 38 * mm, 38 * mm, 30 * mm, 38 * mm],
        )
        summary.setStyle(_table_style(font_name, header_background=colors.HexColor("#0E7490")))
        story.extend((Paragraph("汇总", heading_style), summary, Spacer(1, 5 * mm)))

        if result.periods:
            period_rows = [["统计周期", "车次", "应收（元）", "实收（元）", "授权车次", "授权未收（元）"]]
            for item in result.periods:
                period_rows.append(
                    [
                        item.label,
                        str(item.vehicle_count),
                        f"{item.receivable:.2f}",
                        f"{item.received:.2f}",
                        str(item.authorized_count),
                        f"{item.authorized_uncollected:.2f}",
                    ]
                )
            period_table = LongTable(
                period_rows,
                repeatRows=1,
                colWidths=[38 * mm, 20 * mm, 31 * mm, 31 * mm, 25 * mm, 35 * mm],
            )
            period_table.setStyle(_table_style(font_name))
            story.extend((Paragraph("分期统计", heading_style), period_table, Spacer(1, 5 * mm)))
        else:
            story.append(
                KeepTogether(
                    [
                        Paragraph("分期统计", heading_style),
                        Paragraph("该区间没有已离场停车记录。", body_style),
                    ]
                )
            )

        if result.details:
            status_text = {"paid": "已缴费", "authorized": "授权放行"}
            detail_rows = [["记录", "车牌", "车型", "进场时间", "离场时间", "应收", "实收", "状态"]]
            for item in result.details:
                detail_rows.append(
                    [
                        str(item.record_id),
                        item.plate_no,
                        item.vehicle_type,
                        item.entry_time.strftime("%Y-%m-%d %H:%M"),
                        item.exit_time.strftime("%Y-%m-%d %H:%M"),
                        f"{item.fee:.2f}",
                        f"{item.paid:.2f}",
                        status_text.get(item.payment_status, item.payment_status),
                    ]
                )
            detail_table = LongTable(
                detail_rows,
                repeatRows=1,
                colWidths=[12 * mm, 23 * mm, 20 * mm, 34 * mm, 34 * mm, 17 * mm, 17 * mm, 23 * mm],
            )
            detail_style = _table_style(font_name)
            detail_style.add("ALIGN", (0, 1), (4, -1), "LEFT")
            detail_table.setStyle(detail_style)
            story.extend((Paragraph("停车明细", heading_style), detail_table))

        document.build(story, onFirstPage=footer, onLaterPages=footer)
        if temporary.stat().st_size == 0:
            raise ReportExportError("PDF 生成结果为空")
        os.replace(temporary, target)
    except ReportExportError:
        raise
    except Exception as exc:
        raise ReportExportError(f"PDF 导出失败：{exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return target
