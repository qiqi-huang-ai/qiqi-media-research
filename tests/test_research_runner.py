import json
import pytest

from scripts.research_runner import MODES, ResearchRequest, _effective_requirements, _filter_posts, execute_request, plan_request


def test_all_eleven_modes_have_a_bounded_plan():
    for mode in MODES:
        plan = plan_request(ResearchRequest(mode=mode, platform="douyin", query="AI工具", secondary_platform="xiaohongshu" if mode == "cross-platform" else None))
        assert plan.mode == mode
        assert plan.request_count > 0
        assert plan.request_count <= 20
        assert plan.operations


def test_short_prompts_receive_a_mature_mode_contract_by_default():
    for mode in MODES:
        request = ResearchRequest(mode=mode, platform="douyin", query="AI工具", secondary_platform="xiaohongshu" if mode == "cross-platform" else None)
        assert "mature-mode-report" in _effective_requirements(request)
    account_requirements = set(_effective_requirements(ResearchRequest(mode="account-audit", platform="douyin", query="账号", entity_id="sec-1")))
    assert {"account-profile", "account-baseline", "account-patterns", "top-bottom-comparison", "actionable-recommendations"} <= account_requirements


def test_cross_platform_requires_two_platforms():
    with pytest.raises(ValueError, match="two platforms"):
        plan_request(ResearchRequest(mode="cross-platform", platform="douyin", query="AI工具"))


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="unsupported research mode"):
        plan_request(ResearchRequest(mode="video-editing", platform="douyin", query="AI工具"))


def test_unknown_delivery_requirement_is_rejected():
    with pytest.raises(ValueError, match="unsupported delivery requirements"):
        plan_request(ResearchRequest(mode="niche-discovery", platform="douyin", query="AI工具", requirements=("video-understanding",)))


def test_date_bounds_are_validated():
    with pytest.raises(ValueError, match="start_at must be earlier"):
        plan_request(ResearchRequest(mode="niche-discovery", platform="douyin", query="AI工具", start_at="2026-09-20T00:00:00+00:00", end_at="2026-09-19T00:00:00+00:00"))


def test_strict_time_filter_rejects_unverified_platform_path():
    with pytest.raises(ValueError, match="verified only for Douyin"):
        plan_request(ResearchRequest(mode="niche-discovery", platform="xiaohongshu", query="AI工具", start_at="2026-09-12T00:00:00+08:00"))


def test_search_results_are_filtered_by_published_at():
    from scripts.models import Post
    posts = [
        Post(platform="douyin", post_id="old", source_url="u", published_at="2026-09-11T23:59:59+00:00"),
        Post(platform="douyin", post_id="inside", source_url="u", published_at="2026-09-12T00:00:00+00:00"),
        Post(platform="douyin", post_id="new", source_url="u", published_at="2026-09-19T00:00:01+00:00"),
    ]
    result = _filter_posts(posts, "2026-09-12T00:00:00+00:00", "2026-09-19T00:00:00+00:00")
    assert [post.post_id for post in result] == ["inside"]


def test_plan_does_not_claim_exact_price():
    plan = plan_request(ResearchRequest(mode="trend-scan", platform="douyin", query="AI工具"))
    assert "price" not in plan.cost_notice.lower()
    assert "调用" in plan.cost_notice


def test_keyword_slice_plan_matches_its_single_search_execution():
    plan = plan_request(ResearchRequest(mode="niche-discovery", platform="douyin", query="AI工具"))
    assert plan.request_count == 4
    assert plan.operations == ("search", "statistics")


class FakeAdapter:
    def search_posts(self, keyword, **kwargs):
        from adapters.base import Page
        from scripts.models import Post
        return Page([Post(platform="douyin", post_id="p1", source_url="https://example/p1", author_id="a", views=100, likes=10)], None, False, {"items": ["fixture"]})

    def get_post(self, **kwargs):
        from adapters.base import Page
        from scripts.models import Post
        self.last_raw = {"detail": ["fixture"]}
        return Post(platform="douyin", post_id=kwargs.get("aweme_id") or kwargs["note_id"], source_url="https://example/p1", author_id="a", views=100, likes=10)

    def get_comments(self, aweme_id, **kwargs):
        from adapters.base import Page
        from scripts.models import Comment
        return Page([Comment(platform="douyin", comment_id="c1", post_id=aweme_id, source_url="https://example/p1", text="多少钱")], None, False, {"comments": ["fixture"]})

    def get_video_statistics(self, aweme_ids):
        rows = [
            {"aweme_id": post_id, "play_count": 1000 - index * 150, "digg_count": 100 - index * 10,
             "comment_count": 20 - index, "share_count": 10 - index, "collect_count": 30 - index}
            for index, post_id in enumerate(aweme_ids)
        ]
        self.last_statistics_raw = {"data": {"statistics_list": rows}}
        return {row["aweme_id"]: row for row in rows}

    def get_account(self, sec_user_id):
        from scripts.models import Account
        self.last_raw = {"account": ["fixture"]}
        return Account(platform="douyin", account_id=sec_user_id, source_url="https://example/a", name="Test")

    def get_account_posts(self, sec_user_id, **kwargs):
        from adapters.base import Page
        from scripts.models import Post
        posts = [
            Post(platform="douyin", post_id=f"a{index}", source_url=f"https://example/a{index}",
                 author_id=sec_user_id, author_name="Test", text=text,
                 published_at=f"2026-09-{10 + index:02d}T00:00:00+00:00",
                 views=100 * index, likes=10 * index, comments=index, shares=index, saves=index)
            for index, text in enumerate(("AI工具上线实测", "3个Prompt工作流", "为什么AI会淘汰岗位", "新手教程怎么用"), 1)
        ]
        return Page(posts, None, False, {"items": ["account-fixture"]})

    def get_trends(self):
        from adapters.base import Page
        from scripts.models import TrendItem
        return Page([TrendItem(platform="douyin", trend_id="t1", title="AI工具", source_url="https://example/t1", rank=1)], None, False, {"trends": ["fixture"]})

    def search_accounts(self, keyword, **kwargs):
        from adapters.base import Page
        from scripts.models import Account
        return Page([Account(platform="douyin", account_id="sec-1", source_url="https://example/a", name="Creator")], None, False, {"users": ["fixture"]})


