import json

from scripts.delivery_audit import audit_delivery


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def test_complete_post_delivery_is_ready(tmp_path):
    _write_json(tmp_path / "brief.json", {"mode": "niche-discovery", "start_at": "2026-09-12T00:00:00+00:00", "end_at": "2026-09-19T00:00:00+00:00"})
    _write_json(tmp_path / "manifest.json", {"request_count": 2})
    _write_json(tmp_path / "raw/douyin/search-a.json", {"data": {}})
    _write_json(tmp_path / "analysis/data-quality.json", {"total": 1, "complete_identity": 1, "missing_metric_ratio": 0.0, "duplicate_post_ids": 0})
    _write_json(tmp_path / "analysis/search-filter.json", {"filtered_result_count": 1})
    _write_json(tmp_path / "normalized/posts.jsonl", {"post_id": "p1", "source_url": "https://example/p1", "views": 100})
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n可见数据：播放 100\n\n原始链接：https://example/p1\n", encoding="utf-8")
    result = audit_delivery(tmp_path, report)
    assert result.status == "ready"


def test_missing_identity_blocks_delivery(tmp_path):
    _write_json(tmp_path / "brief.json", {"mode": "niche-discovery"})
    _write_json(tmp_path / "manifest.json", {})
    _write_json(tmp_path / "raw/douyin/search-a.json", {})
    _write_json(tmp_path / "analysis/data-quality.json", {"total": 1, "complete_identity": 0, "missing_metric_ratio": 0.2, "duplicate_post_ids": 0})
    _write_json(tmp_path / "normalized/posts.jsonl", {"post_id": "p1", "source_url": "https://example/p1", "views": 100})
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n可见数据：播放 100\n\n原始链接：https://example/p1\n", encoding="utf-8")
    assert audit_delivery(tmp_path, report).status == "failed"


def test_requested_comment_insights_require_raw_comments(tmp_path):
    _write_json(tmp_path / "brief.json", {"mode": "niche-discovery", "requirements": ["comment-insights"]})
    _write_json(tmp_path / "manifest.json", {})
    _write_json(tmp_path / "raw/douyin/search-a.json", {})
    _write_json(tmp_path / "analysis/data-quality.json", {"total": 1, "complete_identity": 1, "missing_metric_ratio": 0.0, "duplicate_post_ids": 0})
    _write_json(tmp_path / "normalized/posts.jsonl", {"platform": "douyin", "post_id": "p1", "source_url": "https://example/p1", "views": 100, "views_source": "statistics"})
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n可见数据：播放 100\n\n原始链接：https://example/p1\n\n## 评论需求\n\n- 用户想看教程\n", encoding="utf-8")
    result = audit_delivery(tmp_path, report)
    assert result.status == "failed"
    assert any(check.name == "required_comment_insights" and not check.passed for check in result.checks)
