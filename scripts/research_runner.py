"""Unified bounded entry point for the eleven research modes.

This module owns routing and planning. Platform adapters remain responsible for
endpoint details; semantic interpretation remains evidence-bound report work.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
import argparse

from scripts.analyze import compute_post_metrics
from scripts.collect import CollectionPlan, cost_notice, estimate_requests, write_manifest
from scripts.normalize import write_normalized
from scripts.raw_store import RawStore
from scripts.report import Finding, ResearchReport, render_report


MODES = (
    "niche-discovery",
    "trend-scan",
    "competitor-discovery",
    "account-audit",
    "viral-breakdown",
    "comment-mining",
    "content-gap",
    "cross-platform",
    "brand-product",
    "idea-generation",
    "market-map",
)
PLATFORMS = {"douyin", "xiaohongshu"}


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    mode: str
    platform: str
    query: str
    secondary_platform: str | None = None
    entity_id: str | None = None
    sample_pages: int = 1
    comment_pages: int = 0


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    mode: str
    platform: str
    operations: tuple[str, ...]
    request_count: int
    cost_notice: str


@dataclass(frozen=True, slots=True)
class ResearchExecution:
    plan: ResearchPlan
    raw_paths: tuple[Path, ...]
    normalized_path: Path
    report_path: Path
    manifest_path: Path | None = None


_MODE_OPERATIONS: dict[str, tuple[str, ...]] = {
    "niche-discovery": ("search",),
    "trend-scan": ("trends",),
    "competitor-discovery": ("account_search",),
    "account-audit": ("account", "account_posts"),
    "viral-breakdown": ("post_detail", "comments"),
    "comment-mining": ("post_detail", "comments"),
    "content-gap": ("search",),
    "cross-platform": ("search",),
    "brand-product": ("search",),
    "idea-generation": ("search",),
    "market-map": ("search",),
}


def plan_request(request: ResearchRequest) -> ResearchPlan:
    if request.mode not in MODES:
        raise ValueError(f"unsupported research mode: {request.mode}")
    if request.platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {request.platform}")
    if request.mode == "trend-scan" and request.platform != "douyin":
        raise ValueError("trend-scan is currently available only for douyin")
    if not request.query.strip():
        raise ValueError("query cannot be empty")
    if request.mode == "cross-platform":
        if request.secondary_platform not in PLATFORMS or request.secondary_platform == request.platform:
            raise ValueError("cross-platform requires two platforms")
    if request.sample_pages < 1 or request.sample_pages > 3:
        raise ValueError("sample_pages must be between 1 and 3")
    if request.comment_pages < 0 or request.comment_pages > 1:
        raise ValueError("comment_pages must be between 0 and 1")

    operations = _MODE_OPERATIONS[request.mode]
    plan = CollectionPlan(
        search_pages=request.sample_pages * 2 if request.mode == "cross-platform" else (request.sample_pages if "search" in operations else 0),
        accounts=1 if any(item in operations for item in ("account", "account_search")) else 0,
        posts_per_account_pages=1 if "account_posts" in operations else 0,
        post_details=1 if "post_detail" in operations else 0,
        comment_pages=request.comment_pages if "comments" in operations else 0,
        trend_pages=1 if "trends" in operations else 0,
    )
    # A comment operation defaults to one low-cost page when explicitly requested.
    if "comments" in operations and plan.comment_pages == 0:
        plan = CollectionPlan(**{**plan.__dict__, "comment_pages": 1}) if hasattr(plan, "__dict__") else CollectionPlan(
            search_pages=plan.search_pages,
            accounts=plan.accounts,
            posts_per_account_pages=plan.posts_per_account_pages,
            post_details=plan.post_details,
            comment_pages=1,
            trend_pages=plan.trend_pages,
        )
    count = estimate_requests(plan)
    return ResearchPlan(request.mode, request.platform, operations, count, cost_notice(request.platform, plan))


def execute_request(request: ResearchRequest, *, adapter: Any, output_root: str | Path, secondary_adapter: Any | None = None) -> ResearchExecution:
    """Execute the bounded keyword-search slice of a research request.

    Modes needing an account or post identifier are intentionally not guessed;
    callers must supply a specialized adapter invocation in a later execution
    layer. This first slice is enough for low-cost niche/trend/gap research.
    """
    plan = plan_request(request)
    if request.mode in {"viral-breakdown", "comment-mining"}:
        if not request.entity_id:
            raise ValueError("entity_id is required for this research mode")
        result = _execute_post_mode(request, plan, adapter, output_root)
    elif request.mode == "account-audit":
        if not request.entity_id:
            raise ValueError("entity_id is required for this research mode")
        result = _execute_account_mode(request, plan, adapter, output_root)
    elif request.mode == "cross-platform":
        if secondary_adapter is None:
            raise ValueError("cross-platform execution requires two adapters")
        result = _execute_cross_platform(request, plan, adapter, secondary_adapter, output_root)
    elif request.mode == "trend-scan":
        result = _execute_trend_mode(request, plan, adapter, output_root)
    elif request.mode == "competitor-discovery":
        result = _execute_competitor_mode(request, plan, adapter, output_root)
    elif request.mode in {"content-gap", "brand-product", "idea-generation", "market-map"}:
        result = _execute_specialized_keyword_mode(request, plan, adapter, output_root)
    elif "search" in plan.operations:
        result = _execute_keyword_mode(request, plan, adapter, output_root)
    else:
        raise ValueError(f"mode {request.mode} requires an explicit entity and is not keyword-executable")
    manifest = write_manifest(
        output_root,
        platform=request.platform,
        operation=request.mode,
        parameters={
            "query": request.query,
            "entity_id": request.entity_id,
            "secondary_platform": request.secondary_platform,
            "sample_pages": request.sample_pages,
            "comment_pages": request.comment_pages,
        },
        request_count=len(result.raw_paths),
        raw_paths=result.raw_paths,
        failures=(),
    )
    return replace(result, manifest_path=manifest)


def _execute_keyword_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    posts, raw_paths = _search_posts(request, adapter, store)
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary=f"关键词“{request.query}”完成低成本样本研究。",
        task=f"研究模式：{request.mode}；查询：{request.query}",
        coverage=f"{len(posts)} 条作品，最多 {request.sample_pages} 页搜索，原始证据已保存。",
        findings=[Finding(
            text=f"样本中 {sum(metric.relative_performance is not None for metric in metrics)} 条作品可计算账号内相对表现。",
            evidence_ids=[f"post:{post.post_id}" for post in posts[:3]],
            evidence_class="calculated",
        )] if posts else [],
        limitations=["仅执行关键词搜索切片，未自动扩展账号、评论或详情调用。"],
        confidence="low" if len(posts) < 10 else "medium",
    )
    report_path = root / "reports" / f"{request.mode}-{request.platform}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _execute_post_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    if request.platform == "douyin":
        post = adapter.get_post(aweme_id=request.entity_id)
        comments_page = adapter.get_comments(request.entity_id) if "comments" in plan.operations else None
    else:
        post = adapter.get_post(note_id=request.entity_id)
        comments_page = adapter.get_comments(note_id=request.entity_id) if "comments" in plan.operations else None
    post_raw = store.save(request.platform, "post-detail", _adapter_last_raw(adapter, "post detail"))
    comments = comments_page.items if comments_page else []
    raw_paths = [post_raw]
    if comments_page:
        comments_raw = store.save(request.platform, "comments", comments_page.raw)
        raw_paths.append(comments_raw)
    post.raw_path = str(post_raw)
    normalized = write_normalized(root, "posts", [post])
    metrics = compute_post_metrics([post])[0]
    evidence = [f"post:{post.post_id}"]
    if comments:
        evidence.append(f"comment:{comments[0].comment_id}")
    finding_text = f"作品 {post.post_id} 的互动率为 {metrics.engagement_rate:.4f}。" if metrics.engagement_rate is not None else f"作品 {post.post_id} 缺少足够播放数据，未计算互动率。"
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary="完成一条作品的详情与评论低成本研究。",
        task=f"研究模式：{request.mode}；作品：{request.entity_id}",
        coverage=f"1 条作品、{len(comments)} 条评论。",
        findings=[Finding(text=finding_text, evidence_ids=evidence, evidence_class="calculated")],
        limitations=["仅执行单作品切片，未扩展账号或跨平台样本。"],
        confidence="low",
    )
    report_path = root / "reports" / f"{request.mode}-{request.platform}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _execute_account_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    if request.platform == "douyin":
        account = adapter.get_account(request.entity_id)
        posts_page = adapter.get_account_posts(request.entity_id, cursor="0")
    else:
        account = adapter.get_account(user_id=request.entity_id)
        posts_page = adapter.get_account_posts(user_id=request.entity_id, cursor="")
    account_raw = store.save(request.platform, "account", _adapter_last_raw(adapter, "account"))
    posts_raw = store.save(request.platform, "account-posts", posts_page.raw)
    posts = list(posts_page.items)
    for post in posts:
        post.raw_path = str(posts_raw)
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    report = ResearchReport(
        title=f"{request.platform} account-audit",
        summary=f"完成账号 {account.account_id} 的低成本公开资料审计。",
        task=f"研究模式：account-audit；账号：{request.entity_id}",
        coverage=f"1 个账号、{len(posts)} 条作品。",
        findings=[Finding(
            text=f"样本中 {sum(item.relative_performance is not None for item in metrics)} 条作品具备账号内相对表现数据。",
            evidence_ids=[f"account:{account.account_id}"] + [f"post:{post.post_id}" for post in posts[:3]],
            evidence_class="calculated",
        )],
        limitations=["仅采集一页账号作品，不代表账号全量表现。"],
        confidence="low" if len(posts) < 10 else "medium",
    )
    report_path = root / "reports" / f"account-audit-{request.platform}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, (account_raw, posts_raw), normalized, report_path)


def _execute_cross_platform(request: ResearchRequest, plan: ResearchPlan, adapter: Any, secondary_adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    first_posts, first_raw_paths = _search_posts(request, adapter, store)
    secondary_request = replace(request, platform=request.secondary_platform or "", secondary_platform=None)
    second_posts, second_raw_paths = _search_posts(secondary_request, secondary_adapter, store)
    posts = first_posts + second_posts
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    evidence = [f"post:{post.post_id}" for post in posts[:4]]
    report = ResearchReport(
        title="cross-platform research",
        summary=f"完成“{request.query}”在两个平台的一页样本对照。",
        task=f"研究模式：cross-platform；平台：{request.platform}、{request.secondary_platform}",
        coverage=f"{request.platform} {len(first_posts)} 条；{request.secondary_platform} {len(second_posts)} 条。",
        findings=[Finding(text=f"两个平台共获得 {len(metrics)} 条可分析作品，指标仍按平台分别计算。", evidence_ids=evidence, evidence_class="calculated")],
        limitations=["仅比较一页样本，不直接比较平台原始热度分。"],
        confidence="low",
    )
    report_path = root / "reports" / "cross-platform.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, tuple(first_raw_paths + second_raw_paths), normalized, report_path)


def _execute_trend_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    trends_page = adapter.get_trends()
    raw_path = store.save(request.platform, "trends", trends_page.raw)
    trend_path = write_normalized(root, "trends", trends_page.items)
    evidence = [f"trend:{item.trend_id}" for item in trends_page.items[:5]]
    report = ResearchReport(
        title=f"{request.platform} trend-scan",
        summary=f"完成“{request.query}”的低成本趋势扫描。",
        task=f"研究模式：trend-scan；主题：{request.query}",
        coverage=f"{len(trends_page.items)} 条趋势项。",
        findings=[Finding(text=f"当前样本包含 {len(trends_page.items)} 条平台趋势项，需结合关键词搜索判断持续性。", evidence_ids=evidence or [f"raw:{raw_path.name}"], evidence_class="observed")],
        limitations=["趋势接口样本是当前时点快照，不代表长期趋势。"],
        confidence="low",
    )
    report_path = root / "reports" / "trend-scan.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, (raw_path,), trend_path, report_path)


def _execute_competitor_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    page = adapter.search_accounts(request.query)
    raw_path = store.save(request.platform, "account-search", page.raw)
    normalized = write_normalized(root, "accounts", page.items)
    evidence = [f"account:{account.account_id}" for account in page.items[:5]]
    report = ResearchReport(
        title=f"{request.platform} competitor-discovery",
        summary=f"完成“{request.query}”的候选对标账号发现。",
        task=f"研究模式：competitor-discovery；关键词：{request.query}",
        coverage=f"{len(page.items)} 个候选账号。",
        findings=[Finding(text=f"发现 {len(page.items)} 个候选账号，需结合账号作品样本进一步筛选。", evidence_ids=evidence or [f"raw:{raw_path.name}"], evidence_class="observed")],
        limitations=["候选发现不等于对标结论；本次未自动扩展每个账号的作品。"],
        confidence="low",
    )
    report_path = root / "reports" / "competitor-discovery.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, (raw_path,), normalized, report_path)


def _execute_specialized_keyword_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    posts, raw_paths = _search_posts(request, adapter, store)
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    evidence = [f"post:{post.post_id}" for post in posts[:5]] or [f"raw:{raw_paths[0].name}"]
    labels = {
        "content-gap": ("内容空白", "供给与需求"),
        "brand-product": ("品牌/产品", "公开提及与疑问"),
        "idea-generation": ("证据化选题", "可追溯选题"),
        "market-map": ("市场结构", "账号与主题结构"),
    }
    section, analysis = labels[request.mode]
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary=f"完成“{request.query}”的{section}分析。",
        task=f"研究模式：{request.mode}；关键词：{request.query}",
        coverage=f"{len(posts)} 条搜索作品，{sum(metric.engagement_rate is not None for metric in metrics)} 条可计算互动率。",
        findings=[Finding(text=f"本次以 {analysis} 为分析框架，样本需继续扩展后再形成高置信结论。", evidence_ids=evidence, evidence_class="interpreted")],
        limitations=["当前为一页搜索样本；没有把样本外信息写成结论。"],
        confidence="low",
    )
    report_path = root / "reports" / f"{request.mode}-{request.platform}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _search_posts(request: ResearchRequest, adapter: Any, store: RawStore) -> tuple[list[Any], list[Path]]:
    cursor: str | None = "0" if request.platform == "douyin" else None
    posts: list[Any] = []
    raw_paths: list[Path] = []
    for _ in range(request.sample_pages):
        page = adapter.search_posts(request.query, cursor=cursor)
        raw_path = store.save(request.platform, "search", page.raw)
        raw_paths.append(raw_path)
        for post in page.items:
            post.raw_path = str(raw_path)
            posts.append(post)
        if not page.has_more or page.next_cursor is None:
            break
        cursor = page.next_cursor
    return posts, raw_paths


def _adapter_last_raw(adapter: Any, operation: str) -> dict[str, Any]:
    raw = getattr(adapter, "last_raw", None)
    if not isinstance(raw, dict):
        raise RuntimeError(f"adapter did not retain the raw response for {operation}")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded qiqi-media-research task")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--entity-id")
    parser.add_argument("--secondary-platform", choices=sorted(PLATFORMS))
    parser.add_argument("--sample-pages", type=int, default=1)
    parser.add_argument("--out", default="research-output")
    args = parser.parse_args()
    request = ResearchRequest(mode=args.mode, platform=args.platform, query=args.query, entity_id=args.entity_id, secondary_platform=args.secondary_platform, sample_pages=args.sample_pages)
    plan = plan_request(request)
    print(plan.cost_notice)
    if plan.request_count > 20:
        parser.error("planned calls exceed the approval threshold")
    from scripts.api_client import TikHubClient
    from adapters.douyin import DouyinAdapter
    from adapters.xiaohongshu import XiaohongshuAdapter
    client = TikHubClient()
    def make_adapter(platform: str):
        return DouyinAdapter(client) if platform == "douyin" else XiaohongshuAdapter(client)

    adapter = make_adapter(args.platform)
    secondary_adapter = make_adapter(args.secondary_platform) if args.secondary_platform else None
    result = execute_request(request, adapter=adapter, secondary_adapter=secondary_adapter, output_root=args.out)
    print(f"报告已生成：{result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
