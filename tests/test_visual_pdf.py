from scripts.visual_pdf import _display_line, parse_markdown


def test_pdf_reader_text_hides_internal_evidence_annotations():
    line = "结论 `[interpreted]`（evidence: post:123, post:456）"
    assert _display_line(line) == "结论"
    assert "evidence" not in _display_line("作品链接与 evidence ID：post:123")


def test_pdf_parser_keeps_the_markdown_sections_as_the_single_source():
    title, sections = parse_markdown("# 标题\n\n## 摘要\n\n- 一条内容")
    assert title == "标题"
    assert sections[0].title == "摘要"
    assert sections[0].lines == ("一条内容",)
