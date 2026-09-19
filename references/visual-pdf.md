# 可视化 PDF 交付

每次完成有研究结论的社媒报告后，额外交付一份 PDF。PDF 是正文的可读可分享版本，不得替代正文、原始证据或 Markdown 报告。

## 内容

- 首屏展示研究题目、时间范围、章节数、证据引用数和信息源数。
- 依次呈现正文已有的结论、样本、趋势、机会、选题和局限；不得在 PDF 中新增未经证实的结论。
- 保留样本量、时间范围、结论强度和研究边界。内部 evidence ID 仅保存在 `analysis/findings.json`，不得出现在给用户阅读的 PDF 中；外部作品链接可在 Markdown 报告中回查。

## 视觉

使用深墨色、荧光青、酸性黄和珊瑚橙的明亮科技风卡片；禁止使用蓝紫渐变作为默认配色。保持白底正文、足够留白和可打印的文本对比度。

## 生成与验收

运行：

```bash
python3 -m scripts.visual_pdf research-output/<run>/reports/<report>.md \
  --out research-output/<run>/reports/<report>-visual.pdf \
  --period "2026-09-12 至 2026-09-19" --source-count 6
```

生成后必须渲染 PDF 页面并目视检查中文、分页、表格卡片、页脚和链接文字；若研究因接口或权限失败而没有有效正文，不得生成虚构 PDF。
