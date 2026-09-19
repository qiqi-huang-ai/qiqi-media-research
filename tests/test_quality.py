from scripts.models import Post
from scripts.quality import audit_posts


def test_quality_reports_missing_metrics_and_duplicate_ids():
    posts = [
        Post(platform="douyin", post_id="p1", source_url="https://example/p1", author_name="A", text="x", published_at="2026-09-18T00:00:00+00:00", views=100),
        Post(platform="douyin", post_id="p1", source_url="https://example/p1", author_name="A", text="x", published_at="2026-09-18T00:00:00+00:00"),
    ]
    result = audit_posts(posts)
    assert result.total == 2
    assert result.duplicate_post_ids == 1
    assert result.missing_by_field["views"] == 1
    assert result.missing_metric_ratio > 0
