# 统一数据结构

所有数据结构都保留 `platform`、`source_url`、`collected_at` 和 `raw_path` 等溯源字段。平台没有返回的字段必须为 `null`，不得估算、补零或用其他指标替代。

## Account

| 字段 | 类型 | 可空 | 含义 |
|---|---|---:|---|
| platform | string | 否 | 平台标识 |
| account_id | string | 否 | 平台账号 ID |
| source_url | string | 否 | 账号证据链接 |
| name, bio | string | 是 | 昵称、简介 |
| followers, following, posts, likes_received | integer | 是 | 平台明确返回的账号统计 |
| collected_at, raw_path | string | 是 | 采集时间与原始响应路径 |

## Post

| 字段 | 类型 | 可空 | 含义 |
|---|---|---:|---|
| platform, post_id, source_url | string | 否 | 平台、作品 ID、证据链接 |
| author_id, author_name, text, published_at | string | 是 | 作者与作品元数据 |
| views, likes, comments, shares, saves, followers | integer | 是 | 平台明确返回的独立指标 |
| views_source | string | 是 | 播放量来源，如 `detail` 或抖音独立 `statistics` 端点 |
| duration_sec | number | 是 | 视频时长（秒） |
| collected_at, raw_path | string | 是 | 采集时间与原始响应路径 |

`saves` 与 `shares` 是不同指标：小红书收藏不能冒充分享，抖音分享也不能合并成未标注的“互动”字段。跨平台比较必须展示指标名称和缺失值。

## Comment

必填字段为 `platform`、`comment_id`、`post_id`、`source_url`。作者、正文、发布时间、点赞数、回复数、父评论 ID 和溯源字段均可空。

## TrendItem

必填字段为 `platform`、`trend_id`、`title`、`source_url`。榜单名次、平台热度分、分类和溯源字段均可空。不同平台的 `score` 不得直接比较。

## EvidenceRecord

每条证据包含 `evidence_id`、`platform`、`entity_type`、`entity_id`、`source_url`、`source_field` 和原始 `value`；`collected_at`、`raw_path` 可空。`source_field` 必须记录值来自哪个平台字段，以便回查。
