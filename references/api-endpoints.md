# TikHub API 端点清单

- 基础地址：`https://api.tikhub.io`
- 鉴权：请求头 `Authorization: Bearer $TIKHUB_API_KEY`
- 核对日期：2026-09-18
- 状态：抖音 App V3 与抖音 Search 为首版已适配接口；上线前仍应运行少量真实验收。

## 抖音

| 能力 | 路径 |
|---|---|
| 单作品 | `/api/v1/douyin/app/v3/fetch_one_video` |
| 分享链接解析 | `/api/v1/douyin/app/v3/fetch_one_video_by_share_url` |
| 作品统计 | `/api/v1/douyin/app/v3/fetch_video_statistics` |
| 账号资料 | `/api/v1/douyin/app/v3/handler_user_profile` |
| 账号作品 | `/api/v1/douyin/app/v3/fetch_user_post_videos` |
| 评论 | `/api/v1/douyin/app/v3/fetch_video_comments` |
| 评论回复 | `/api/v1/douyin/app/v3/fetch_video_comment_replies` |
| 热榜 | `/api/v1/douyin/app/v3/fetch_hot_search_list` |
| 搜作品 | `/api/v1/douyin/search/fetch_video_search_v2` |
| 搜账号 | `/api/v1/douyin/search/fetch_user_search_v2` |

抖音 Search 单独计费，任何研究预算和调用前成本估算都必须单列搜索调用，不得把它视为 App V3 的免费附带能力。

抖音多数作品接口不再可靠返回播放量。需要播放量时，必须额外调用作品统计端点，参数为 `aweme_ids`（一次最多两个），读取 `data.statistics_list[].play_count`；不能把详情接口中的 `play_count: 0` 当成真实零播放。

官方资料：

- https://tikhub.io/douyin-api
- https://docs.tikhub.io/186826220e0
- https://docs.tikhub.io/186826223e0

## 小红书

首版使用当前推荐的 App V2：图片/视频笔记详情、用户资料、用户笔记、评论与子评论、笔记/用户搜索、话题资料与话题内容流。核对路径均位于 `/api/v1/xiaohongshu/app_v2/`。App V2 的推荐状态可能变化，每次发布前必须重新核对官方文档；不调用已弃用的 App V1 或 Web V2/V3。

官方资料：

- https://blog.tikhub.io/zh/article/7
- https://docs.tikhub.io/420136391e0
- https://docs.tikhub.io/420136395e0
- https://docs.tikhub.io/420136396e0
- https://docs.tikhub.io/420748830e0
