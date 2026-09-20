import json

from scripts.visual_pdf import _display_line, infer_data_pack_path, load_account_visual_data, parse_markdown, render_pdf


def test_pdf_reader_text_hides_internal_evidence_annotations():
    line = "结论 `[interpreted]`（evidence: post:123, post:456）"
    assert _display_line(line) == "结论"
    assert "evidence" not in _display_line("作品链接与 evidence ID：post:123")


def test_pdf_parser_keeps_the_markdown_sections_as_the_single_source():
    title, sections = parse_markdown("# 标题\n\n## 摘要\n\n- 一条内容")
    assert title == "标题"
    assert sections[0].title == "摘要"
    assert sections[0].lines == ("一条内容",)


def test_account_visual_data_uses_same_run_observed_metrics(tmp_path):
    data_pack = tmp_path / "data-pack.json"
    data_pack.write_text(json.dumps({
        "mode": "account-audit",
        "account": {"name": "测试博主", "followers": 125703},
        "posts": [{"post_id": "p1", "views": 100, "likes": 10}, {"post_id": "p2", "views": 900, "likes": 90}],
        "comments": [{"post_id": "p1"}, {"post_id": "p1"}, {"post_id": "p2"}],
        "decision_metrics": {
            "baseline": {"views_median": 500, "likes_median": 50},
            "performance_bands": {"high_median": 900, "low_median": 100},
            "content_pillars": [{"label": "教程", "count": 2, "views_median": 500}],
            "comment_coverage": {"count": 3, "post_count": 2},
        },
    }, ensure_ascii=False), encoding="utf-8")

    visual = load_account_visual_data(data_pack)

    assert visual is not None
    assert visual.account_name == "测试博主"
    assert visual.followers == 125703
    assert visual.views_median == 500
    assert visual.high_median == 900
    assert visual.low_median == 100
    assert visual.pillars[0].label == "教程"
    assert visual.comment_post_count == 2


def test_visual_pdf_infers_only_the_sibling_run_data_pack(tmp_path):
    report_path = tmp_path / "run-a" / "reports" / "account.md"
    data_pack = tmp_path / "run-a" / "analysis" / "data-pack.json"
    report_path.parent.mkdir(parents=True)
    data_pack.parent.mkdir(parents=True)
    report_path.write_text("# 标题", encoding="utf-8")
    data_pack.write_text("{}", encoding="utf-8")

    assert infer_data_pack_path(report_path) == data_pack


def test_visual_pdf_renders_markdown_with_observed_account_charts(tmp_path):
    report_path = tmp_path / "run-a" / "reports" / "account.md"
    data_pack = tmp_path / "run-a" / "analysis" / "data-pack.json"
    output_path = tmp_path / "account.pdf"
    report_path.parent.mkdir(parents=True)
    data_pack.parent.mkdir(parents=True)
    report_path.write_text(
        "# 对标账号决策报告\n\n"
        "## 账号定位与内容角色\n\n- 基于样本的定位结论。\n\n"
        "## 爆款规律与反例\n\n- 结合高低表现组比较。\n\n"
        "## 内容策略地图\n\n- 教程支柱值得测试。\n\n"
        "## 公开受众需求画像\n\n- 评论反映公开可见的问题。\n\n"
        "## 可借鉴方向\n\n- 先做一周小样本测试。\n\n"
        "## 验证计划\n\n- 指标、观察、升级逐项记录。\n",
        encoding="utf-8",
    )
    data_pack.write_text(json.dumps({
        "mode": "account-audit",
        "account": {"name": "测试博主", "followers": 12000},
        "posts": [{"post_id": "p1", "views": 100}, {"post_id": "p2", "views": 900}],
        "comments": [{"post_id": "p1"}],
        "decision_metrics": {
            "baseline": {"views_median": 500, "likes_median": 50},
            "performance_bands": {"high_median": 900, "low_median": 100},
            "content_pillars": [{"label": "教程", "count": 2, "views_median": 500}],
            "comment_coverage": {"count": 1, "post_count": 1},
        },
    }, ensure_ascii=False), encoding="utf-8")

    render_pdf(report_path, output_path, period="2026-09-01 至 2026-09-07", source_count=4)

    assert output_path.read_bytes().startswith(b"%PDF")
    assert output_path.stat().st_size > 5_000
