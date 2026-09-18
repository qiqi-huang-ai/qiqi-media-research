"""Opt-in live acceptance planner. Dry-run performs zero network calls."""

import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.douyin import DouyinAdapter
from adapters.xiaohongshu import XiaohongshuAdapter
from scripts.analyze import compute_post_metrics
from scripts.api_client import TikHubClient, TikHubError
from scripts.normalize import write_normalized
from scripts.raw_store import RawStore
from scripts.report import Finding, ResearchReport, render_report


MAX_SEARCH_PAGES = 1
MAX_ACCOUNT_POST_PAGES = 2
MAX_COMMENT_PAGES = 1
MAX_POST_DETAILS = 3


OPERATIONS = {
    "douyin": [
        "search",
        "account",
        "account_posts",
        "post_detail",
        "comments",
        "pagination_check",
        "normalization",
        "analysis",
        "report",
    ],
    "xiaohongshu": [
        "search",
        "account",
        "account_posts",
        "post_detail",
        "comments",
        "pagination_check",
        "normalization",
        "analysis",
        "report",
    ],
}


def request_cap_per_platform() -> int:
    # The pagination check is performed within the two capped account-post pages.
    return MAX_SEARCH_PAGES + 1 + MAX_ACCOUNT_POST_PAGES + MAX_POST_DETAILS + MAX_COMMENT_PAGES


def acceptance_manifest(platform: str) -> dict[str, object]:
    platforms = list(OPERATIONS) if platform == "all" else [platform]
    return {
        "dry_run": True,
        "network_calls_made": 0,
        "platforms": {
            name: {
                "operations": OPERATIONS[name],
                "maximum_requests": request_cap_per_platform(),
                "caps": {
                    "search_pages": MAX_SEARCH_PAGES,
                    "account_post_pages": MAX_ACCOUNT_POST_PAGES,
                    "comment_pages": MAX_COMMENT_PAGES,
                    "post_details": MAX_POST_DETAILS,
                },
            }
            for name in platforms
        },
        "maximum_requests_total": request_cap_per_platform() * len(platforms),
        "billing_notice": "TikHub pricing may change; Douyin Search is separately billed.",
    }


@dataclass(slots=True)
class AcceptanceState:
    platform: str
    cap: int
    requests: int = 0
    raw_paths: list[Path] = field(default_factory=list)
    outcomes: list[tuple[str, str]] = field(default_factory=list)


class RecordingClient:
    def __init__(self, client, store: RawStore, state: AcceptanceState):
        self.client = client
        self.store = store
        self.state = state

    def get(self, path, params):
        return self._request("get", path, params)

    def post(self, path, params):
        return self._request("post", path, params)

    def _request(self, method, path, params):
        if self.state.requests >= self.state.cap:
            raise RuntimeError(f"acceptance request cap reached for {self.state.platform}")
        self.state.requests += 1
        try:
            response = getattr(self.client, method)(path, params)
        except TikHubError as error:
            self.state.outcomes.append((path, f"HTTP {error.status or 'network-error'}"))
            raise
        raw_path = self.store.save(self.state.platform, Path(path).name, response.data)
        self.state.raw_paths.append(raw_path)
        self.state.outcomes.append((path, f"HTTP {response.status}"))
        return response


def _dedupe_posts(posts):
    return list({post.post_id: post for post in posts if post.post_id}.values())


