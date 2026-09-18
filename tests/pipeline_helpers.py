from dataclasses import dataclass
import json
from pathlib import Path

from adapters.douyin import DouyinAdapter
from scripts.analyze import compute_post_metrics
from scripts.normalize import write_normalized
from scripts.raw_store import RawStore
from scripts.report import Finding, ResearchReport
from scripts.score import OpportunityInputs, score_opportunity


FIXTURES = Path(__file__).parent / "fixtures"


class FixtureClient:
    def __init__(self, payload):
        self.payload = payload

    def get(self, path, params):
        return type("Response", (), {"data": self.payload})()


@dataclass(slots=True)
class PipelineResult:
    raw_files: list[Path]
    normalized_posts: list[object]
    report: ResearchReport


def run_fixture_research(root: Path, *, platform: str) -> PipelineResult:
    if platform != "douyin":
        raise ValueError("offline helper currently uses the Douyin fixture")
    payload = json.loads((FIXTURES / "douyin/posts.json").read_text(encoding="utf-8"))
    raw_path = RawStore(root).save(platform, "account-posts", payload)
    posts = DouyinAdapter(FixtureClient(payload)).get_account_posts("sec-1").items
    for post in posts:
        post.raw_path = str(raw_path)
    write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    opportunity = score_opportunity(OpportunityInputs(60, 50, 50, 60, 50, 50))
    finding = Finding(
        text=f"样本最高账号内相对表现为 {max(item.relative_performance or 0 for item in metrics):.2f}，演示机会分 {opportunity.score:.2f}",
        evidence_ids=[f"post:{posts[0].post_id}"],
        evidence_class="calculated",
    )
    report = ResearchReport(
        title="离线夹具研究",
        summary="完整离线链路已生成结果。",
        task="验证采集、标准化、分析、评分与报告接口",
        coverage=f"抖音 {len(posts)} 条脱敏作品",
        findings=[finding],
        limitations=["仅使用脱敏固定样本"],
        confidence="low",
    )
    return PipelineResult([raw_path], posts, report)
