"""Render an evidence-bound Markdown report as a bright visual PDF."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    lines: tuple[str, ...]


_INTERNAL_EVIDENCE = re.compile(r"\s*`?\[(?:observed|calculated|interpreted|hypothesis)\]`?\s*（?evidence:.*?\）?$")
_INTERNAL_IDS = re.compile(r"\s*与?\s*evidence\s*ID\s*[:：].*$", re.IGNORECASE)


def _display_line(line: str) -> str:
    """Keep the PDF reader-facing text free of internal evidence annotations."""
    return _INTERNAL_IDS.sub("", _INTERNAL_EVIDENCE.sub("", line)).rstrip("` ")


def parse_markdown(source: str) -> tuple[str, tuple[ReportSection, ...]]:
    title = "社媒研究报告"
    sections: list[ReportSection] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            title = line[2:].strip() or title
        elif line.startswith("## "):
            if current_title is not None:
                sections.append(ReportSection(current_title, tuple(current_lines)))
            current_title = line[3:].strip()
            current_lines = []
        elif line:
            current_lines.append(_display_line(line.removeprefix("- ")))
    if current_title is not None:
        sections.append(ReportSection(current_title, tuple(current_lines)))
    return title, tuple(sections)


def render_pdf(input_path: Path, output_path: Path, *, period: str = "", source_count: int = 0) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(TTFont("QiqiSans", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
    title, sections = parse_markdown(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    navy = colors.HexColor("#111827")
    ink = colors.HexColor("#172033")
    cyan = colors.HexColor("#00DDF5")
    lime = colors.HexColor("#D9FF38")
    coral = colors.HexColor("#FF6B5E")
    mist = colors.HexColor("#F4F7FB")
    slate = colors.HexColor("#62708A")
    styles = getSampleStyleSheet()
    hero = ParagraphStyle("hero", parent=styles["Normal"], fontName="QiqiSans", fontSize=26, leading=34, textColor=colors.white)
    subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontName="QiqiSans", fontSize=10, leading=15, textColor=colors.HexColor("#C6D2E7"))
    section = ParagraphStyle("section", parent=styles["Normal"], fontName="QiqiSans", fontSize=16, leading=22, textColor=navy, spaceAfter=5)
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="QiqiSans", fontSize=10, leading=16, textColor=ink, alignment=TA_LEFT)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, firstLineIndent=-8, spaceAfter=4)
    caption = ParagraphStyle("caption", parent=styles["Normal"], fontName="QiqiSans", fontSize=8, leading=12, textColor=slate)

    evidence_lines = sum(1 for item in sections for line in item.lines if line)
    cards = [
        ("研究章节", str(len(sections)), cyan),
        ("研究要点", str(evidence_lines), lime),
        ("信息源", str(source_count) if source_count else "已记录", coral),
    ]
    story = []
    cover = Table([[Paragraph(title, hero), Paragraph(f"研究时间\n{period or '以报告为准'}", subtitle)]], colWidths=[128 * mm, 50 * mm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy), ("BOX", (0, 0), (-1, -1), 0, navy),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 12 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 10 * mm), ("TOPPADDING", (0, 0), (-1, -1), 14 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14 * mm),
    ]))
    story.extend([cover, Spacer(1, 7 * mm)])
    card_cells = []
    for label, value, accent in cards:
        cell = Table([[Paragraph(value, ParagraphStyle("metric", parent=body, fontSize=23, leading=27, textColor=navy))], [Paragraph(label, caption)]], colWidths=[52 * mm])
        cell.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), mist), ("LINEABOVE", (0, 0), (-1, 0), 4, accent), ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm), ("TOPPADDING", (0, 0), (-1, -1), 5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm)]))
        card_cells.append(cell)
    story.extend([Table([card_cells], colWidths=[54 * mm] * 3), Spacer(1, 8 * mm)])

    for index, item in enumerate(sections):
        rows = [[Paragraph(f"{index + 1:02d}  {item.title}", section)]]
        for line in item.lines:
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            rows.append([Paragraph(f"- {safe}", bullet)])
        # Keep each line as a row so long sections (especially raw work lists)
        # can split across pages instead of becoming one oversized table cell.
        block = Table(rows, colWidths=[178 * mm], repeatRows=1)
        block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("LINEBEFORE", (0, 0), (0, -1), 3, cyan if index % 2 == 0 else lime),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCE4F0")), ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm), ("TOPPADDING", (0, 0), (-1, -1), 5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ]))
        story.extend([block, Spacer(1, 4 * mm)])

    def page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0, 0, A4[0], 8 * mm, fill=1, stroke=0)
        canvas.setFont("QiqiSans", 8)
        canvas.setFillColor(colors.HexColor("#6B7891"))
        canvas.drawString(16 * mm, 12 * mm, "qiqi-media-research  |  evidence-first visual report")
        canvas.drawRightString(A4[0] - 16 * mm, 12 * mm, f"{document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=20 * mm)
    document.build(story, onFirstPage=page, onLaterPages=page)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a bright visual PDF from an evidence-bound Markdown report")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--period", default="")
    parser.add_argument("--source-count", type=int, default=0)
    args = parser.parse_args()
    render_pdf(args.input, args.out, period=args.period, source_count=args.source_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
