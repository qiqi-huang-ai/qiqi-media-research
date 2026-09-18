"""Unified bounded entry point for the eleven research modes.

This module owns routing and planning. Platform adapters remain responsible for
endpoint details; semantic interpretation remains evidence-bound report work.
"""

from dataclasses import dataclass

from scripts.collect import CollectionPlan, cost_notice, estimate_requests


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
    sample_pages: int = 1
    comment_pages: int = 0


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    mode: str
    platform: str
    operations: tuple[str, ...]
    request_count: int
    cost_notice: str


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
