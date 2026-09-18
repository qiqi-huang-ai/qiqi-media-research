# Live acceptance results

- 时间：2026-09-18T08:28:04.605787+00:00
- 凭证：仅进程内使用，未写入结果

## xiaohongshu

- 请求数：4/5
- 原始证据文件：3
- 报告：docs/acceptance/live-artifacts/xiaohongshu/xiaohongshu-acceptance-report.md
- 端点结果：
  - `/api/v1/xiaohongshu/app_v2/search_notes`：HTTP 200
  - `/api/v1/xiaohongshu/app_v2/get_image_note_detail`：HTTP 200
  - `/api/v1/xiaohongshu/app_v2/get_user_info`：HTTP 200
  - `/api/v1/xiaohongshu/app_v2/get_user_posted_notes`：HTTP 400
- 限制/失败：TikHubError: TikHub HTTP 400
