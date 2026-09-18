# 平台能力状态

状态含义：`available-unverified` 表示已用脱敏固定样本完成适配，但尚未用用户自己的 TikHub Key 做少量真实验收；只有真实验收通过后才能改成 `verified`。`not-available` 表示首版不提供。

| 平台 | 搜索 | 账号 | 账号作品 | 作品详情 | 评论 | 回复 | 趋势 |
|---|---|---|---|---|---|---|---|
| 抖音 | verified | verified | verified | verified | verified | available-unverified | available-unverified |
| 小红书 | verified | verified | available-unverified | verified | verified | available-unverified | not-available |

本次低量真实验收（2026-09-18）验证了抖音搜索、账号资料、账号作品、作品详情和评论；抖音评论回复与热榜未验收。小红书搜索、账号资料、作品详情和评论通过；账号作品返回 HTTP 400，故保持未验证；回复未验收，首版不提供趋势。

本表只描述 `qiqi-media-research` 当前实现，不代表 TikHub 的全部平台能力。其它平台未验证，不得宣传为支持。
