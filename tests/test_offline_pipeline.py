from scripts.report import render_report


def test_fixture_pipeline_creates_evidence_bound_report(tmp_path):
    from tests.pipeline_helpers import run_fixture_research

    result = run_fixture_research(tmp_path, platform="douyin")
    report = render_report(result.report)
    assert result.raw_files
    assert result.normalized_posts
    assert "核心发现" in report
    assert "evidence:" in report
