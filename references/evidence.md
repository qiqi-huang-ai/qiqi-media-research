# 证据等级

报告中的每个关键结论必须标注至少一个证据 ID，并归入以下一种：

- `observed`：API 原始响应中直接出现的事实。
- `calculated`：能从已列明字段和公式重复计算的结果。
- `interpreted`：基于多条事实作出的语义判断，必须说明推理依据。
- `hypothesis`：需要继续验证的推测。

当评论或趋势样本低于置信度门槛时，相关洞察必须标为 `hypothesis`，不得写成已确认的用户需求或市场趋势。证据 ID 应能回到 `raw_path`、`source_url` 和 `source_field`。
