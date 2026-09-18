# Live acceptance results

- 时间：2026-09-18T08:24:46.137979+00:00
- 凭证：仅进程内使用，未写入结果

## douyin

- 请求数：1/7
- 原始证据文件：1
- 报告：未生成
- 端点结果：
  - `/api/v1/douyin/search/fetch_video_search_v2`：HTTP 200
- 限制/失败：RuntimeError: search returned no mapped posts

## xiaohongshu

- 请求数：2/7
- 原始证据文件：2
- 报告：未生成（搜索结果未映射）
- 端点结果：
  - `/api/v1/xiaohongshu/app_v2/search_notes`：HTTP 200
  - `/api/v1/xiaohongshu/app_v2/get_image_note_detail`：HTTP 200
- 限制/失败：XiaohongshuAvailabilityError: Xiaohongshu note is unavailable
