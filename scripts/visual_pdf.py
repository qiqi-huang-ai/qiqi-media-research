"""Render an evidence-bound Markdown report as a bright visual PDF.

Markdown remains the reader-facing source of truth. Charts are optional and
calculated from the deterministic ``analysis/data-pack.json`` of the same run;
the renderer never generates new prose conclusions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
from statistics import median
from typing import Any


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PillarMetric:
    label: str
    count: int
    views_median: float | None


@dataclass(frozen=True, slots=True)
class AccountVisualData:
    account_name: str | None
    followers: int | None
    sample_size: int
    views_median: float | None
    likes_median: float | None
    high_median: float | None
    low_median: float | None
    pillars: tuple[PillarMetric, ...]
    comment_count: int
    comment_post_count: int


_INTERNAL_EVIDENCE = re.compile(r"\s*`?\[(?:observed|calculated|interpreted|hypothesis)\]`?\s*（?evidence:.*?\）?$")
_INTERNAL_IDS = re.compile(r"\s*与?\s*evidence\s*ID\s*[:：].*$", re.IGNORECASE)
_MARKDOWN_EMPHASIS = re.compile(r"(\*\*|__|`)")


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


def infer_data_pack_path(report_path: Path) -> Path | None:
    """Find the sibling research data pack without guessing across runs."""
    candidate = report_path.parent.parent / "analysis" / "data-pack.json"
    return candidate if candidate.is_file() else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _positive_numbers(values: list[Any]) -> list[float]:
    return [number for item in values if (number := _number(item)) is not None and number > 0]


def _as_int(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _band_medians(posts: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    values = sorted(_positive_numbers([post.get("views") for post in posts]), reverse=True)
    if not values:
        return None, None
    group_size = max(1, len(values) // 4)
    return float(median(values[:group_size])), float(median(values[-group_size:]))


def load_account_visual_data(data_pack_path: Path | None) -> AccountVisualData | None:
    """Read only directly observable account metrics from one data pack.

    The legacy flattened pack is supported so old runs can still be rendered,
    while newly generated packs use ``decision_metrics`` directly.
    """
    if data_pack_path is None or not data_pack_path.is_file():
        return None
    try:
        pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if pack.get("mode") != "account-audit":
        return None

    posts = [post for post in pack.get("posts", []) if isinstance(post, dict)]
    account = pack.get("account") if isinstance(pack.get("account"), dict) else {}
    decisions = pack.get("decision_metrics") if isinstance(pack.get("decision_metrics"), dict) else {}
    baseline = decisions.get("baseline") if isinstance(decisions.get("baseline"), dict) else {}
    performance = decisions.get("performance_bands") if isinstance(decisions.get("performance_bands"), dict) else {}
    comments = pack.get("comments")
    coverage = decisions.get("comment_coverage") if isinstance(decisions.get("comment_coverage"), dict) else {}

    views_median = _number(baseline.get("views_median"))
    if views_median is None:
        legacy = pack.get("baseline_recent") if isinstance(pack.get("baseline_recent"), dict) else {}
        overall = pack.get("baseline_overall") if isinstance(pack.get("baseline_overall"), dict) else {}
        views_median = _number(legacy.get("views_median")) or _number(overall.get("views_median"))
    if views_median is None:
        values = _positive_numbers([post.get("views") for post in posts])
        views_median = float(median(values)) if values else None

    likes_median = _number(baseline.get("likes_median"))
    if likes_median is None:
        legacy = pack.get("baseline_recent") if isinstance(pack.get("baseline_recent"), dict) else {}
        likes_median = _number(legacy.get("likes_median"))
    if likes_median is None:
        values = _positive_numbers([post.get("likes") for post in posts])
        likes_median = float(median(values)) if values else None

    high_median = _number(performance.get("high_median"))
    low_median = _number(performance.get("low_median"))
    if high_median is None or low_median is None:
        fallback_high, fallback_low = _band_medians(posts)
        high_median = high_median if high_median is not None else fallback_high
        low_median = low_median if low_median is not None else fallback_low

    raw_pillars = decisions.get("content_pillars")
    if not isinstance(raw_pillars, list):
        raw_pillars = pack.get("category_medians") if isinstance(pack.get("category_medians"), list) else []
    pillars: list[PillarMetric] = []
    for item in raw_pillars:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("cat") or "未命名内容类型").strip()
        count = _as_int(item.get("count")) or 0
        if label and count:
            pillars.append(PillarMetric(label, count, _number(item.get("views_median"))))

    if isinstance(comments, list):
        fallback_comment_count = len(comments)
        fallback_post_count = len({str(item.get("post_id")) for item in comments if isinstance(item, dict) and item.get("post_id")})
    elif isinstance(comments, dict):
        fallback_comment_count = _as_int(comments.get("total")) or 0
        fallback_post_count = _as_int(comments.get("posts_covered")) or 0
    else:
        fallback_comment_count = 0
        fallback_post_count = 0

    sample = pack.get("sample") if isinstance(pack.get("sample"), dict) else {}
    sample_size = _as_int(sample.get("total")) or len(posts)
    return AccountVisualData(
        account_name=str(account.get("name") or "").strip() or None,
        followers=_as_int(account.get("followers")),
        sample_size=sample_size,
        views_median=views_median,
        likes_median=likes_median,
        high_median=high_median,
        low_median=low_median,
        pillars=tuple(sorted(pillars, key=lambda item: (-item.count, item.label))),
        comment_count=_as_int(coverage.get("count")) or fallback_comment_count,
        comment_post_count=_as_int(coverage.get("post_count")) or fallback_post_count,
    )


def _format_number(value: float | int | None) -> str:
    if value is None:
        return "未返回"
    number = float(value)
    if number >= 10000:
        rendered = f"{number / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{rendered} 万"
    return f"{int(round(number)):,}"


def _safe_paragraph_text(line: str) -> str:
    return html.escape(_MARKDOWN_EMPHASIS.sub("", line))


def render_pdf(
    input_path: Path,
    output_path: Path,
    *,
    period: str = "",
    source_count: int = 0,
    data_pack_path: Path | None = None,
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    navy = colors.HexColor("#0B2028")
    ink = colors.HexColor("#132A32")
    mint = colors.HexColor("#13C7A2")
    lime = colors.HexColor("#C8F24B")
    coral = colors.HexColor("#FF7A5B")
    mist = colors.HexColor("#F2F8F6")
    slate = colors.HexColor("#62777B")

    class ChartPanel(Flowable):
        """A compact chart drawn from deterministic numerical data only."""

        def __init__(self, title: str, caption: str, entries: tuple[tuple[str, float | None, str], ...], accent: Any) -> None:
            super().__init__()
            self.title = title
            self.caption = caption
            self.entries = entries
            self.accent = accent
            self.width = 178 * mm
            self.height = (38 + 17 * len(entries)) * mm

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            self.width = available_width
            return available_width, self.height

        def draw(self) -> None:
            canvas = self.canv
            width, height = self.width, self.height
            canvas.saveState()
            canvas.setFillColor(mist)
            canvas.roundRect(0, 0, width, height, 3 * mm, fill=1, stroke=0)
            canvas.setFont("QiqiSans", 12)
            canvas.setFillColor(navy)
            canvas.drawString(6 * mm, height - 10 * mm, self.title)
            canvas.setFont("QiqiSans", 8)
            canvas.setFillColor(slate)
            canvas.drawString(6 * mm, height - 16 * mm, self.caption)
            available = width - 74 * mm
            visible = [entry[1] for entry in self.entries if entry[1] is not None]
            maximum = max(visible) if visible else 1
            for index, (label, value, value_label) in enumerate(self.entries):
                y = height - (27 + index * 17) * mm
                canvas.setFont("QiqiSans", 9)
                canvas.setFillColor(ink)
                canvas.drawString(6 * mm, y + 1 * mm, label[:14])
                canvas.setFillColor(colors.HexColor("#DCE8E5"))
                canvas.roundRect(48 * mm, y, available, 6 * mm, 2 * mm, fill=1, stroke=0)
                if value is not None:
                    canvas.setFillColor(self.accent)
                    canvas.roundRect(48 * mm, y, max(2 * mm, available * value / maximum), 6 * mm, 2 * mm, fill=1, stroke=0)
                canvas.setFont("QiqiSans", 8)
                canvas.setFillColor(slate)
                canvas.drawRightString(width - 6 * mm, y + 1 * mm, value_label)
            canvas.restoreState()

    def metric_card(label: str, value: str, note: str, accent: Any) -> Table:
        cell = Table(
            [[Paragraph(value, ParagraphStyle("metric", parent=body, fontSize=21, leading=25, textColor=navy))], [Paragraph(label, caption)], [Paragraph(note, micro)]],
            colWidths=[56 * mm],
        )
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), mist), ("LINEABOVE", (0, 0), (-1, 0), 4, accent),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ]))
        return cell

    pdfmetrics.registerFont(TTFont("QiqiSans", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
    title, sections = parse_markdown(input_path.read_text(encoding="utf-8"))
    visual_data = load_account_visual_data(data_pack_path or infer_data_pack_path(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    hero = ParagraphStyle("hero", parent=styles["Normal"], fontName="QiqiSans", fontSize=25, leading=33, textColor=colors.white)
    subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontName="QiqiSans", fontSize=9, leading=14, textColor=colors.HexColor("#C7DAD6"))
    section = ParagraphStyle("section", parent=styles["Normal"], fontName="QiqiSans", fontSize=16, leading=22, textColor=navy, spaceAfter=5)
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="QiqiSans", fontSize=9.5, leading=15, textColor=ink, alignment=TA_LEFT)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, firstLineIndent=-8, spaceAfter=4)
    caption = ParagraphStyle("caption", parent=styles["Normal"], fontName="QiqiSans", fontSize=8, leading=11, textColor=slate)
    micro = ParagraphStyle("micro", parent=caption, fontSize=7.2, leading=10, textColor=slate)

    evidence_lines = sum(1 for item in sections for line in item.lines if line)
    meta = "Markdown 正文可视化版" if visual_data is None else "Markdown 正文 + 同次 data-pack.json 可复算图表"
    story: list[Any] = []
    cover = Table(
        [[Paragraph(_safe_paragraph_text(title), hero), Paragraph(f"研究时间<br/>{_safe_paragraph_text(period or '以正文为准')}<br/><br/>{meta}", subtitle)]],
        colWidths=[128 * mm, 50 * mm],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy), ("BOX", (0, 0), (-1, -1), 0, navy), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 12 * mm), ("RIGHTPADDING", (1, 0), (1, 0), 10 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 13 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 13 * mm),
    ]))
    story.extend([cover, Spacer(1, 6 * mm)])
    story.extend([Table([[
        metric_card("研究章节", str(len(sections)), "来自 Markdown 正文", mint),
        metric_card("研究要点", str(evidence_lines), "来自 Markdown 正文", lime),
        metric_card("信息源", str(source_count) if source_count else "已记录", "以证据包回查", coral),
    ]], colWidths=[59.3 * mm] * 3), Spacer(1, 7 * mm)])

    if visual_data:
        account_label = visual_data.account_name or "账号样本"
        account_rows = [
            [Paragraph("数据快照", section)],
            [Paragraph(f"账号：{_safe_paragraph_text(account_label)}。下列数字均来自同次 research data-pack；它们描述公开样本，不代表平台全量曝光或商业转化。", body)],
            [Table([[
                metric_card("样本作品", str(visual_data.sample_size), "本次采集范围", mint),
                metric_card("账号粉丝", _format_number(visual_data.followers), "公开主页字段", lime),
                metric_card("播放中位数", _format_number(visual_data.views_median), "样本内，不是曝光量", coral),
            ]], colWidths=[59.3 * mm] * 3)],
        ]
        account_block = Table(account_rows, colWidths=[178 * mm])
        account_block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("LINEBEFORE", (0, 0), (0, -1), 3, mint),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E6E2")), ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm), ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ]))
        story.extend([account_block, Spacer(1, 6 * mm)])

    for index, item in enumerate(sections):
        normalized_title = item.title.replace(" ", "")
        chart: Flowable | None = None
        if visual_data and "爆款规律" in normalized_title and (visual_data.high_median is not None or visual_data.low_median is not None):
            chart = ChartPanel("样本高低表现对照", "按样本播放量排序取高、低四分位；用于比较，不等同于平台推荐机制。", (
                ("高表现组中位数", visual_data.high_median, _format_number(visual_data.high_median)),
                ("低表现组中位数", visual_data.low_median, _format_number(visual_data.low_median)),
            ), coral)
        elif visual_data and "内容策略" in normalized_title and visual_data.pillars:
            entries = tuple((pillar.label, float(pillar.count), f"{pillar.count} 条 / 播放中位 {_format_number(pillar.views_median)}") for pillar in visual_data.pillars[:5])
            chart = ChartPanel("内容支柱样本分布", "柱长代表样本条数；右侧展示该支柱的样本播放中位数。", entries, mint)
        elif visual_data and "受众需求" in normalized_title:
            chart = ChartPanel("公开评论证据覆盖", "评论是公开可见的需求线索，不代表全部观众；未采集到的评论不作推断。", (
                ("评论样本", float(visual_data.comment_count), f"{visual_data.comment_count} 条"),
                ("覆盖作品", float(visual_data.comment_post_count), f"{visual_data.comment_post_count} 条作品"),
            ), lime)

        rows: list[list[Any]] = [[Paragraph(f"{index + 1:02d}  {_safe_paragraph_text(item.title)}", section)]]
        if chart:
            rows.append([chart])
        rows.extend([ [Paragraph(f"- {_safe_paragraph_text(line)}", bullet)] for line in item.lines ])
        block = Table(rows, colWidths=[178 * mm], repeatRows=1)
        block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("LINEBEFORE", (0, 0), (0, -1), 3, mint if index % 2 == 0 else lime),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E6E2")), ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm), ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ]))
        story.extend([block, Spacer(1, 4 * mm)])

    def page(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0, 0, A4[0], 7 * mm, fill=1, stroke=0)
        canvas.setFont("QiqiSans", 8)
        canvas.setFillColor(slate)
        canvas.drawString(16 * mm, 12 * mm, "qiqi-media-research | evidence-bound visual report")
        canvas.drawRightString(A4[0] - 16 * mm, 12 * mm, str(document.page))
        canvas.restoreState()

    document = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=20 * mm)
    document.build(story, onFirstPage=page, onLaterPages=page)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a bright visual PDF from an evidence-bound Markdown report")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--period", default="")
    parser.add_argument("--source-count", type=int, default=0)
    parser.add_argument("--data-pack", type=Path, help="Same-run analysis/data-pack.json; inferred beside reports/ when omitted")
    args = parser.parse_args()
    render_pdf(args.input, args.out, period=args.period, source_count=args.source_count, data_pack_path=args.data_pack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
