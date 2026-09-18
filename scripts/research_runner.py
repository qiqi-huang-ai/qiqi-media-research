"""Unified bounded entry point for the eleven research modes.

This module owns routing and planning. Platform adapters remain responsible for
endpoint details; semantic interpretation remains evidence-bound report work.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.analyze import compute_post_metrics
from scripts.collect import CollectionPlan, cost_notice, estimate_requests
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


_MODE_OPERATIONS: dict[str, tuple[str, ...]] = {
    "niche-discovery": ("search", "post_detail", "comments"),
    "trend-scan": ("trends", "search"),
    "competitor-discovery": ("account_search", "account", "account_posts"),
    "account-audit": ("account", "account_posts", "post_detail"),
    "viral-breakdown": ("post_detail", "comments"),
    "comment-mining": ("comments",),
    "content-gap": ("search", "account_posts", "comments"),
    "cross-platform": ("search", "post_detail"),
    "brand-product": ("search", "comments", "account"),
    "idea-generation": ("search", "comments", "post_detail"),
    "market-map": ("search", "account_search", "account_posts"),
}


def plan_request(request: ResearchRequest) -> ResearchPlan:
    if request.mode not in MODES:
        raise ValueError(f"unsupported research mode: {request.mode}")
    if request.platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {request.platform}")
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
        search_pages=request.sample_pages if "search" in operations else 0,
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


def execute_request(request: ResearchRequest, *, adapter: Any, output_root: str | Path) -> ResearchExecution:
    """Execute the bounded keyword-search slice of a research request.

    Modes needing an account or post identifier are intentionally not guessed;
    callers must supply a specialized adapter invocation in a later execution
    layer. This first slice is enough for low-cost niche/trend/gap research.
    """
    plan = plan_request(request)
    if request.mode in {"viral-breakdown", "comment-mining"}:
        if not request.entity_id:
            raise ValueError("entity_id is required for this research mode")
        return _execute_post_mode(request, plan, adapter, output_root)
    if request.mode == "account-audit":
        if not request.entity_id:
            raise ValueError("entity_id is required for this research mode")
        return _execute_account_mode(request, plan, adapter, output_root)
    if "search" not in plan.operations:
        raise ValueError(f"mode {request.mode} requires an explicit entity and is not keyword-executable")
    if request.mode == "cross-platform":
        raise ValueError("cross-platform execution requires two adapters; use plan_request first")

    root = Path(output_root)
    store = RawStore(root)
    page = adapter.search_posts(request.query, cursor="0")
    raw_path = store.save(request.platform, "search", page.raw)
    posts = list(page.items)
    for post in posts:
        post.raw_path = str(raw_path)
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary=f"关键词“{request.query}”完成一页低成本样本研究。",
        task=f"研究模式：{request.mode}；查询：{request.query}",
        coverage=f"{len(posts)} 条作品，1 页搜索，原始证据已保存。",
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
    return ResearchExecution(plan, (raw_path,), normalized, report_path)


def _execute_post_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    if request.platform == "douyin":
        post = adapter.get_post(aweme_id=request.entity_id)
        comments_page = adapter.get_comments(request.entity_id) if "comments" in plan.operations else None
    else:
        post = adapter.get_post(note_id=request.entity_id)
        comments_page = adapter.get_comments(note_id=request.entity_id) if "comments" in plan.operations else None
    post_raw = store.save(request.platform, "post-detail", {"post_id": post.post_id, "source_url": post.source_url})
    comments = comments_page.items if comments_page else []
    if comments_page:
        store.save(request.platform, "comments", comments_page.raw)
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
    raw_paths = tuple(root.glob("raw/*/*.json"))
    return ResearchExecution(plan, raw_paths, normalized, report_path)


def _execute_account_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    account = adapter.get_account(request.entity_id)
    posts_page = adapter.get_account_posts(request.entity_id, cursor="0")
    account_raw = store.save(request.platform, "account", {"account_id": account.account_id, "name": account.name})
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
