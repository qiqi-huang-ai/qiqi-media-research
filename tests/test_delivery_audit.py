import json

from scripts.delivery_audit import audit_delivery


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_ledger(root):
    _write_json(root / "analysis/findings.json", [{"text": "结论", "evidence_class": "observed", "evidence_ids": ["post:p1"]}])


def test_complete_post_delivery_is_ready(tmp_path):
    _write_json(tmp_path / "brief.json", {"mode": "niche-discovery", "start_at": "2026-09-12T00:00:00+00:00", "end_at": "2026-09-19T00:00:00+00:00"})
    _write_json(tmp_path / "manifest.json", {"request_count": 2})
    _write_json(tmp_path / "raw/douyin/search-a.json", {"data": {}})
    _write_json(tmp_path / "analysis/data-quality.json", {"total": 1, "complete_identity": 1, "missing_metric_ratio": 0.0, "duplicate_post_ids": 0})
    _write_json(tmp_path / "analysis/search-filter.json", {"filtered_result_count": 1})
    _write_ledger(tmp_path)
    _write_json(tmp_path / "normalized/posts.jsonl", {"post_id": "p1", "source_url": "https://example/p1", "views": 100})
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n可见数据：播放 100\n\n原始链接：https://example/p1\n", encoding="utf-8")
    result = audit_delivery(tmp_path, report)
    assert result.status == "ready", [(check.name, check.passed, check.detail) for check in result.checks]


def test_missing_identity_blocks_delivery(tmp_path):
    _write_json(tmp_path / "brief.json", {"mode": "niche-discovery"})
    _write_json(tmp_path / "manifest.json", {})
    _write_json(tmp_path / "raw/douyin/search-a.json", {})
    _write_json(tmp_path / "analysis/data-quality.json", {"total": 1, "complete_identity": 0, "missing_metric_ratio": 0.2, "duplicate_post_ids": 0})
    _write_ledger(tmp_path)
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
    _write_ledger(tmp_path)
    _write_json(tmp_path / "normalized/posts.jsonl", {"platform": "douyin", "post_id": "p1", "source_url": "https://example/p1", "views": 100, "views_source": "statistics"})
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n可见数据：播放 100\n\n原始链接：https://example/p1\n\n## 评论需求\n\n- 用户想看教程\n", encoding="utf-8")
    result = audit_delivery(tmp_path, report)
    assert result.status == "failed"
    assert any(check.name == "required_comment_insights" and not check.passed for check in result.checks)


def test_short_prompt_mode_contract_blocks_a_skeletal_report(tmp_path):
    _write_json(tmp_path / "brief.json", {"mode": "competitor-discovery", "requirements": ["mature-mode-report"]})
    _write_json(tmp_path / "manifest.json", {})
    _write_json(tmp_path / "raw/douyin/account-search-a.json", {})
    _write_json(tmp_path / "normalized/accounts.jsonl", {"account_id": "a1", "source_url": "https://example/a1"})
    _write_ledger(tmp_path)
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n## 对标账号\n\n- 候选账号 1 个\n", encoding="utf-8")
    result = audit_delivery(tmp_path, report)
    assert result.status == "failed"
    check = next(item for item in result.checks if item.name == "required_mature_mode_report")
    assert "建议选题与下一步" in check.detail


def test_account_decision_report_blocks_skeletal_report(tmp_path):
    _write_json(tmp_path / "brief.json", {
        "mode": "account-audit",
        "requirements": ["mature-mode-report", "account-profile", "account-baseline", "account-patterns", "top-bottom-comparison", "actionable-recommendations"],
    })
    _write_json(tmp_path / "manifest.json", {})
    _write_json(tmp_path / "raw/douyin/account-a.json", {})
    _write_json(tmp_path / "raw/douyin/account-posts-a.json", {})
    _write_json(tmp_path / "normalized/accounts.jsonl", {"account_id": "a1", "source_url": "https://example/a"})
    _write_json(tmp_path / "normalized/posts.jsonl", {"post_id": "p1", "source_url": "https://example/p1", "views": 100})
    _write_ledger(tmp_path)
    (tmp_path / "analysis/evidence-pack.md").write_text("# evidence pack\n" + ("x" * 300), encoding="utf-8")
    _write_json(tmp_path / "analysis/semantic-review.json", {
        "status": "reviewed",
        "mode": "account-audit",
        "source_data_pack": "analysis/data-pack.json",
        "reviewed_sections": {key: "充分的语义复核，包含样本依据、反例边界和行动含义。" for key in (
            "account_positioning", "recent_vs_historical", "content_strategy", "viral_patterns",
            "audience_needs", "copyable_boundaries", "actions_and_validation",
        )},
    })
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n\n## 对标账号\n\n- 账号事实：a\n\n## 核心发现\n\n- 表现基线：100\n\n## 高表现内容\n\n- 分组对照：top/bottom\n\n## 评论需求\n\n- 评论覆盖：1\n\n## 建议选题与下一步\n\n- 可执行建议：做内容\n", encoding="utf-8")
    result = audit_delivery(tmp_path, report)
    assert result.status == "failed"
    quality = next(item for item in result.checks if item.name == "decision_report_quality")
    assert not quality.passed


