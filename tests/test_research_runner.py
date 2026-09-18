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


class FakeAdapter:
    def search_posts(self, keyword, **kwargs):
        from adapters.base import Page
        from scripts.models import Post
        return Page([Post(platform="douyin", post_id="p1", source_url="https://example/p1", author_id="a", views=100, likes=10)], None, False, {"items": ["fixture"]})


def test_execute_keyword_mode_writes_evidence_and_report(tmp_path):
    result = execute_request(
        ResearchRequest(mode="niche-discovery", platform="douyin", query="AI工具"),
        adapter=FakeAdapter(),
        output_root=tmp_path,
    )
    assert result.report_path.is_file()
    assert result.raw_paths
    assert result.normalized_path.is_file()
    assert "evidence:" in result.report_path.read_text()
