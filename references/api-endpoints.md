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

官方资料：

- https://tikhub.io/douyin-api
- https://docs.tikhub.io/186826220e0
- https://docs.tikhub.io/186826223e0
