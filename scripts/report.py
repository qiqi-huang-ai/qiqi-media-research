"""Deterministic Markdown renderer for evidence-bound research reports."""

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


SECTIONS = (
    "结论摘要",
    "研究任务",
    "数据覆盖",
    "核心发现",
    "赛道与趋势",
    "对标账号",
    "高表现内容",
    "评论需求",
    "内容空白",
    "机会排序",
    "建议选题与下一步",
    "局限与置信度",
)
FINDING_SECTIONS = set(SECTIONS[3:11])
EVIDENCE_CLASSES = {"observed", "calculated", "interpreted", "hypothesis"}


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|")


@dataclass(slots=True)
class Finding:
    text: str
    evidence_ids: list[str]
    evidence_class: str = "interpreted"
    section: str = "核心发现"


@dataclass(slots=True)
class ResearchReport:
    title: str
    summary: str
    findings: list[Finding] = field(default_factory=list)
    task: str = "未提供"
    coverage: str = "未提供"
    limitations: list[str] = field(default_factory=list)
    confidence: str = "未评估"


def _validate(report: ResearchReport) -> None:
    for finding in report.findings:
        if not finding.evidence_ids:
            raise ValueError("every finding requires at least one evidence ID")
        if finding.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"invalid evidence class: {finding.evidence_class}")
        if finding.section not in FINDING_SECTIONS:
            raise ValueError(f"invalid report section: {finding.section}")


def render_report(report: ResearchReport) -> str:
    _validate(report)
    grouped = {section: [] for section in FINDING_SECTIONS}
    for finding in report.findings:
        evidence = ", ".join(_escape(item) for item in finding.evidence_ids)
        grouped[finding.section].append(
            f"- {_escape(finding.text)} `[{finding.evidence_class}]`（evidence: {evidence}）"
        )

    blocks = [f"# {_escape(report.title)}"]
    for section in SECTIONS:
        blocks.append(f"## {section}")
        if section == "结论摘要":
            content = _escape(report.summary)
        elif section == "研究任务":
            content = _escape(report.task)
        elif section == "数据覆盖":
            content = _escape(report.coverage)
        elif section == "局限与置信度":
            limitations = [f"- {_escape(item)}" for item in report.limitations]
            content = "\n".join([f"置信度：{_escape(report.confidence)}", *limitations])
        else:
            content = "\n".join(grouped[section]) or "- 本次研究未形成有充分证据的结论。"
        blocks.append(content)
    return "\n\n".join(blocks) + "\n"


def _from_dict(data: dict[str, Any]) -> ResearchReport:
    findings = [Finding(**item) for item in data.get("findings", [])]
    return ResearchReport(
        title=data["title"],
        summary=data["summary"],
        findings=findings,
        task=data.get("task", "未提供"),
        coverage=data.get("coverage", "未提供"),
        limitations=data.get("limitations", []),
        confidence=data.get("confidence", "未评估"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an evidence-bound research report")
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = _from_dict(json.loads(args.input_json.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
