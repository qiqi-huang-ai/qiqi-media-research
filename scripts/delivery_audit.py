"""Audit whether a research run is safe to present as a data-backed deliverable."""

from dataclasses import asdict, dataclass
import argparse
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
    ledger_path = root / "analysis" / "findings.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.is_file() else {}
    mode = brief.get("mode")
    entity = "trends" if mode == "trend-scan" else "accounts" if mode == "competitor-discovery" else "posts"
    normalized_path = root / "normalized" / f"{entity}.jsonl"
    raw_files = list(root.rglob("raw/*/*.json"))
    add("research_brief", brief_path.is_file(), "brief.json 已生成" if brief_path.is_file() else "缺少 brief.json")
    add("manifest", manifest_path.is_file(), "manifest.json 已生成" if manifest_path.is_file() else "缺少 manifest.json")
    add("raw_evidence", bool(raw_files), f"原始响应 {len(raw_files)} 份")
    add("normalized_data", normalized_path.is_file(), f"{entity}.jsonl 已生成" if normalized_path.is_file() else f"缺少 {entity}.jsonl")
    add("report", report_path.is_file(), "Markdown 报告已生成" if report_path.is_file() else "缺少 Markdown 报告")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else []
    valid_ledger = bool(ledger) and all(item.get("evidence_ids") and item.get("evidence_class") for item in ledger)
    add("evidence_ledger", valid_ledger, f"内部证据记录 {len(ledger)} 条" if ledger_path.is_file() else "缺少 analysis/findings.json")

    if entity == "posts":
        quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {}
        total = int(quality.get("total", 0))
        complete = int(quality.get("complete_identity", 0))
        duplicate_count = int(quality.get("duplicate_post_ids", 0))
        missing_ratio = float(quality.get("missing_metric_ratio", 1.0))
        add("identity_fields", total > 0 and complete == total, f"身份字段完整 {complete}/{total}")
        add("duplicate_posts", duplicate_count == 0, f"重复作品 {duplicate_count} 条")
        add("metric_coverage", total > 0 and missing_ratio <= 0.4, f"指标缺失率 {missing_ratio:.1%}")

    records: list[dict] = []
    zero_views = 0
    source_urls: list[str] = []
    if normalized_path.is_file():
        for line in normalized_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            records.append(record)
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

    requirements = set(brief.get("requirements") or [])
    report_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    raw_names = [path.name for path in raw_files]
    if "time-window" in requirements:
        add("required_time_window", bool(brief.get("start_at") and brief.get("end_at") and filter_path.is_file()), "时间边界与过滤记录齐全")
    if "post-metadata" in requirements:
        identity_check = next((item for item in checks if item.name == "identity_fields"), None)
        links_check = next((item for item in checks if item.name == "source_links"), None)
        add("required_post_metadata", bool(identity_check and identity_check.passed and links_check and links_check.passed), "作品身份字段与原始链接齐全")
    if "visible-metrics" in requirements:
        missing_views = sum(record.get("views") is None for record in records)
        unverified_douyin_views = sum(record.get("platform") == "douyin" and record.get("views_source") != "statistics" for record in records)
        add("required_visible_metrics", bool(records) and missing_views == 0 and unverified_douyin_views == 0, f"缺播放量 {missing_views} 条；抖音非独立统计来源 {unverified_douyin_views} 条")
    if "comment-insights" in requirements:
        has_comments = any(name.startswith("comments-") for name in raw_names)
        add("required_comment_insights", has_comments and _meaningful_section(report_text, "评论需求"), "评论原始响应和评论需求结论均存在")
    if "trend-distinction" in requirements:
        add("required_trend_distinction", _meaningful_section(report_text, "高表现内容") and _meaningful_section(report_text, "赛道与趋势"), "高表现个案与共同趋势已分别呈现")
    if "content-ideas" in requirements:
        add("required_content_ideas", _meaningful_section(report_text, "建议选题与下一步"), "选题章节包含非占位内容")
    if "text-hook-structure" in requirements:
        has_boundary = "初步" in report_text or "基于标题/文案" in report_text or "待视频画面复核" in report_text
        add("required_text_hook_structure", "开头钩子判断：" in report_text and "内容结构判断：" in report_text and has_boundary, "文本层钩子/结构及证据边界已呈现")
    if "account-profile" in requirements:
        account_path = root / "normalized" / "accounts.jsonl"
        add("required_account_profile", account_path.is_file() and "账号事实：" in report_text, "账号资料已标准化并进入报告")
    if "account-baseline" in requirements:
        add("required_account_baseline", "表现基线：" in report_text, "账号样本表现基线已计算")
    if "account-patterns" in requirements:
        add("required_account_patterns", "标题/文案模式：" in report_text, "标题/文案模式已按样本统计")
    if "top-bottom-comparison" in requirements:
        add("required_top_bottom_comparison", "分组对照：" in report_text, "高表现与低表现样本已对照")
    if "actionable-recommendations" in requirements:
        add("required_actionable_recommendations", "可执行建议：" in report_text, "建议已连接到样本基线和模式")
    if "mature-mode-report" in requirements:
        required_sections = {
            "niche-discovery": ("核心发现", "赛道与趋势", "高表现内容", "建议选题与下一步"),
            "trend-scan": ("赛道与趋势", "高表现内容", "建议选题与下一步"),
            "competitor-discovery": ("对标账号", "建议选题与下一步"),
            "account-audit": ("核心发现", "对标账号", "高表现内容", "评论需求", "建议选题与下一步"),
            "viral-breakdown": ("核心发现", "高表现内容", "评论需求", "建议选题与下一步"),
            "comment-mining": ("评论需求", "建议选题与下一步"),
            "content-gap": ("高表现内容", "内容空白", "建议选题与下一步"),
            "cross-platform": ("核心发现", "赛道与趋势", "建议选题与下一步"),
            "brand-product": ("高表现内容", "评论需求", "建议选题与下一步"),
            "idea-generation": ("高表现内容", "建议选题与下一步"),
            "market-map": ("赛道与趋势", "对标账号", "机会排序", "建议选题与下一步"),
        }.get(mode, ())
        missing_sections = [title for title in required_sections if not _meaningful_section(report_text, title)]
        add("required_mature_mode_report", not missing_sections, "模式核心问题均已回答" if not missing_sections else f"缺少成熟分析章节：{', '.join(missing_sections)}")

    essential = {"research_brief", "manifest", "raw_evidence", "normalized_data", "report", "evidence_ledger", "identity_fields", "duplicate_posts", "zero_view_semantics", "source_links", "visible_metrics", "time_filter"}
    essential.update(check.name for check in checks if check.name.startswith("required_"))
    failed_essential = [check for check in checks if check.name in essential and not check.passed]
    status = "failed" if failed_essential else "ready" if all(check.passed for check in checks) else "ready_with_caveats"
    return DeliveryAudit(status, tuple(checks))


def _meaningful_section(report_text: str, title: str) -> bool:
    marker = f"## {title}"
    if marker not in report_text:
        return False
    content = report_text.split(marker, 1)[1].split("\n## ", 1)[0]
    return bool(content.strip()) and "未形成有充分证据的结论" not in content


def write_delivery_audit(root: str | Path, audit: DeliveryAudit) -> Path:
    target = Path(root) / "analysis" / "delivery-audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a qiqi-media-research delivery")
    parser.add_argument("root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit_delivery(args.root, args.report)
    target = write_delivery_audit(args.root, result)
    print(f"{result.status}: {target}")
    for check in result.checks:
        print(f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}")
    return 2 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
