# 评分规则

机会分的六个输入均为研究者根据证据归一化后的 0–100 分：

```text
OpportunityScore =
  0.24 * demand
+ 0.18 * momentum
+ 0.18 * (100 - supply)
+ 0.16 * relative_performance
+ 0.12 * repeatability
+ 0.12 * goal_fit
```

`supply` 代表供给/竞争强度，因此反向计分。输出同时保留各项贡献值，不允许只展示无法解释的总分。

置信度与机会分完全分离。置信度依据平台数、作品数、评论数、指标缺失率和来源一致性分为 `high`、`medium`、`low`，并输出具体原因。数据少不等于机会差，只代表结论需要更谨慎。
