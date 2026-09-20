# qiqi-media-research

一个面向自媒体研究的开源 Skill。它通过 TikHub REST API 采集公开社媒数据，把原始证据、统一数据、确定性计算和 AI 解读分开，最终生成可回查来源的研究报告。

用户可以只输入“分析这个博主 + 主页链接”“研究最近 7 天某个主题”或“帮我找选题”。Skill 会按研究模式自动补全成熟交付合同，建立数据基线、分组对照和行动建议；短提示词不会降级成简单账号简介或搜索摘要。

## 平台状态

首版只适配抖音和小红书。脱敏样本、字段映射和离线流程已验证；在你的 TikHub 账号上完成少量真实调用前，接口能力仍标记为 `available-unverified`。其他平台暂不支持。

## 安装

- Codex：按根目录 `SKILL.md` 使用，`agents/openai.yaml` 提供界面信息。
- Claude Code：通过 `CLAUDE.md` 路由到根 Skill。
- Cursor：保留 `.cursor/rules/qiqi-media-research.mdc`。
- WorkBuddy：使用 `workbuddy/SKILL.md` 作为入口。

你可以给用户两种入口：安装包或 GitHub 地址 `https://github.com/qiqi-huang-ai/qiqi-media-research`。安装完成后，让 AI 在 Skill 根目录执行以下命令：它会创建隔离 `.venv` 并安装运行依赖，用户不需要手动敲 pip 命令。

```bash
python3 -m scripts.bootstrap --setup
```

运行环境需要 Python 3.11+；PDF 渲染依赖 ReportLab，会随安装自动安装。开发测试才需要执行 `python3 -m pip install -e '.[dev]'`。两种入口、AI 初始化提示词和密钥边界见 [references/first-run.md](references/first-run.md)。

## 配置 TIKHUB_API_KEY

从 TikHub 获取自己的 Key，只保存在 WorkBuddy/Codex 的安全环境变量或本机环境变量。不要把 Key 发给 AI；AI 只能检查它是否已配置：

```bash
export TIKHUB_API_KEY="你的本地Key"
```

不要把 Key 写进配置文件、提示词、截图、日志或 GitHub。

## 运行诊断

```bash
python3 -m scripts.doctor
```

诊断不会请求 TikHub 或产生费用，只显示 Key 是 `configured` 还是 `missing`。

## 命令行运行

每次运行先显示调用计划；默认只取 1 页。需要扩样本时显式传入 `--sample-pages 2` 或 `3`，调用上限仍受 20 次确认规则约束。

```bash
python3 -m scripts.research_runner \
  --mode niche-discovery --platform douyin --query "AI 表格教程" \
  --out research-output/ai-table
```

需要严格限定时间范围时，传入带时区的 ISO-8601 边界；结果会先过滤再排名：

```bash
python3 -m scripts.research_runner \
  --mode niche-discovery --platform douyin --query "WorkBuddy" \
  --start-at "2026-09-12T00:00:00+08:00" \
  --end-at "2026-09-19T23:59:59+08:00" \
  --require time-window --require post-metadata --require visible-metrics
```

`--require` 是交付合同，可重复使用。通用合同包括：`time-window`、`post-metadata`、`visible-metrics`、`comment-insights`、`trend-distinction`、`content-ideas`、`text-hook-structure`；账号合同包括：`account-profile`、`account-baseline`、`account-patterns`、`top-bottom-comparison`、`actionable-recommendations`。单个采集阶段可以暂时显示 `failed` 并继续补证；最终必须运行 `python3 -m scripts.delivery_audit ... --report ...`，该命令在证据缺失时返回失败状态，结果不得作为成熟交付。

`account-audit` 默认交付决策报告：账号定位与内容角色、爆款规律与反例、内容策略地图、公开受众需求画像、可借鉴方向矩阵和验证计划。完整原始作品明细单独写入 `analysis/evidence-pack.md`，主报告和 PDF 只呈现精选证据与行动判断。内部 evidence ID 写入 `analysis/findings.json`，不会出现在给用户阅读的 Markdown 或 PDF 中。

跨平台研究必须提供第二个平台：

```bash
python3 -m scripts.research_runner \
  --mode cross-platform --platform douyin --secondary-platform xiaohongshu \
  --query "AI 会议纪要" --sample-pages 1
```

小红书暂不支持 `trend-scan`；详情和评论研究需要提供对应平台的公开 `--entity-id`。

## 第一次低成本抖音示例

> 研究抖音“AI 表格教程”。先做 1 页搜索和 1 条作品详情，告诉我预计调用次数后再开始。

## 第一次低成本小红书示例

> 研究小红书“AI 会议纪要”。先看 1 页搜索结果和 1 篇笔记，不扩展评论采集。

## 11 种研究模式

`niche-discovery`、`trend-scan`、`competitor-discovery`、`account-audit`、`viral-breakdown`、`comment-mining`、`content-gap`、`cross-platform`、`brand-product`、`idea-generation`、`market-map`。详见 `references/research-modes.md`。

## 输出目录

`research-output/raw/` 保存原始响应，`normalized/` 保存统一 JSONL，`analysis/data-quality.json` 保存字段级质量检查，`analysis/findings.json` 保存内部证据台账，`analysis/search-filter.json` 保存时间过滤结果，`analysis/delivery-audit.json` 给出最终交付状态，`brief.json` 记录研究边界和计划/实际调用量，`manifest.json` 记录实际调用清单（不含凭证）。搜索类报告会逐条呈现标题、作者、发布时间、链接、播放量和互动指标，并对热门原因、评论痛点、钩子与结构标明事实/推断边界。

每次研究正文完成后，还会生成一份亮色科技风的可视化 PDF。PDF 规范、命令和验收要求见 [references/visual-pdf.md](references/visual-pdf.md)。

## 成本与数据边界

TikHub 的额度、价格和接口状态可能变化，本项目不提供免费额度。抖音 Search 单独纳入计费预估。默认从 1–3 个样本开始，计划超过 20 次调用时必须再次确认。只处理公开数据，不绕过权限。

抖音播放量使用独立的作品统计端点补取；详情接口返回 `0` 时会继续查询真实统计，不会把接口缺失误报为零播放。

## 测试与贡献

```bash
python3 -m pytest -v
python3 -m compileall -q adapters scripts
```

不得提交真实 Key、真实个人数据、缓存文件，或删除证据链和调用成本提醒。
