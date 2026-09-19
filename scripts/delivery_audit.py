"""Audit whether a research run is safe to present as a data-backed deliverable."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DeliveryCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DeliveryAudit:
    status: str
    checks: tuple[DeliveryCheck, ...]


def audit_delivery(root: str | Path, report_path: str | Path) -> DeliveryAudit:
    root = Path(root)
    report_path = Path(report_path)
    checks: list[DeliveryCheck] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(DeliveryCheck(name, passed, detail))

    brief_path = root / "brief.json"
    manifest_path = root / "manifest.json"
    quality_path = root / "analysis" / "data-quality.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.is_file() else {}
    mode = brief.get("mode")
    entity = "trends" if mode == "trend-scan" else "accounts" if mode == "competitor-discovery" else "posts"
    normalized_path = root / "normalized" / f"{entity}.jsonl"
    raw_files = list((root / "raw").glob("*/*.json")) if (root / "raw").exists() else []
    add("research_brief", brief_path.is_file(), "brief.json 已生成" if brief_path.is_file() else "缺少 brief.json")
    add("manifest", manifest_path.is_file(), "manifest.json 已生成" if manifest_path.is_file() else "缺少 manifest.json")
    add("raw_evidence", bool(raw_files), f"原始响应 {len(raw_files)} 份")
    add("normalized_data", normalized_path.is_file(), f"{entity}.jsonl 已生成" if normalized_path.is_file() else f"缺少 {entity}.jsonl")
    add("report", report_path.is_file(), "Markdown 报告已生成" if report_path.is_file() else "缺少 Markdown 报告")

    if entity == "posts":
        quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {}
        total = int(quality.get("total", 0))
        complete = int(quality.get("complete_identity", 0))
        duplicate_count = int(quality.get("duplicate_post_ids", 0))
        missing_ratio = float(quality.get("missing_metric_ratio", 1.0))
        add("identity_fields", total > 0 and complete == total, f"身份字段完整 {complete}/{total}")
        add("duplicate_posts", duplicate_count == 0, f"重复作品 {duplicate_count} 条")
        add("metric_coverage", total > 0 and missing_ratio <= 0.4, f"指标缺失率 {missing_ratio:.1%}")

    zero_views = 0
    source_urls: list[str] = []
    if normalized_path.is_file():
        for line in normalized_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            zero_views += record.get("views") == 0 and record.get("views_source") != "statistics"
            if record.get("source_url"):
                source_urls.append(str(record["source_url"]))
    add("zero_view_semantics", zero_views == 0, f"错误零播放记录 {zero_views} 条")
    if entity == "posts" and report_path.is_file():
        report_text = report_path.read_text(encoding="utf-8")
        missing_links = sum(url not in report_text for url in source_urls)
        detail_rows = report_text.count("可见数据：")
        add("source_links", bool(source_urls) and missing_links == 0, f"报告缺少 {missing_links} 条原始链接")
        add("visible_metrics", detail_rows >= len(source_urls), f"作品指标行 {detail_rows}/{len(source_urls)}")

    has_bounds = bool(brief.get("start_at") or brief.get("end_at"))
    filter_path = root / "analysis" / "search-filter.json"
    add("time_filter", not has_bounds or filter_path.is_file(), "已记录时间过滤" if has_bounds and filter_path.is_file() else ("任务未要求时间边界" if not has_bounds else "缺少时间过滤记录"))

    essential = {"research_brief", "manifest", "raw_evidence", "normalized_data", "report", "identity_fields", "duplicate_posts", "zero_view_semantics", "source_links", "visible_metrics", "time_filter"}
    failed_essential = [check for check in checks if check.name in essential and not check.passed]
    status = "failed" if failed_essential else "ready" if all(check.passed for check in checks) else "ready_with_caveats"
    return DeliveryAudit(status, tuple(checks))


def write_delivery_audit(root: str | Path, audit: DeliveryAudit) -> Path:
    target = Path(root) / "analysis" / "delivery-audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