def test_account_decision_report_passes_with_evidence_bound_modules(tmp_path):
    _write_json(tmp_path / "brief.json", {
        "mode": "account-audit",
        "requirements": ["mature-mode-report", "account-profile", "account-baseline", "account-patterns", "top-bottom-comparison", "actionable-recommendations"],
    })
    _write_json(tmp_path / "manifest.json", {})
    _write_json(tmp_path / "raw/douyin/account-a.json", {})
    _write_json(tmp_path / "raw/douyin/account-posts-a.json", {})
    _write_json(tmp_path / "raw/douyin/comments-a.json", {})
    _write_json(tmp_path / "analysis/data-quality.json", {"total": 1, "complete_identity": 1, "missing_metric_ratio": 0.0, "duplicate_post_ids": 0})
    _write_json(tmp_path / "normalized/accounts.jsonl", {"account_id": "a1", "source_url": "https://example/a"})
    _write_json(tmp_path / "normalized/posts.jsonl", {"platform": "douyin", "post_id": "p1", "source_url": "https://example/p1", "views": 100, "views_source": "statistics"})
    _write_json(tmp_path / "analysis/data-pack.json", {})
    _write_ledger(tmp_path)
    (tmp_path / "analysis/evidence-pack.md").write_text("# evidence pack\n" + ("x" * 300), encoding="utf-8")
    _write_json(tmp_path / "analysis/semantic-review.json", {
        "status": "reviewed", "mode": "account-audit", "source_data_pack": "analysis/data-pack.json",
        "reviewed_sections": {key: "这项复核使用了多个样本依据，说明了普通表现反例、适用边界和对创作者下一步行动的含义；同时标明结论层级、证据覆盖范围和仍需补充的数据，并解释了为什么这些样本足以支持当前的方向性判断。" for key in (
            "account_positioning", "recent_vs_historical", "content_strategy", "viral_patterns",
            "audience_needs", "copyable_boundaries", "actions_and_validation",
        )},
    })
    sections = [
        "账号定位与内容角色", "爆款规律与反例", "内容策略地图", "公开受众需求画像", "可借鉴方向", "验证计划",
    ]
    body = "\n\n".join(f"## {section}\n\n结论基于样本与账号内基线，依据包括高表现和普通作品；需要保留反例边界，并转化为可执行的行动判断。" for section in sections)
    report = tmp_path / "reports/report.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        "# report\n\n## 对标账号\n\n账号事实：研究对象和公开主页。\n\n## 核心发现\n\n表现基线：账号内中位数。\n\n## 高表现内容\n\n分组对照：高低表现和依据。\n\n标题/文案模式：样本分类。\n\n内容组合：样本分类。\n\n## 评论需求\n\n评论覆盖和样本依据。\n\n## 建议选题与下一步\n\n可执行建议 1 连接到基线。可执行建议 2 连接到评论。可执行建议 3 连接到验证。\n\n可见数据：播放 100；原始链接：https://example/p1\n\n" + body.replace("## 验证计划", "## 验证计划\n\n指标、观察周期和升级条件。请在观察周期内记录指标变化，并依据升级条件决定是否扩展为系列。每周记录相对基线、互动率和评论质量；观察两轮后根据升级条件判断是否增加样本或升级为固定栏目。"),
        encoding="utf-8",
    )
    result = audit_delivery(tmp_path, report)
    assert result.status == "ready", [(check.name, check.passed, check.detail) for check in result.checks]
