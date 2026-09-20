# 可视化 PDF 交付

每次完成有研究结论的社媒报告后，额外交付一份 PDF。PDF 是 Markdown 正文的可读、可分享、可视化版本；Markdown 是结论真源，PDF 不得替代正文、原始证据或 Markdown 报告。

## 内容

- 首屏展示研究题目、时间范围、章节数、证据引用数和信息源数。
- 依次呈现正文已有的结论、样本、趋势、机会、选题和局限；不得在 PDF 中新增未经证实的结论。
- 保留样本量、时间范围、结论强度和研究边界。内部 evidence ID 仅保存在 `analysis/findings.json`，不得出现在给用户阅读的 PDF 中；外部作品链接可在 Markdown 报告中回查。
- 图表只读取同一次运行的 `analysis/data-pack.json`。图旁写明口径、样本或不可判断的边界；禁止把推断分数、平台未返回的曝光/点击/完播/转粉/成交数据画成事实。
- `account-audit` 可视化公开账号事实、样本播放/互动中位数、样本高低表现对照、内容支柱样本分布和评论覆盖。它们辅助理解 Markdown 已有结论，不替代正文的证据链或生成新的判断。

## 视觉

使用深墨色、荧光青、酸性黄和珊瑚橙的明亮科技风卡片；禁止使用蓝紫渐变作为默认配色。保持白底正文、足够留白和可打印的文本对比度。

## 生成与验收

运行：

```bash
python3 -m scripts.visual_pdf research-output/<run>/reports/<report>.md \
  --out research-output/<run>/reports/<report>-visual.pdf \
  --period "2026-09-12 至 2026-09-19" --source-count 6 \
  --data-pack research-output/<run>/analysis/data-pack.json
```

省略 `--data-pack` 时，脚本只会查找该报告所属运行目录下的同级 `analysis/data-pack.json`；找不到或不是账号审计数据包时，PDF 保持 Markdown 可视化版，不编造图表。

生成后必须渲染 PDF 页面并目视检查中文、分页、表格卡片、页脚和链接文字；若研究因接口或权限失败而没有有效正文，不得生成虚构 PDF。