def run_platform(platform: str, keyword: str, root: Path, cap: int | None = None) -> tuple[AcceptanceState, Path | None, list[str]]:
    state = AcceptanceState(platform, cap or request_cap_per_platform())
    client = RecordingClient(TikHubClient(max_retries=0), RawStore(root), state)
    adapter = DouyinAdapter(client) if platform == "douyin" else XiaohongshuAdapter(client)
    failures = []
    posts = []
    try:
        page = adapter.search_posts(keyword)
        posts.extend(page.items)
        if not page.items:
            raise RuntimeError("search returned no mapped posts")
        first = page.items[0]
        detail = adapter.get_post(**({"aweme_id": first.post_id} if platform == "douyin" else {"note_id": first.post_id}))
        posts.append(detail)
        if first.author_id:
            if platform == "douyin":
                adapter.get_account(first.author_id)
                account_page = adapter.get_account_posts(first.author_id)
            else:
                adapter.get_account(user_id=first.author_id)
                account_page = adapter.get_account_posts(user_id=first.author_id)
            posts.extend(account_page.items)
            if account_page.has_more and account_page.next_cursor and state.requests < state.cap - 1:
                if platform == "douyin":
                    posts.extend(adapter.get_account_posts(first.author_id, cursor=account_page.next_cursor).items)
                else:
                    posts.extend(adapter.get_account_posts(user_id=first.author_id, cursor=account_page.next_cursor).items)
        if state.requests < state.cap:
            if platform == "douyin":
                adapter.get_comments(first.post_id)
            else:
                adapter.get_comments(note_id=first.post_id)
    except Exception as error:
        failures.append(f"{type(error).__name__}: {error}")

    posts = _dedupe_posts(posts)
    if not posts:
        return state, None, failures
    for post in posts:
        if state.raw_paths and not post.raw_path:
            post.raw_path = str(state.raw_paths[0])
    write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    finding = Finding(
        text=f"成功映射 {len(posts)} 条作品；{sum(item.engagement_rate is not None for item in metrics)} 条可计算互动率",
        evidence_ids=[f"post:{posts[0].post_id}"],
        evidence_class="calculated",
    )
    report = ResearchReport(
        title=f"{platform} 真实接口验收",
        summary="本报告只验证接口与证据链，不代表市场研究结论。",
        task=f"使用关键词进行低量真实验收：{keyword}",
        coverage=f"{len(posts)} 条标准化作品、{state.requests} 次请求、{len(state.raw_paths)} 个原始证据文件",
        findings=[finding],
        limitations=failures or ["仅做低量接口验收"],
        confidence="low",
    )
    report_path = root / f"{platform}-acceptance-report.md"
    report_path.write_text(render_report(report), encoding="utf-8")
    return state, report_path, failures


def write_results(out: Path, results) -> None:
    lines = ["# Live acceptance results", "", f"- 时间：{datetime.now(UTC).isoformat()}", "- 凭证：仅进程内使用，未写入结果", ""]
    for platform, state, report_path, failures in results:
        report_display = report_path.relative_to(Path.cwd()).as_posix() if report_path else "未生成"
        lines.extend([f"## {platform}", "", f"- 请求数：{state.requests}/{state.cap}", f"- 原始证据文件：{len(state.raw_paths)}", f"- 报告：{report_display}", "- 端点结果："])
        lines.extend(f"  - `{path}`：{status}" for path, status in state.outcomes)
        lines.append(f"- 限制/失败：{'; '.join(failures) if failures else '无'}")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("douyin", "xiaohongshu", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--douyin-keyword")
    parser.add_argument("--xiaohongshu-keyword")
    parser.add_argument("--out")
    parser.add_argument("--max-requests-per-platform", type=int, default=request_cap_per_platform())
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(acceptance_manifest(args.platform), ensure_ascii=False, indent=2))
        return 0
    if not os.environ.get("TIKHUB_API_KEY"):
        parser.error("TIKHUB_API_KEY is missing")
    if not args.out:
        parser.error("--out is required for live execution")
    selected = list(OPERATIONS) if args.platform == "all" else [args.platform]
    keyword_by_platform = {
        "douyin": args.douyin_keyword,
        "xiaohongshu": args.xiaohongshu_keyword,
    }
    if any(not keyword_by_platform[name] for name in selected):
        parser.error("a keyword is required for every selected platform")
    output = Path(args.out).resolve()
    artifact_root = output.parent / "live-artifacts"
    results = []
    for name in selected:
        state, report_path, failures = run_platform(name, keyword_by_platform[name], artifact_root / name, args.max_requests_per_platform)
        results.append((name, state, report_path, failures))
    write_results(output, results)
    print(json.dumps({"result": str(output), "requests": sum(item[1].requests for item in results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
