# qiqi-media-research

一个面向自媒体研究的开源 Skill。它通过 TikHub REST API 采集公开社媒数据，把原始证据、统一数据、确定性计算和 AI 解读分开，最终生成可回查来源的研究报告。

## 平台状态

首版只适配抖音和小红书。脱敏样本、字段映射和离线流程已验证；在你的 TikHub 账号上完成少量真实调用前，接口能力仍标记为 `available-unverified`。其他平台暂不支持。

## 安装

- Codex：按根目录 `SKILL.md` 使用，`agents/openai.yaml` 提供界面信息。
- Claude Code：通过 `CLAUDE.md` 路由到根 Skill。
- Cursor：保留 `.cursor/rules/qiqi-media-research.mdc`。
- WorkBuddy：使用 `workbuddy/SKILL.md` 作为入口。

运行环境只需要 Python 3.11+ 标准库。开发测试可执行 `python3 -m pip install -e '.[dev]'`。

## 配置 TIKHUB_API_KEY

从 TikHub 获取自己的 Key，只保存在本机环境变量：

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

`research-output/raw/` 保存原始响应，`normalized/` 保存统一 JSONL，`manifest.json` 记录实际调用清单（不含凭证），Markdown 报告记录 evidence ID、覆盖范围和局限。

## 成本与数据边界

TikHub 的额度、价格和接口状态可能变化，本项目不提供免费额度。抖音 Search 单独纳入计费预估。默认从 1–3 个样本开始，计划超过 20 次调用时必须再次确认。只处理公开数据，不绕过权限。

## 测试与贡献

```bash
python3 -m pytest -v
python3 -m compileall -q adapters scripts
```

不得提交真实 Key、真实个人数据、缓存文件，或删除证据链和调用成本提醒。
