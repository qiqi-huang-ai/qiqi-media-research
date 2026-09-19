---
name: qiqi-media-research
description: 使用 TikHub REST API 研究公开社媒数据，完成赛道、趋势、对标账号、账号审计、爆款、评论需求、内容空白、跨平台、品牌产品、选题和市场地图分析。已验证平台为抖音和小红书；不用于内容发布、私密数据或绕过平台限制。
---

# qiqi-media-research

研究公开社媒数据并生成可回查证据的报告。代码适配已验证：抖音、小红书；发布包中的状态以 `references/platform-capabilities.md` 为准，用户环境的真实接口仍需少量验收。

## 路由

只支持以下 11 种模式：

`niche-discovery`、`trend-scan`、`competitor-discovery`、`account-audit`、`viral-breakdown`、`comment-mining`、`content-gap`、`cross-platform`、`brand-product`、`idea-generation`、`market-map`。

根据用户目标选择一个主模式；需要组合时列出主次关系。每种模式的输入、最小调用和输出见 `references/research-modes.md`。不要增加写稿、封面、剪辑、发布、发布后复盘或账号管理功能。

用户提示词很短时，读取 [references/mature-delivery.md](references/mature-delivery.md) 并自动补全该模式的成熟交付合同，不要把缺少细项理解为只需输出概览。只有研究对象缺失、链接无法解析、平台冲突或预计超过 20 次调用时才追问。主页链接或“分析这个博主”路由为 `account-audit`，并额外读取 [references/account-audit.md](references/account-audit.md)。

## 执行流程

1. 用 `templates/research-brief.md` 明确研究问题、平台、时间窗、最小样本和排除项。
2. 运行 `python3 -m scripts.doctor`。缺少 `TIKHUB_API_KEY` 时停止；不得请求、显示、保存或记录密钥。
3. 读取 `references/platform-capabilities.md`，只使用当前平台可用的能力。
4. 用 `scripts.collect.CollectionPlan` 估算调用次数并说明端点族。默认先取 1–3 个样本；超过 20 次调用须先取得用户明确同意。
5. 遇到 `401/403` 停止并提示检查权限；遇到 `402` 停止并提示额度或计费问题，不自动重试付费失败。
6. 每次请求先以 `RawStore` 保存原始响应，再写入 `normalized/*.jsonl` 和不含凭证的 `manifest.json`。
7. 先运行 `scripts.analyze` 与 `scripts.score` 的确定性计算，再进行语义解释。不得让语言模型改写原始数值。
8. 用 `scripts.report` 输出报告。每条关键发现必须在 `analysis/findings.json` 中保留内部证据类别和 evidence ID；面向用户的 Markdown 和 PDF 只呈现自然语言，不显示机器标签。局限部分使用“结论层级、研究边界、下一步验证”，不要写成缺陷清单。
9. 研究正文完成后，必须额外生成可视化 PDF；按 [references/visual-pdf.md](references/visual-pdf.md) 渲染、检查后交付。PDF 只呈现已有证据，不得替代 Markdown 或制造结论。
10. 搜索类研究必须输出作品级明细：标题、作者、发布时间、原始链接、播放量及可见互动指标。抖音播放量必须先走独立统计端点；详情接口的 `0` 只能表示未取到，不得写成零播放。
11. 对“热门原因、用户痛点、开头钩子、内容结构”逐项区分数据事实、样本推断和待验证假设。没有逐字稿或视频画面时，只能说“基于标题/文案的初步判断”，不能冒充已完成视频拆解。
12. 搜索结果必须按 `published_at` 做本地时间过滤；用户给出“最近 N 天”时，先换算成明确的带时区 `start_at/end_at`，并在 `brief.json` 和报告中记录原始样本、过滤后样本及时间边界。
13. 每次执行都写出 `brief.json` 和 `analysis/data-quality.json`。质量检查发现身份字段缺失、指标缺失或重复作品时，要降低结论层级并在报告中说明，不得用占位数字补齐。
14. 交付前对最终 Markdown 运行 `python3 -m scripts.delivery_audit <研究根目录> --report <最终报告>`，再读取 `analysis/delivery-audit.json`：`failed` 不得包装成成熟报告；`ready_with_caveats` 必须把具体缺口写入研究边界；只有 `ready` 才能声称数据链路验收通过。
15. 报告不能只列 Top 内容：凡模式涉及账号、选题或趋势，都要建立中位数基线，并把高表现与普通/低表现样本进行对照。不能计算时明确说明缺少哪类公开数据。

用户同时要求热门内容、用户痛点和选题时，不得只跑一次关键词搜索。组合执行：搜索与时间过滤 → 高表现及普通基线作品详情/统计 → 代表作品评论 → 评论聚合 → 选题。各阶段共享已有原始数据，避免重复调用。

把用户明确要求映射为交付合同并写入 `requirements`：时间范围=`time-window`，作品信息=`post-metadata`，真实可见指标=`visible-metrics`，评论痛点=`comment-insights`，爆款/趋势区分=`trend-distinction`，选题=`content-ideas`，文本层钩子/结构=`text-hook-structure`。验收器会逐项查证；不要省略用户已经提出的要求。

报告字段、作品明细和 PDF 单一来源规则见 [references/report-quality.md](references/report-quality.md)。

## 数据规则

- 缺失字段保持 `null`，不得补零、估算或借用其他指标。
- 小红书收藏与抖音分享是不同指标，不得合并成未标注的互动量。
- 跨平台只比较同名同义指标或平台内标准化结果，不直接比较平台热度分。
- 原始证据、标准化数据、计算结果和解释结论分层保存。
- 遵守 `references/safety.md`；只处理公开数据。

按需读取：数据结构见 `references/schemas.md`，评分见 `references/scoring.md`，证据等级见 `references/evidence.md`，端点见 `references/api-endpoints.md`。
