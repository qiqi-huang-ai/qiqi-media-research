import pytest

from scripts.report import Finding, ResearchReport, render_report


def test_finding_without_evidence_is_rejected():
    report = ResearchReport(title="测试", summary="摘要", findings=[Finding(text="这是趋势", evidence_ids=[])])
    with pytest.raises(ValueError, match="evidence"):
        render_report(report)


def test_report_contains_coverage_and_limitations():
    report = ResearchReport(
        title="AI工具赛道",
        summary="样本显示教程需求集中。",
        findings=[Finding(text="教程问题集中", evidence_ids=["comment:c1"], evidence_class="observed")],
        coverage="抖音10条作品、50条评论",
        limitations=["仅覆盖最近30天"],
    )
    text = render_report(report)
    assert "数据覆盖" in text
    assert "局限与置信度" in text
    assert "comment:c1" in text


def test_user_pipes_are_escaped():
    report = ResearchReport(
        title="A | B",
        summary="摘要",
        findings=[Finding(text="左 | 右", evidence_ids=["post:1"])],
    )
    text = render_report(report)
    assert "A \\| B" in text
    assert "左 \\| 右" in text
