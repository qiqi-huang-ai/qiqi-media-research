"""Bounded collection planning and evidence manifest helpers."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable


APPROVAL_THRESHOLD = 20
_SECRET_NAMES = {"tikhub_api_key", "api_key", "authorization", "token", "access_token"}


@dataclass(frozen=True, slots=True)
class CollectionPlan:
    search_pages: int = 0
    accounts: int = 0
    posts_per_account_pages: int = 0
    post_details: int = 0
    comment_pages: int = 0
    trend_pages: int = 0
    statistics: int = 0


def estimate_requests(plan: CollectionPlan) -> int:
    values = asdict(plan)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values.values()):
        raise ValueError("collection plan counts must be non-negative integers")
    return (
        plan.search_pages
        + plan.accounts
        + plan.accounts * plan.posts_per_account_pages
        + plan.post_details
        + plan.comment_pages
        + plan.trend_pages
        + plan.statistics
    )


def require_expansion_approval(request_count: int) -> bool:
    if request_count < 0:
        raise ValueError("request_count cannot be negative")
    return request_count > APPROVAL_THRESHOLD


def cost_notice(platform: str, plan: CollectionPlan) -> str:
    total = estimate_requests(plan)
    families = []
    if plan.search_pages:
        families.append(f"search={plan.search_pages}")
    if plan.accounts:
        families.append(f"account={plan.accounts}")
    if plan.posts_per_account_pages:
        families.append(f"account_posts={plan.accounts * plan.posts_per_account_pages}")
    if plan.post_details:
        families.append(f"post_detail={plan.post_details}")
    if plan.comment_pages:
        families.append(f"comments={plan.comment_pages}")
    if plan.trend_pages:
        families.append(f"trends={plan.trend_pages}")
    if plan.statistics:
        families.append(f"statistics={plan.statistics}")
    suffix = "；抖音 Search 单独计费" if platform == "douyin" and plan.search_pages else ""
    return f"计划调用 {total} 次（{', '.join(families) or '无调用'}）{suffix}。实际单价请以 TikHub 当前页面为准。"


def _safe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in parameters.items() if key.lower() not in _SECRET_NAMES}


def write_manifest(
    root: str | Path,
    *,
    platform: str,
    operation: str,
    parameters: dict[str, Any],
    request_count: int,
    raw_paths: Iterable[str | Path],
    failures: Iterable[str],
) -> Path:
    target = Path(root) / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "platform": platform,
        "operation": operation,
        "parameters": _safe_parameters(parameters),
        "request_count": request_count,
        "raw_paths": [str(path) for path in raw_paths],
        "collected_at": datetime.now(UTC).isoformat(),
        "failures": list(failures),
    }
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
