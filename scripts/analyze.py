"""Deterministic, platform-safe research calculations."""

from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Mapping, Sequence

from scripts.models import Comment, Post


@dataclass(slots=True)
class PostMetrics:
    platform: str
    post_id: str
    engagement_rate: float | None
    view_follower_ratio: float | None
    relative_performance: float | None
    relative_basis: str | None
    platform_percentile: float | None


def _positive(value: int | None) -> bool:
    return value is not None and value > 0


def compute_post_metrics(posts: Sequence[Post]) -> list[PostMetrics]:
    groups: dict[tuple[str, str], list[Post]] = defaultdict(list)
    for post in posts:
        groups[(post.platform, post.author_id or "__unknown__")].append(post)

    basis_by_post: dict[int, tuple[str | None, float | None, float | None]] = {}
    pools: dict[tuple[str, str], list[float]] = defaultdict(list)
    for group in groups.values():
        view_values = [float(post.views) for post in group if _positive(post.views)]
        basis = "views" if view_values else "likes"
        values = view_values if view_values else [float(post.likes) for post in group if _positive(post.likes)]
        baseline = median(values) if values else None
        for post in group:
            raw_value = post.views if basis == "views" else post.likes
            relative = float(raw_value) / baseline if _positive(raw_value) and baseline else None
            selected_basis = basis if baseline is not None else None
            basis_by_post[id(post)] = (selected_basis, relative, float(raw_value) if _positive(raw_value) else None)
            if selected_basis and _positive(raw_value):
                pools[(post.platform, selected_basis)].append(float(raw_value))

    results = []
    for post in posts:
        basis, relative, raw_value = basis_by_post[id(post)]
        engagement = None
        if _positive(post.views):
            engagement = sum(value or 0 for value in (post.likes, post.comments, post.shares)) / post.views
        follower_ratio = post.views / post.followers if _positive(post.views) and _positive(post.followers) else None
        percentile = None
        if basis and raw_value is not None:
            pool = pools[(post.platform, basis)]
            percentile = 100.0 * sum(value <= raw_value for value in pool) / len(pool)
        results.append(PostMetrics(post.platform, post.post_id, engagement, follower_ratio, relative, basis, percentile))
    return results


def count_comment_signals(
    comments: Iterable[Comment], signals: Mapping[str, Iterable[str]]
) -> dict[str, int]:
    """Count comments matching each explicitly supplied keyword group once."""

    normalized = {name: tuple(word.casefold() for word in words) for name, words in signals.items()}
    counts = {name: 0 for name in normalized}
    for comment in comments:
        text = (comment.text or "").casefold()
        for name, words in normalized.items():
            if any(word and word in text for word in words):
                counts[name] += 1
    return counts
