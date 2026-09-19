"""Unified bounded entry point for the eleven research modes.

This module owns routing and planning. Platform adapters remain responsible for
endpoint details; semantic interpretation remains evidence-bound report work.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from typing import Any
import argparse

from scripts.analyze import compute_post_metrics, count_comment_signals
from scripts.collect import CollectionPlan, cost_notice, estimate_requests, write_manifest
from scripts.delivery_audit import audit_delivery, write_delivery_audit
from scripts.normalize import write_normalized
from scripts.raw_store import RawStore
from scripts.quality import audit_posts, write_quality
from scripts.report import Finding, ResearchReport, evidence_ledger, render_report


MODES = (
    "niche-discovery",
    "trend-scan",
    "competitor-discovery",
    "account-audit",
    "viral-breakdown",
    "comment-mining",
    "content-gap",
    "cross-platform",
    "brand-product",
    "idea-generation",
    "market-map",
)
PLATFORMS = {"douyin", "xiaohongshu"}
REQUIREMENTS = {
    "time-window", "post-metadata", "visible-metrics", "comment-insights",
    "trend-distinction", "content-ideas", "text-hook-structure",
    "account-profile", "account-baseline", "account-patterns",
    "top-bottom-comparison", "actionable-recommendations",
    "mature-mode-report",
}

ACCOUNT_AUDIT_REQUIREMENTS = (
    "account-profile",
    "account-baseline",
    "account-patterns",
    "top-bottom-comparison",
    "actionable-recommendations",
)


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    mode: str
    platform: str
    query: str
    secondary_platform: str | None = None
    entity_id: str | None = None
    sample_pages: int = 1
    comment_pages: int = 0
    start_at: str | None = None
    end_at: str | None = None
    requirements: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    mode: str
    platform: str
    operations: tuple[str, ...]
    request_count: int
    cost_notice: str


@dataclass(frozen=True, slots=True)
class ResearchExecution:
    plan: ResearchPlan
    raw_paths: tuple[Path, ...]
    normalized_path: Path
    report_path: Path
    manifest_path: Path | None = None
    brief_path: Path | None = None
    audit_path: Path | None = None


_MODE_OPERATIONS: dict[str, tuple[str, ...]] = {
    "niche-discovery": ("search", "statistics"),
    "trend-scan": ("trends", "search", "statistics"),
    "competitor-discovery": ("account_search",),
    "account-audit": ("account", "account_posts", "statistics", "comments"),
    "viral-breakdown": ("post_detail", "statistics", "comments"),
    "comment-mining": ("post_detail", "statistics", "comments"),
    "content-gap": ("search", "statistics", "comments"),
    "cross-platform": ("search", "statistics"),
    "brand-product": ("search", "statistics", "comments"),
    "idea-generation": ("search", "statistics", "comments"),
    "market-map": ("search", "statistics"),
}


def _headline(text: str | None) -> str:
    for line in (text or "").splitlines():
        line = line.strip().lstrip("> ")
        if line and not line.startswith("#"):
            return line[:120]
    return "未提供标题/文案"


def _hook_and_structure(text: str | None) -> tuple[str, str]:
    content = text or ""
    if any(word in content for word in ("零基础", "新手", "小白", "保姆级")):
        hook = "以新手身份和低门槛承诺切入"
    elif any(word in content for word in ("30秒", "一分钟", "一条视频")):
        hook = "以极短时间和快速结果承诺切入"
    elif any(word in content for word in ("怎么用", "如何", "手把手", "教程")):
        hook = "以具体问题或教程承诺切入"
    else:
        hook = "仅能根据公开标题/文案判断，需看视频前 5 秒复核"
    has_steps = any(token in content for token in ("1.", "2.", "3.", "第一", "第二", "从安装", "工作流"))
    structure = "问题/结果承诺 → 分步操作 → 场景演示 → 收藏或资料 CTA" if has_steps else "标题/文案承诺 → 具体演示（待视频画面复核）"
    return hook, structure


def _post_detail_lines(posts: list[Any], metrics: list[Any]) -> list[str]:
    metric_by_id = {item.post_id: item for item in metrics}
    lines: list[str] = []
    for index, post in enumerate(posts, 1):
        metric = metric_by_id.get(post.post_id)
        values = [
            f"播放 {post.views if post.views is not None else '未返回'}",
            f"赞 {post.likes if post.likes is not None else '—'}",
            f"评 {post.comments if post.comments is not None else '—'}",
            f"转 {post.shares if post.shares is not None else '—'}",
            f"藏 {post.saves if post.saves is not None else '—'}",
        ]
        rate = f"{metric.engagement_rate:.2%}" if metric and metric.engagement_rate is not None else "未计算"
        hook, structure = _hook_and_structure(post.text)
        lines.extend([
            f"{index}. 标题：{_headline(post.text)}",
            f"作者：{post.author_name or '未提供'}；发布时间：{post.published_at or '未提供'}；视频时长：{post.duration_sec or '未提供'} 秒",
            f"可见数据：{'；'.join(values)}；互动率：{rate}；播放量来源：{post.views_source or '未返回'}",
            f"开头钩子判断：{hook}；内容结构判断：{structure}",
            f"原始链接：{post.source_url}",
        ])
    return lines


def _keyword_findings(posts: list[Any], metrics: list[Any]) -> list[Finding]:
    if not posts:
        return []
    ranked = sorted(posts, key=lambda post: (post.views or 0, post.likes or 0), reverse=True)
    top = ranked[0]
    top_value = f"播放 {top.views}" if top.views is not None else f"点赞 {top.likes or '未返回'}"
    hook, structure = _hook_and_structure(top.text)
    findings = [
        Finding(
            text=f"当前样本中表现最高的是《{_headline(top.text)}》，作者为 {top.author_name or '未提供'}，{top_value}；这是样本内高表现，不等同于平台全量爆款。",
            evidence_ids=[f"post:{top.post_id}"], evidence_class="observed", section="高表现内容",
        ),
        Finding(
            text=f"该作品的初步钩子判断为“{hook}”，候选结构为“{structure}”；若无逐字稿或画面，仍需人工复核。",
            evidence_ids=[f"post:{top.post_id}"], evidence_class="interpreted", section="核心发现",
        ),
    ]
    values = _positive_values([post.views if post.views is not None else post.likes for post in posts])
    if values:
        baseline = median(values)
        top_numeric = float(top.views if top.views is not None else top.likes or 0)
        findings.append(Finding(
            text=f"样本基线以{'播放' if any(post.views is not None for post in posts) else '点赞'}中位数 {_format_count(baseline)} 计算；最高作品约为基线的 {top_numeric / baseline:.1f} 倍。",
            evidence_ids=[f"post:{post.post_id}" for post in posts],
            evidence_class="calculated",
            section="核心发现",
        ))
    buckets = {"入门教程": ("入门", "新手", "小白", "保姆级"), "工作流自动化": ("工作流", "自动化"), "案例实操": ("案例", "实操", "实测")}
    repeated = []
    for label, terms in buckets.items():
        count = sum(any(term in (post.text or "") for term in terms) for post in posts)
        if count:
            repeated.append(f"{label} {count}/{len(posts)} 条")
    if repeated:
        findings.append(Finding(
            text="样本主题覆盖：" + "；".join(repeated) + "。多个账号重复出现才可作为方向性趋势，单一账号仍按个案处理。",
            evidence_ids=[f"post:{post.post_id}" for post in posts[:5]], evidence_class="calculated", section="赛道与趋势",
        ))
        findings.extend([
            Finding(
                text=f"机会排序：先验证样本中重复出现且表现可计算的方向——{repeated[0].split()[0]}；只有一条作品出现的主题先按探索项处理。",
                evidence_ids=[f"post:{post.post_id}" for post in posts[:5]],
                evidence_class="interpreted",
                section="机会排序",
            ),
            Finding(
                text=f"可执行建议：围绕“{repeated[0].split()[0]}”制作 3 条不同切口内容，以样本中位数为基线复核；若只由单一账号贡献，不升级为平台趋势。",
                evidence_ids=[f"post:{post.post_id}" for post in posts[:5]],
                evidence_class="interpreted",
                section="建议选题与下一步",
            ),
        ])
    else:
        findings.extend([
            Finding(
                text="共同趋势判断：当前样本未形成重复的预设主题，因此只能确认高表现个案，不能升级为多个账号共同趋势。",
                evidence_ids=[f"post:{post.post_id}" for post in ranked[:3]],
                evidence_class="calculated",
                section="赛道与趋势",
            ),
            Finding(
                text="可执行建议：先对高表现与中位表现作品做人工主题归类，再决定选题，不从单条最高作品直接外推。",
                evidence_ids=[f"post:{post.post_id}" for post in ranked[:3]],
                evidence_class="interpreted",
                section="建议选题与下一步",
            ),
        ])
    return findings


def _comment_findings(comments: list[Any], post_id: str) -> list[Finding]:
    if not comments:
        return []
    signals = count_comment_signals(comments, {
        "使用与配置": ("怎么用", "教程", "安装", "配置", "设置"),
        "价格与权限": ("多少钱", "收费", "免费", "会员", "权限"),
        "故障与效果": ("不会", "报错", "失败", "太慢", "没有", "不行"),
        "资料与模板": ("资料", "模板", "文档", "链接", "代码"),
    })
    ranked = sorted(comments, key=lambda item: item.likes or 0, reverse=True)
    top_examples = [f"“{(item.text or '').strip()[:80]}”" for item in ranked[:3] if item.text]
    counts = "；".join(f"{key} {value} 条" for key, value in signals.items() if value)
    evidence = [f"comment:{item.comment_id}" for item in ranked[:3]] or [f"post:{post_id}"]
    return [Finding(
        text=f"评论需求信号（样本 {len(comments)} 条）：{counts or '未命中预设问题词'}。代表性评论：{'；'.join(top_examples) or '未返回文本'}。",
        evidence_ids=evidence, evidence_class="observed", section="评论需求",
    )]


def _window_label(request: ResearchRequest) -> str:
    if request.start_at or request.end_at:
        return f"；时间范围 {request.start_at or '未限定'} 至 {request.end_at or '未限定'}（已先过滤再排名）"
    return "；未设置时间过滤边界"


def _effective_requirements(request: ResearchRequest) -> tuple[str, ...]:
    defaults = ("mature-mode-report", *(ACCOUNT_AUDIT_REQUIREMENTS if request.mode == "account-audit" else ()))
    return tuple(dict.fromkeys((*defaults, *request.requirements)))


def _write_report(root: Path, filename: str, report: ResearchReport) -> Path:
    """Write the reader-facing report and a separate internal evidence ledger."""
    report_path = root / "reports" / filename
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report), encoding="utf-8")
    ledger_path = root / "analysis" / "findings.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(evidence_ledger(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def _positive_values(values: list[int | float | None]) -> list[float]:
    return [float(value) for value in values if value is not None and value > 0]


def _format_count(value: float | int | None) -> str:
    if value is None:
        return "未返回"
    return f"{int(round(value)):,}"


def _title_signals(text: str | None) -> set[str]:
    content = (text or "").casefold()
    groups = {
        "教程/方法": ("如何", "怎么", "教程", "手把手", "步骤", "指南"),
        "工具/产品": ("工具", "上线", "发布", "更新", "测评", "实测"),
        "Prompt/工作流": ("prompt", "提示词", "工作流", "自动化", "agent"),
        "冲突/风险": ("完蛋", "淘汰", "失业", "灭绝", "危机", "骗局", "封号", "黑暗"),
        "清单/数字": ("1个", "2个", "3个", "5个", "10个", "一文看懂", "清单"),
        "观点/解释": ("为什么", "意味着", "聊聊", "看懂", "真相", "本质"),
    }
    return {label for label, words in groups.items() if any(word in content for word in words)}


def _account_findings(account: Any, posts: list[Any], metrics: list[Any], comments: list[Any]) -> list[Finding]:
    account_evidence = [f"account:{account.account_id}"]
    post_evidence = [f"post:{post.post_id}" for post in posts]
    findings = [Finding(
        text=(
            f"账号事实：{account.name or '未返回昵称'}；简介“{account.bio or '未返回'}”；"
            f"粉丝 {_format_count(account.followers)}，作品 {_format_count(account.posts)}，"
            f"累计获赞 {_format_count(account.likes_received)}，关注 {_format_count(account.following)}。"
            "这些字段只用于描述公开账号规模，不据此推断流量来源或行业地位。"
        ),
        evidence_ids=account_evidence,
        evidence_class="observed",
        section="对标账号",
    )]
    if not posts:
        return findings

    ranked = [post for post in posts if (post.views or post.likes or 0) > 0]
    ranked.sort(key=lambda post: (post.views if post.views is not None else post.likes or 0), reverse=True)
    view_values = _positive_values([post.views for post in posts])
    like_values = _positive_values([post.likes for post in posts])
    engagement_values = [
        metric.engagement_rate for metric in metrics if metric.engagement_rate is not None
    ]
    basis = "播放" if view_values else "点赞"
    basis_values = view_values or like_values
    baseline = median(basis_values) if basis_values else None
    findings.append(Finding(
        text=(
            f"表现基线：样本 {len(posts)} 条，{basis}中位数 {_format_count(baseline)}；"
            f"点赞中位数 {_format_count(median(like_values) if like_values else None)}；"
            f"互动率中位数 {median(engagement_values):.2%}。" if engagement_values else
            f"表现基线：样本 {len(posts)} 条，{basis}中位数 {_format_count(baseline)}；"
            f"点赞中位数 {_format_count(median(like_values) if like_values else None)}；互动率因缺少有效播放量未计算。"
        ),
        evidence_ids=post_evidence,
        evidence_class="calculated",
        section="核心发现",
    ))

    if ranked:
        group_size = max(1, len(ranked) // 4)
        top_group = ranked[:group_size]
        bottom_group = ranked[-group_size:]
        top_values = [float(post.views if post.views is not None else post.likes or 0) for post in top_group]
        bottom_values = [float(post.views if post.views is not None else post.likes or 0) for post in bottom_group]
        ratio = median(top_values) / median(bottom_values) if median(bottom_values) > 0 else None
        findings.append(Finding(
            text=(
                f"分组对照：按{basis}把有效样本分为前 25% 与后 25%。前组中位数 {_format_count(median(top_values))}，"
                f"后组中位数 {_format_count(median(bottom_values))}，差距 {ratio:.1f} 倍。" if ratio is not None else
                f"分组对照：已形成前 25% 与后 25% 样本，但后组缺少可用{basis}，未计算倍数。"
            ) + f"前组代表《{_headline(top_group[0].text)}》；后组代表《{_headline(bottom_group[-1].text)}》。",
            evidence_ids=[f"post:{post.post_id}" for post in top_group + bottom_group],
            evidence_class="calculated",
            section="高表现内容",
        ))

    signal_rows = []
    for label in ("教程/方法", "工具/产品", "Prompt/工作流", "冲突/风险", "清单/数字", "观点/解释"):
        tagged = [post for post in posts if label in _title_signals(post.text)]
        values = _positive_values([post.views if post.views is not None else post.likes for post in tagged])
        if tagged:
            signal_rows.append((label, len(tagged), median(values) if values else None, tagged))
    if signal_rows:
        summary = "；".join(
            f"{label} {count} 条（{basis}中位数 {_format_count(value)}）"
            for label, count, value, _ in signal_rows
        )
        findings.append(Finding(
            text=f"标题/文案模式：{summary}。这是多标签文本分类，只说明公开标题/文案与表现的关联，不等同于视频内部结构。",
            evidence_ids=post_evidence,
            evidence_class="calculated",
            section="高表现内容",
        ))
        stable = [row for row in signal_rows if row[1] >= 2 and row[2] is not None]
        if stable:
            strongest = max(stable, key=lambda row: row[2] or 0)
            findings.append(Finding(
                text=(
                    f"可执行建议：先围绕“{strongest[0]}”做 3 条同主题不同切口的原创测试，并以账号{basis}中位数"
                    f" {_format_count(baseline)} 作为第一轮基线；不要只复制单条最高作品，也不要把标题信号写成已观察的视频钩子。"
                ),
                evidence_ids=[f"post:{post.post_id}" for post in strongest[3]],
                evidence_class="interpreted",
                section="建议选题与下一步",
            ))
        else:
            findings.append(Finding(
                text="可执行建议：当前标题模式每类不足 2 条，先按高表现组代表选题做 3 条原创测试，再用同一表现基线判断是否形成稳定打法。",
                evidence_ids=[f"post:{post.post_id}" for post in ranked[:3]] or post_evidence,
                evidence_class="interpreted",
                section="建议选题与下一步",
            ))
    else:
        findings.extend([
            Finding(
                text="标题/文案模式：当前公开文案未命中预设模式词，不能据此编造内容结构；应保留作品明细并进行人工语义归类。",
                evidence_ids=post_evidence,
                evidence_class="observed",
                section="高表现内容",
            ),
            Finding(
                text="可执行建议：先从高表现组与低表现组各选 3 条进行人工主题归类，再确定可重复方向，暂不把单条高表现写成稳定公式。",
                evidence_ids=[f"post:{post.post_id}" for post in ranked[:3]] or post_evidence,
                evidence_class="interpreted",
                section="建议选题与下一步",
            ),
        ])

    dates = []
    for post in posts:
        try:
            if post.published_at:
                dates.append(datetime.fromisoformat(post.published_at.replace("Z", "+00:00")))
        except ValueError:
            continue
    if len(dates) >= 2:
        dates.sort()
        span_days = max((dates[-1] - dates[0]).total_seconds() / 86400, 1)
        weekly = (len(dates) - 1) / span_days * 7
        findings.append(Finding(
            text=f"更新节奏：样本发布时间跨度 {dates[0].date()} 至 {dates[-1].date()}，折算约 {weekly:.1f} 条/周；该值只代表当前样本窗口。",
            evidence_ids=post_evidence,
            evidence_class="calculated",
            section="核心发现",
        ))

    if comments:
        signals = count_comment_signals(comments, {
            "使用与配置": ("怎么用", "教程", "安装", "配置", "设置"),
            "价格与权限": ("多少钱", "收费", "免费", "会员", "权限"),
            "故障与效果": ("不会", "报错", "失败", "太慢", "没有", "不行"),
            "资料与模板": ("资料", "模板", "文档", "链接", "代码"),
        })
        covered_posts = len({comment.post_id for comment in comments})
        counts = "；".join(f"{label} {count} 条" for label, count in signals.items())
        findings.append(Finding(
            text=f"评论需求：抽取 {covered_posts} 条代表作品的 {len(comments)} 条公开评论；{counts}。这是需求信号，不代表全部受众比例。",
            evidence_ids=[f"comment:{comment.comment_id}" for comment in comments[:10]],
            evidence_class="calculated",
            section="评论需求",
        ))
    return findings


def plan_request(request: ResearchRequest) -> ResearchPlan:
    if request.mode not in MODES:
        raise ValueError(f"unsupported research mode: {request.mode}")
    if request.platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {request.platform}")
    if request.mode == "trend-scan" and request.platform != "douyin":
        raise ValueError("trend-scan is currently available only for douyin")
    if not request.query.strip():
        raise ValueError("query cannot be empty")
    if request.mode == "cross-platform":
        if request.secondary_platform not in PLATFORMS or request.secondary_platform == request.platform:
            raise ValueError("cross-platform requires two platforms")
    if request.sample_pages < 1 or request.sample_pages > 3:
        raise ValueError("sample_pages must be between 1 and 3")
    if request.comment_pages < 0 or request.comment_pages > 1:
        raise ValueError("comment_pages must be between 0 and 1")
    unknown_requirements = set(_effective_requirements(request)) - REQUIREMENTS
    if unknown_requirements:
        raise ValueError(f"unsupported delivery requirements: {sorted(unknown_requirements)}")
    _parse_bound(request.start_at, "start_at")
    _parse_bound(request.end_at, "end_at")
    if request.start_at and request.end_at and _parse_bound(request.start_at, "start_at") > _parse_bound(request.end_at, "end_at"):
        raise ValueError("start_at must be earlier than end_at")

    operations = _MODE_OPERATIONS[request.mode]
    if (request.start_at or request.end_at) and "search" not in operations:
        raise ValueError("time bounds are currently supported only for search-based modes")
    if (request.start_at or request.end_at) and (request.platform != "douyin" or request.secondary_platform is not None):
        raise ValueError("strict time filtering is currently verified only for Douyin search")
    account_post_pages = request.sample_pages if "account_posts" in operations else 0
    # One account page normally contains at most 20 works. Douyin statistics
    # accepts two IDs per call, so a mature one-page audit budgets ten calls.
    account_statistics = 10 * account_post_pages if request.mode == "account-audit" and request.platform == "douyin" else 0
    account_comment_samples = 3 if request.mode == "account-audit" else 0
    keyword_comment_samples = 3 if request.mode in {"content-gap", "brand-product", "idea-generation"} else 0
    plan = CollectionPlan(
        search_pages=request.sample_pages * 2 if request.mode == "cross-platform" else (request.sample_pages if "search" in operations else 0),
        accounts=1 if any(item in operations for item in ("account", "account_search")) else 0,
        posts_per_account_pages=account_post_pages,
        post_details=1 if "post_detail" in operations else 0,
        comment_pages=account_comment_samples or keyword_comment_samples or (request.comment_pages if "comments" in operations else 0),
        trend_pages=1 if "trends" in operations else 0,
        # The statistics endpoint accepts at most two IDs. Hydrate the first
        # six search results (three calls) so visible ranking claims use real
        # play counts without turning a default run into an unbounded crawl.
        statistics=(account_statistics or (1 if "post_detail" in operations else 3)) if "statistics" in operations and request.platform == "douyin" else 0,
    )
    # A comment operation defaults to one low-cost page when explicitly requested.
    if "comments" in operations and plan.comment_pages == 0:
        plan = CollectionPlan(**{**plan.__dict__, "comment_pages": 1}) if hasattr(plan, "__dict__") else CollectionPlan(
            search_pages=plan.search_pages,
            accounts=plan.accounts,
            posts_per_account_pages=plan.posts_per_account_pages,
            post_details=plan.post_details,
            comment_pages=1,
            trend_pages=plan.trend_pages,
            statistics=plan.statistics,
        )
    count = estimate_requests(plan)
    return ResearchPlan(request.mode, request.platform, operations, count, cost_notice(request.platform, plan))


def execute_request(request: ResearchRequest, *, adapter: Any, output_root: str | Path, secondary_adapter: Any | None = None) -> ResearchExecution:
    """Execute the bounded keyword-search slice of a research request.

    Modes needing an account or post identifier are intentionally not guessed;
    callers must supply a specialized adapter invocation in a later execution
    layer. This first slice is enough for low-cost niche/trend/gap research.
    """
    plan = plan_request(request)
    if request.mode in {"viral-breakdown", "comment-mining"}:
        if not request.entity_id:
            raise ValueError("entity_id is required for this research mode")
        result = _execute_post_mode(request, plan, adapter, output_root)
    elif request.mode == "account-audit":
        if not request.entity_id:
            raise ValueError("entity_id is required for this research mode")
        result = _execute_account_mode(request, plan, adapter, output_root)
    elif request.mode == "cross-platform":
        if secondary_adapter is None:
            raise ValueError("cross-platform execution requires two adapters")
        result = _execute_cross_platform(request, plan, adapter, secondary_adapter, output_root)
    elif request.mode == "trend-scan":
        result = _execute_trend_mode(request, plan, adapter, output_root)
    elif request.mode == "competitor-discovery":
        result = _execute_competitor_mode(request, plan, adapter, output_root)
    elif request.mode in {"content-gap", "brand-product", "idea-generation", "market-map"}:
        result = _execute_specialized_keyword_mode(request, plan, adapter, output_root)
    elif "search" in plan.operations:
        result = _execute_keyword_mode(request, plan, adapter, output_root)
    else:
        raise ValueError(f"mode {request.mode} requires an explicit entity and is not keyword-executable")
    manifest = write_manifest(
        output_root,
        platform=request.platform,
        operation=request.mode,
        parameters={
            "query": request.query,
            "entity_id": request.entity_id,
            "secondary_platform": request.secondary_platform,
            "sample_pages": request.sample_pages,
            "comment_pages": request.comment_pages,
            "start_at": request.start_at,
            "end_at": request.end_at,
        },
        request_count=len(result.raw_paths),
        raw_paths=result.raw_paths,
        failures=(),
    )
    brief = Path(output_root) / "brief.json"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(json.dumps({
        "mode": request.mode,
        "platform": request.platform,
        "secondary_platform": request.secondary_platform,
        "query": request.query,
        "entity_id": request.entity_id,
        "sample_pages": request.sample_pages,
        "comment_pages": request.comment_pages,
        "start_at": request.start_at,
        "end_at": request.end_at,
        "planned_requests": result.plan.request_count,
        "actual_requests": len(result.raw_paths),
        "requirements": list(_effective_requirements(request)),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_path = write_delivery_audit(output_root, audit_delivery(output_root, result.report_path))
    return replace(result, manifest_path=manifest, brief_path=brief, audit_path=audit_path)


def _execute_keyword_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    posts, raw_paths = _search_posts(request, adapter, store)
    raw_paths += _hydrate_statistics(posts, adapter, store, request.platform)
    write_quality(root, audit_posts(posts))
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    quality = audit_posts(posts)
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary=f"关键词“{request.query}”完成低成本样本研究。",
        task=f"研究模式：{request.mode}；查询：{request.query}",
        coverage=f"{len(posts)} 条作品，最多 {request.sample_pages} 页搜索{_window_label(request)}，身份字段完整 {quality.complete_identity}/{quality.total}，指标缺失率 {quality.missing_metric_ratio:.1%}，原始证据已保存。",
        post_details=_post_detail_lines(posts, metrics),
        findings=_keyword_findings(posts, metrics) + ([Finding(
            text=f"样本中 {sum(metric.relative_performance is not None for metric in metrics)} 条作品可计算账号内相对表现。",
            evidence_ids=[f"post:{post.post_id}" for post in posts[:3]], evidence_class="calculated",
        )] if posts else []),
        limitations=["本次结论聚焦关键词搜索样本，用于近期方向筛选；不外推为平台全量趋势或账号长期表现。"],
        confidence="low" if len(posts) < 10 else "medium",
    )
    report_path = _write_report(root, f"{request.mode}-{request.platform}.md", report)
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _execute_post_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    if request.platform == "douyin":
        post = adapter.get_post(aweme_id=request.entity_id)
        statistics = adapter.get_video_statistics([post.post_id]) if "statistics" in plan.operations else {}
        comments_page = adapter.get_comments(request.entity_id) if "comments" in plan.operations else None
    else:
        post = adapter.get_post(note_id=request.entity_id)
        statistics = {}
        comments_page = adapter.get_comments(note_id=request.entity_id) if "comments" in plan.operations else None
    post_raw = store.save(request.platform, "post-detail", _adapter_last_raw(adapter, "post detail"))
    comments = comments_page.items if comments_page else []
    raw_paths = [post_raw]
    if comments_page:
        comments_raw = store.save(request.platform, "comments", comments_page.raw)
        raw_paths.append(comments_raw)
    if statistics:
        values = statistics.get(post.post_id, {})
        for field in ("views", "likes", "comments", "shares", "saves"):
            metric = {"views": "play_count", "likes": "digg_count", "comments": "comment_count", "shares": "share_count", "saves": "collect_count"}[field]
            value = values.get(metric)
            if value is not None:
                setattr(post, field, value)
                if field == "views":
                    post.views_source = "statistics"
        stats_raw = store.save(request.platform, "statistics", getattr(adapter, "last_statistics_raw", {}))
        raw_paths.append(stats_raw)
    write_quality(root, audit_posts([post]))
    post.raw_path = str(post_raw)
    normalized = write_normalized(root, "posts", [post])
    metrics = compute_post_metrics([post])[0]
    evidence = [f"post:{post.post_id}"]
    if comments:
        evidence.append(f"comment:{comments[0].comment_id}")
    finding_text = f"作品 {post.post_id} 的互动率为 {metrics.engagement_rate:.4f}。" if metrics.engagement_rate is not None else f"作品 {post.post_id} 缺少足够播放数据，未计算互动率。"
    hook, structure = _hook_and_structure(post.text)
    findings = [
        Finding(text=finding_text, evidence_ids=evidence, evidence_class="calculated"),
        Finding(
            text=f"文本层拆解：公开标题/文案呈现“{hook}”；候选结构为“{structure}”。这不是视频画面或逐字稿结论。",
            evidence_ids=[f"post:{post.post_id}"], evidence_class="interpreted", section="高表现内容",
        ),
        Finding(
            text="可执行建议：先复用作品的选题问题与结果承诺，不复制原句；发布后用同口径互动率和评论问题验证是否适合继续扩展。",
            evidence_ids=evidence, evidence_class="interpreted", section="建议选题与下一步",
        ),
    ] + _comment_findings(comments, post.post_id)
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary="完成一条作品的详情与评论低成本研究。",
        task=f"研究模式：{request.mode}；作品：{request.entity_id}",
        coverage=f"1 条作品、{len(comments)} 条评论。",
        post_details=_post_detail_lines([post], [metrics]),
        findings=findings,
        limitations=["本次结论聚焦单条公开作品，用于内容拆解；不外推为该账号整体表现或同类作品的普遍规律。"],
        confidence="low",
    )
    report_path = _write_report(root, f"{request.mode}-{request.platform}.md", report)
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _execute_account_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    if request.platform == "douyin":
        account = adapter.get_account(request.entity_id)
        cursor: str | None = "0"
    else:
        account = adapter.get_account(user_id=request.entity_id)
        cursor = ""
    account_raw = store.save(request.platform, "account", _adapter_last_raw(adapter, "account"))
    account.raw_path = str(account_raw)
    write_normalized(root, "accounts", [account])
    posts: list[Any] = []
    raw_paths = [account_raw]
    for _ in range(request.sample_pages):
        if request.platform == "douyin":
            page = adapter.get_account_posts(request.entity_id, cursor=cursor or "0")
        else:
            page = adapter.get_account_posts(user_id=request.entity_id, cursor=cursor or "")
        posts_raw = store.save(request.platform, "account-posts", page.raw)
        raw_paths.append(posts_raw)
        for post in page.items:
            post.raw_path = str(posts_raw)
            posts.append(post)
        if not page.has_more or page.next_cursor is None:
            break
        cursor = page.next_cursor

    raw_paths += _hydrate_statistics(posts, adapter, store, request.platform, limit=len(posts))
    write_quality(root, audit_posts(posts))
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    quality = audit_posts(posts)
    ranked = sorted(
        [post for post in posts if (post.views or post.likes or 0) > 0],
        key=lambda post: (post.views if post.views is not None else post.likes or 0),
        reverse=True,
    )
    representatives: list[Any] = []
    for candidate in ([*ranked[:2], ranked[len(ranked) // 2]] if ranked else []):
        if all(candidate.post_id != existing.post_id for existing in representatives):
            representatives.append(candidate)
    comments: list[Any] = []
    for post in representatives[:3]:
        if request.platform == "douyin":
            comments_page = adapter.get_comments(post.post_id)
        else:
            comments_page = adapter.get_comments(note_id=post.post_id)
        comments.extend(comments_page.items)
        raw_paths.append(store.save(request.platform, "comments", comments_page.raw))
    if comments:
        write_normalized(root, "comments", comments)
    report = ResearchReport(
        title=f"{account.name or request.entity_id}｜{request.platform} 对标账号审计",
        summary=f"已从账号事实、表现基线、作品分组、标题/文案模式、评论需求和可执行借鉴六个层面完成审计。",
        task=f"分析公开账号 {account.source_url}；默认目标是判断账号如何做内容、什么表现稳定、哪些打法可借鉴。",
        coverage=(
            f"1 个账号、{len(posts)} 条近期作品、{len(comments)} 条公开评论；"
            f"身份字段完整 {quality.complete_identity}/{quality.total}，指标缺失率 {quality.missing_metric_ratio:.1%}。"
        ),
        post_details=_post_detail_lines(posts, metrics),
        findings=_account_findings(account, posts, metrics, comments),
        limitations=[
            f"本次使用最近 {request.sample_pages} 页公开作品样本，不代表账号全部历史作品。",
            "标题/文案模式是文本层分类；未读取视频画面、逐字稿和完播率，因此不声称观察到真实前三秒钩子或完整视频结构。",
            "评论来自最多 3 条代表作品，用于发现问题方向，不作为全部受众占比。",
        ],
        confidence="low" if len(posts) < 10 else "medium",
        confidence_note="公开账号事实和样本内统计可复算；策略结论仅在当前样本范围内成立。",
        validation_steps=["后续复核时保持同一口径增加作品页数，并比较模式的持续性，而不是只追踪单条最高播放作品。"],
    )
    report_path = _write_report(root, f"account-audit-{request.platform}.md", report)
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _execute_cross_platform(request: ResearchRequest, plan: ResearchPlan, adapter: Any, secondary_adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    first_posts, first_raw_paths = _search_posts(request, adapter, store)
    secondary_request = replace(request, platform=request.secondary_platform or "", secondary_platform=None)
    second_posts, second_raw_paths = _search_posts(secondary_request, secondary_adapter, store)
    first_raw_paths += _hydrate_statistics(first_posts, adapter, store, request.platform)
    second_raw_paths += _hydrate_statistics(second_posts, secondary_adapter, store, request.secondary_platform or "")
    posts = first_posts + second_posts
    write_quality(root, audit_posts(posts))
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    evidence = [f"post:{post.post_id}" for post in posts[:4]]
    platform_rows = []
    for platform, platform_posts in ((request.platform, first_posts), (request.secondary_platform, second_posts)):
        values = _positive_values([post.views if post.views is not None else post.likes for post in platform_posts])
        platform_rows.append(f"{platform} {len(platform_posts)} 条，平台内主指标中位数 {_format_count(median(values) if values else None)}")
    findings = [
        Finding(text="平台内基线：" + "；".join(platform_rows) + "。指标仅在各平台内部解释，不直接横向比较原始数值。", evidence_ids=evidence, evidence_class="calculated", section="核心发现"),
        Finding(text="跨平台趋势判断：只有在两个平台均出现的主题才能写成共同方向；当前先保留各平台作品明细和平台内高表现样本，避免把单平台个案外推。", evidence_ids=evidence, evidence_class="interpreted", section="赛道与趋势"),
        Finding(text="可执行建议：同一选题先分别适配两平台表达，再以各自平台中位数衡量；不要用抖音播放量直接和小红书点赞/收藏量比较。", evidence_ids=evidence, evidence_class="interpreted", section="建议选题与下一步"),
    ]
    report = ResearchReport(
        title="cross-platform research",
        summary=f"完成“{request.query}”在两个平台的一页样本对照。",
        task=f"研究模式：cross-platform；平台：{request.platform}、{request.secondary_platform}",
        coverage=f"{request.platform} {len(first_posts)} 条；{request.secondary_platform} {len(second_posts)} 条。",
        post_details=_post_detail_lines(posts, metrics),
        findings=findings,
        limitations=["本次比较同一关键词的一页平台内样本；只观察结构和平台内相对表现，不直接比较平台原始热度分。"],
        confidence="low",
    )
    report_path = _write_report(root, "cross-platform.md", report)
    return ResearchExecution(plan, tuple(first_raw_paths + second_raw_paths), normalized, report_path)


def _execute_trend_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    trends_page = adapter.get_trends()
    raw_path = store.save(request.platform, "trends", trends_page.raw)
    trend_path = write_normalized(root, "trends", trends_page.items)
    posts, search_raw_paths = _search_posts(request, adapter, store)
    search_raw_paths += _hydrate_statistics(posts, adapter, store, request.platform)
    write_normalized(root, "posts", posts)
    write_quality(root, audit_posts(posts))
    metrics = compute_post_metrics(posts)
    matching = [item for item in trends_page.items if request.query.casefold() in item.title.casefold()]
    trend_evidence = [f"trend:{item.trend_id}" for item in (matching or trends_page.items[:5])]
    trend_text = (
        "热榜中直接命中：" + "；".join(f"#{item.rank or '—'} {item.title}" for item in matching[:5])
        if matching else f"当前热榜未直接命中“{request.query}”；趋势判断主要依据关键词作品的重复出现和表现，不能把热榜快照当作持续趋势。"
    )
    report = ResearchReport(
        title=f"{request.platform} trend-scan",
        summary=f"完成“{request.query}”的热榜快照、关键词作品和样本表现三层趋势扫描。",
        task=f"研究模式：trend-scan；主题：{request.query}",
        coverage=f"{len(trends_page.items)} 条趋势项、{len(posts)} 条关键词作品{_window_label(request)}。",
        post_details=_post_detail_lines(posts, metrics),
        findings=[Finding(text=trend_text, evidence_ids=trend_evidence or [f"raw:{raw_path.name}"], evidence_class="observed", section="赛道与趋势")] + _keyword_findings(posts, metrics),
        limitations=["趋势数据是当前时点的公开快照，用于发现观察方向；持续性需要结合后续时间窗口复核。"],
        confidence="low" if len(posts) < 10 else "medium",
    )
    report_path = _write_report(root, "trend-scan.md", report)
    return ResearchExecution(plan, tuple([raw_path, *search_raw_paths]), trend_path, report_path)


def _execute_competitor_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    page = adapter.search_accounts(request.query)
    raw_path = store.save(request.platform, "account-search", page.raw)
    normalized = write_normalized(root, "accounts", page.items)
    evidence = [f"account:{account.account_id}" for account in page.items[:5]]
    account_findings = [
        Finding(
            text=(
                f"候选 {index}：{account.name or '未返回昵称'}；粉丝 {_format_count(account.followers)}，"
                f"作品 {_format_count(account.posts)}，累计获赞 {_format_count(account.likes_received)}；主页 {account.source_url}。"
            ),
            evidence_ids=[f"account:{account.account_id}"], evidence_class="observed", section="对标账号",
        )
        for index, account in enumerate(page.items[:10], 1)
    ]
    if page.items:
        account_findings.append(Finding(
            text="可执行建议：先从候选中选择内容定位最接近的 3 个账号进入 account-audit，比较近期作品中位数和高低表现结构；粉丝数只用于规模分层，不直接等同于对标价值。",
            evidence_ids=evidence, evidence_class="interpreted", section="建议选题与下一步",
        ))
    report = ResearchReport(
        title=f"{request.platform} competitor-discovery",
        summary=f"完成“{request.query}”的候选对标账号发现。",
        task=f"研究模式：competitor-discovery；关键词：{request.query}",
        coverage=f"{len(page.items)} 个候选账号。",
        findings=account_findings or [Finding(text="当前搜索未返回可验证候选账号。", evidence_ids=[f"raw:{raw_path.name}"], evidence_class="observed", section="对标账号")],
        limitations=["候选账号用于建立观察名单；是否适合长期对标，需要结合账号作品样本和内容目标继续判断。"],
        confidence="low",
    )
    report_path = _write_report(root, "competitor-discovery.md", report)
    return ResearchExecution(plan, (raw_path,), normalized, report_path)


def _execute_specialized_keyword_mode(request: ResearchRequest, plan: ResearchPlan, adapter: Any, output_root: str | Path) -> ResearchExecution:
    root = Path(output_root)
    store = RawStore(root)
    posts, raw_paths = _search_posts(request, adapter, store)
    raw_paths += _hydrate_statistics(posts, adapter, store, request.platform)
    ranked = sorted(posts, key=lambda post: (post.views or 0, post.likes or 0), reverse=True)
    comments: list[Any] = []
    for post in ranked[:3] if "comments" in plan.operations else []:
        if request.platform == "douyin":
            page = adapter.get_comments(post.post_id)
        else:
            page = adapter.get_comments(note_id=post.post_id)
        comments.extend(page.items)
        raw_paths.append(store.save(request.platform, "comments", page.raw))
    if comments:
        write_normalized(root, "comments", comments)
    write_quality(root, audit_posts(posts))
    normalized = write_normalized(root, "posts", posts)
    metrics = compute_post_metrics(posts)
    quality = audit_posts(posts)
    evidence = [f"post:{post.post_id}" for post in posts[:5]] or [f"raw:{raw_paths[0].name}"]
    labels = {
        "content-gap": ("内容空白", "供给与需求"),
        "brand-product": ("品牌/产品", "公开提及与疑问"),
        "idea-generation": ("证据化选题", "可追溯选题"),
        "market-map": ("市场结构", "账号与主题结构"),
    }
    section, analysis = labels[request.mode]
    mode_findings: list[Finding] = []
    if request.mode == "content-gap":
        mode_findings.append(Finding(
            text=f"内容空白判断：当前从 {len(posts)} 条供给作品和 {len(comments)} 条代表评论交叉观察；只有评论中重复出现、但高表现作品未充分回答的问题才列为空白，当前结果仍限于样本。",
            evidence_ids=evidence + [f"comment:{comment.comment_id}" for comment in comments[:10]], evidence_class="interpreted", section="内容空白",
        ))
    elif request.mode == "brand-product":
        mode_findings.extend(_comment_findings(comments, ranked[0].post_id if ranked else "unknown"))
    elif request.mode == "idea-generation" and comments:
        mode_findings.extend(_comment_findings(comments, ranked[0].post_id if ranked else "unknown"))
    elif request.mode == "market-map":
        author_count = len({post.author_id for post in posts if post.author_id})
        mode_findings.append(Finding(
            text=f"市场参与者：当前样本覆盖 {author_count} 个可识别账号；这里只作为关键词市场的观察名单，不等同于完整玩家地图。",
            evidence_ids=evidence, evidence_class="calculated", section="对标账号",
        ))
    report = ResearchReport(
        title=f"{request.platform} {request.mode}",
        summary=f"完成“{request.query}”的{section}分析。",
        task=f"研究模式：{request.mode}；关键词：{request.query}",
        coverage=f"{len(posts)} 条搜索作品，{sum(metric.engagement_rate is not None for metric in metrics)} 条可计算互动率{_window_label(request)}；身份字段完整 {quality.complete_identity}/{quality.total}，指标缺失率 {quality.missing_metric_ratio:.1%}。",
        post_details=_post_detail_lines(posts, metrics),
        findings=_keyword_findings(posts, metrics) + mode_findings + [Finding(text=f"本次以 {analysis} 为分析框架，样本外信息不写成结论。", evidence_ids=evidence, evidence_class="interpreted")],
        limitations=["本次以一页关键词样本识别方向，不把样本外信息写成结论；建议用后续样本验证供需和选题持续性。"],
        confidence="low",
    )
    report_path = _write_report(root, f"{request.mode}-{request.platform}.md", report)
    return ResearchExecution(plan, tuple(raw_paths), normalized, report_path)


def _search_posts(request: ResearchRequest, adapter: Any, store: RawStore) -> tuple[list[Any], list[Path]]:
    cursor: str | None = "0" if request.platform == "douyin" else None
    posts: list[Any] = []
    raw_paths: list[Path] = []
    for _ in range(request.sample_pages):
        page = adapter.search_posts(request.query, cursor=cursor)
        raw_path = store.save(request.platform, "search", page.raw)
        raw_paths.append(raw_path)
        for post in page.items:
            post.raw_path = str(raw_path)
            posts.append(post)
        if not page.has_more or page.next_cursor is None:
            break
        cursor = page.next_cursor
    filtered = _filter_posts(posts, request.start_at, request.end_at)
    filter_report = store.root / "analysis" / "search-filter.json"
    filter_report.parent.mkdir(parents=True, exist_ok=True)
    filter_report.write_text(json.dumps({
        "raw_result_count": len(posts),
        "filtered_result_count": len(filtered),
        "start_at": request.start_at,
        "end_at": request.end_at,
        "excluded_count": len(posts) - len(filtered),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return filtered, raw_paths


def _parse_bound(value: str | None, name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 datetime") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _filter_posts(posts: list[Any], start_at: str | None, end_at: str | None) -> list[Any]:
    start = _parse_bound(start_at, "start_at")
    end = _parse_bound(end_at, "end_at")
    if not start and not end:
        return posts
    kept: list[Any] = []
    for post in posts:
        published = _parse_bound(post.published_at, "published_at")
        if published is None:
            continue
        if start and published < start:
            continue
        if end and published > end:
            continue
        kept.append(post)
    return kept


def _hydrate_statistics(
    posts: list[Any], adapter: Any, store: RawStore, platform: str, *, limit: int = 6
) -> list[Path]:
    """Fill real public view metrics for a bounded search sample."""
    if platform != "douyin" or not posts or not hasattr(adapter, "get_video_statistics"):
        return []
    raw_paths: list[Path] = []
    for offset in range(0, min(len(posts), limit), 2):
        batch = posts[offset:offset + 2]
        stats = adapter.get_video_statistics([post.post_id for post in batch])
        for post in batch:
            values = stats.get(post.post_id, {})
            mapping = {"views": "play_count", "likes": "digg_count", "comments": "comment_count", "shares": "share_count", "saves": "collect_count"}
            for field, key in mapping.items():
                if values.get(key) is not None:
                    setattr(post, field, values[key])
                    if field == "views":
                        post.views_source = "statistics"
        raw_paths.append(store.save(platform, "statistics", getattr(adapter, "last_statistics_raw", {})))
    return raw_paths


def _adapter_last_raw(adapter: Any, operation: str) -> dict[str, Any]:
    raw = getattr(adapter, "last_raw", None)
    if not isinstance(raw, dict):
        raise RuntimeError(f"adapter did not retain the raw response for {operation}")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded qiqi-media-research task")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--entity-id")
    parser.add_argument("--secondary-platform", choices=sorted(PLATFORMS))
    parser.add_argument("--sample-pages", type=int, default=1)
    parser.add_argument("--start-at", help="ISO-8601 UTC or timezone-aware lower bound")
    parser.add_argument("--end-at", help="ISO-8601 UTC or timezone-aware upper bound")
    parser.add_argument("--require", action="append", choices=sorted(REQUIREMENTS), default=[], help="Evidence-backed output required for delivery; repeat as needed")
    parser.add_argument("--out", default="research-output")
    args = parser.parse_args()
    request = ResearchRequest(mode=args.mode, platform=args.platform, query=args.query, entity_id=args.entity_id, secondary_platform=args.secondary_platform, sample_pages=args.sample_pages, start_at=args.start_at, end_at=args.end_at, requirements=tuple(args.require))
    plan = plan_request(request)
    print(plan.cost_notice)
    if plan.request_count > 20:
        parser.error("planned calls exceed the approval threshold")
    from scripts.api_client import TikHubClient
    from adapters.douyin import DouyinAdapter
    from adapters.xiaohongshu import XiaohongshuAdapter
    client = TikHubClient()
    def make_adapter(platform: str):
        return DouyinAdapter(client) if platform == "douyin" else XiaohongshuAdapter(client)

    adapter = make_adapter(args.platform)
    secondary_adapter = make_adapter(args.secondary_platform) if args.secondary_platform else None
    result = execute_request(request, adapter=adapter, secondary_adapter=secondary_adapter, output_root=args.out)
    print(f"报告已生成：{result.report_path}")
    if result.audit_path:
        audit = json.loads(result.audit_path.read_text(encoding="utf-8"))
        print(f"交付验收：{audit['status']}（{result.audit_path}）")
        if audit["status"] == "failed":
            print("当前阶段尚未满足全部交付合同；组合研究可继续补证，最终必须重新运行 delivery_audit。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