def test_execute_keyword_mode_writes_evidence_and_report(tmp_path):
    result = execute_request(
        ResearchRequest(mode="niche-discovery", platform="douyin", query="AI工具"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert result.raw_paths
    assert result.normalized_path.is_file()
    assert result.manifest_path.is_file()
    assert result.audit_path and result.audit_path.is_file()
    quality = json.loads((tmp_path / "analysis/data-quality.json").read_text())
    assert quality["missing_by_field"]["views"] == 0
    normalized = json.loads(result.normalized_path.read_text().splitlines()[0])
    assert normalized["views"] == 1000
    assert normalized["views_source"] == "statistics"
    assert '"request_count": 2' in result.manifest_path.read_text()
    report = result.report_path.read_text()
    assert "原始作品明细" in report
    assert "原始链接" in report
    assert "播放" in report
    assert "evidence:" not in report
    ledger = json.loads((tmp_path / "analysis/findings.json").read_text())
    assert ledger[0]["evidence_ids"]


def test_execute_viral_breakdown_requires_post_id_and_writes_comment_evidence(tmp_path):
    result = execute_request(
        ResearchRequest(mode="viral-breakdown", platform="douyin", query="作品拆解", entity_id="p1"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert "comment:c1" not in result.report_path.read_text()
    ledger = json.loads((tmp_path / "analysis/findings.json").read_text())
    assert any("comment:c1" in item["evidence_ids"] for item in ledger)
    assert "评论需求" in result.report_path.read_text()
    assert result.brief_path and result.brief_path.is_file()


def test_entity_modes_require_entity_id():
    with pytest.raises(ValueError, match="entity_id"):
        execute_request(ResearchRequest(mode="comment-mining", platform="douyin", query="评论"), adapter=FakeAdapter(), output_root="/tmp/x")


def test_comment_mining_plan_includes_detail_and_comments():
    plan = plan_request(ResearchRequest(mode="comment-mining", platform="douyin", query="评论", entity_id="p1"))
    assert plan.request_count == 3
    assert plan.operations == ("post_detail", "statistics", "comments")


def test_xiaohongshu_trend_scan_is_rejected_before_execution():
    with pytest.raises(ValueError, match="only for douyin"):
        plan_request(ResearchRequest(mode="trend-scan", platform="xiaohongshu", query="AI"))


def test_execute_account_audit_requires_entity_id(tmp_path):
    result = execute_request(
        ResearchRequest(mode="account-audit", platform="douyin", query="账号审计", entity_id="sec-1"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert not result.report_path.exists()
    assert (tmp_path / "analysis/data-pack.json").is_file()
    assert (tmp_path / "analysis/draft-account-audit.md").is_file()
    assert (tmp_path / "analysis/semantic-review.template.json").is_file()
    audit = json.loads(result.audit_path.read_text())
    assert audit["status"] == "failed"
    assert any(item["name"] == "semantic_review" and not item["passed"] for item in audit["checks"])


def test_execute_cross_platform_requires_and_combines_second_adapter(tmp_path):
    result = execute_request(
        ResearchRequest(mode="cross-platform", platform="douyin", secondary_platform="xiaohongshu", query="AI工具"),
        adapter=FakeAdapter(),
        secondary_adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert "cross-platform" in result.report_path.read_text()


def test_cross_platform_starts_xiaohongshu_with_an_empty_cursor(tmp_path):
    class XiaohongshuFake(FakeAdapter):
        def search_posts(self, keyword, *, cursor=None, **kwargs):
            assert cursor is None
            return super().search_posts(keyword, **kwargs)

    execute_request(
        ResearchRequest(mode="cross-platform", platform="douyin", secondary_platform="xiaohongshu", query="AI工具"),
        adapter=FakeAdapter(),
        secondary_adapter=XiaohongshuFake(),
        output_root=tmp_path,
    )


def test_execute_trend_scan_writes_trend_evidence(tmp_path):
    result = execute_request(
        ResearchRequest(mode="trend-scan", platform="douyin", query="AI工具"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert "趋势" in result.report_path.read_text()


def test_execute_competitor_discovery_writes_account_evidence(tmp_path):
    result = execute_request(
        ResearchRequest(mode="competitor-discovery", platform="douyin", query="AI工具"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert "account:sec-1" not in result.report_path.read_text()
    ledger = json.loads((tmp_path / "analysis/findings.json").read_text())
    assert any("account:sec-1" in item["evidence_ids"] for item in ledger)


@pytest.mark.parametrize("mode,marker", [
    ("content-gap", "供给与需求"),
    ("brand-product", "品牌/产品"),
    ("idea-generation", "证据化选题"),
    ("market-map", "市场结构"),
])
def test_specialized_keyword_modes_have_mode_specific_analysis(tmp_path, mode, marker):
    result = execute_request(
        ResearchRequest(mode=mode, platform="douyin", query="AI工具"),
        adapter=FakeAdapter(),
        output_root=tmp_path / mode,
    )
    assert marker in result.report_path.read_text()
