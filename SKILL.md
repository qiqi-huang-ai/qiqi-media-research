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

## 执行流程

1. 用 `templates/research-brief.md` 明确研究问题、平台、时间窗、最小样本和排除项。
2. 运行 `python -m scripts.doctor`。缺少 `TIKHUB_API_KEY` 时停止；不得请求、显示、保存或记录密钥。
3. 读取 `references/platform-capabilities.md`，只使用当前平台可用的能力。
4. 用 `scripts.collect.CollectionPlan` 估算调用次数并说明端点族。默认先取 1–3 个样本；超过 20 次调用须先取得用户明确同意。
5. 遇到 `401/403` 停止并提示检查权限；遇到 `402` 停止并提示额度或计费问题，不自动重试付费失败。
6. 每次请求先以 `RawStore` 保存原始响应，再写入 `normalized/*.jsonl` 和不含凭证的 `manifest.json`。
7. 先运行 `scripts.analyze` 与 `scripts.score` 的确定性计算，再进行语义解释。不得让语言模型改写原始数值。
8. 用 `scripts.report` 输出报告。每条关键发现必须包含证据类别、evidence ID；同时写明覆盖范围、缺失字段、局限与置信度。

## 数据规则

- 缺失字段保持 `null`，不得补零、估算或借用其他指标。
- 小红书收藏与抖音分享是不同指标，不得合并成未标注的互动量。
- 跨平台只比较同名同义指标或平台内标准化结果，不直接比较平台热度分。
- 原始证据、标准化数据、计算结果和解释结论分层保存。
- 遵守 `references/safety.md`；只处理公开数据。

按需读取：数据结构见 `references/schemas.md`，评分见 `references/scoring.md`，证据等级见 `references/evidence.md`，端点见 `references/api-endpoints.md`。
