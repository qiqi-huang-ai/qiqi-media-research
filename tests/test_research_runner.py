import pytest

from scripts.research_runner import MODES, ResearchRequest, execute_request, plan_request


def test_all_eleven_modes_have_a_bounded_plan():
    for mode in MODES:
        plan = plan_request(ResearchRequest(mode=mode, platform="douyin", query="AI工具", secondary_platform="xiaohongshu" if mode == "cross-platform" else None))
        assert plan.mode == mode
        assert plan.request_count > 0
        assert plan.request_count <= 20
        assert plan.operations


def test_cross_platform_requires_two_platforms():
    with pytest.raises(ValueError, match="two platforms"):
        plan_request(ResearchRequest(mode="cross-platform", platform="douyin", query="AI工具"))


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="unsupported research mode"):
        plan_request(ResearchRequest(mode="video-editing", platform="douyin", query="AI工具"))


def test_plan_does_not_claim_exact_price():
    plan = plan_request(ResearchRequest(mode="trend-scan", platform="douyin", query="AI工具"))
    assert "price" not in plan.cost_notice.lower()
    assert "调用" in plan.cost_notice


def test_keyword_slice_plan_matches_its_single_search_execution():
    plan = plan_request(ResearchRequest(mode="niche-discovery", platform="douyin", query="AI工具"))
    assert plan.request_count == 1
    assert plan.operations == ("search",)


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
        self.last_statistics_raw = {"data": {"statistics_list": [{"aweme_id": aweme_ids[0], "play_count": 1000}]}}
        return {aweme_ids[0]: {"play_count": 1000}}

    def get_account(self, sec_user_id):
        from scripts.models import Account
        self.last_raw = {"account": ["fixture"]}
        return Account(platform="douyin", account_id=sec_user_id, source_url="https://example/a", name="Test")

    def get_account_posts(self, sec_user_id, **kwargs):
        return self.search_posts("account")

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
    assert '"request_count": 1' in result.manifest_path.read_text()
    assert "evidence:" in result.report_path.read_text()


def test_execute_viral_breakdown_requires_post_id_and_writes_comment_evidence(tmp_path):
    result = execute_request(
        ResearchRequest(mode="viral-breakdown", platform="douyin", query="作品拆解", entity_id="p1"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert "comment:c1" in result.report_path.read_text()


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
    assert result.report_path.is_file()
    assert "account-audit" in result.report_path.read_text()


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
    assert "account:sec-1" in result.report_path.read_text()


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
