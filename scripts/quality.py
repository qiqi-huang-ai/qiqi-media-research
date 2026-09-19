"""Field-level data quality checks for normalized public post records."""

from dataclasses import asdict, dataclass
from collections import Counter
import json
from pathlib import Path
from typing import Iterable


REQUIRED_POST_FIELDS = ("post_id", "source_url", "author_name", "text", "published_at")
METRIC_FIELDS = ("views", "likes", "comments", "shares", "saves")


@dataclass(frozen=True, slots=True)
class PostQuality:
    total: int
    complete_identity: int
    missing_by_field: dict[str, int]
    missing_metric_ratio: float
    duplicate_post_ids: int


def audit_posts(posts: Iterable[object]) -> PostQuality:
    records = list(posts)
    missing = {field: 0 for field in (*REQUIRED_POST_FIELDS, *METRIC_FIELDS)}
    ids: list[str] = []
    complete = 0
    for post in records:
        post_id = str(getattr(post, "post_id", ""))
        ids.append(post_id)
        identity_ok = True
        for field in REQUIRED_POST_FIELDS:
            value = getattr(post, field, None)
            if value in (None, ""):
                missing[field] += 1
                identity_ok = False
        for field in METRIC_FIELDS:
            if getattr(post, field, None) is None:
                missing[field] += 1
        if identity_ok:
            complete += 1
    metric_slots = len(records) * len(METRIC_FIELDS)
    missing_metric_ratio = (sum(missing[field] for field in METRIC_FIELDS) / metric_slots) if metric_slots else 1.0
    duplicates = sum(count - 1 for item, count in Counter(ids).items() if item and count > 1)
    return PostQuality(len(records), complete, missing, round(missing_metric_ratio, 4), duplicates)


def write_quality(root: str | Path, quality: PostQuality) -> Path:
    target = Path(root) / "analysis" / "data-quality.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(quality), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
