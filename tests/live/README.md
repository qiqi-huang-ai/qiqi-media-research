# Live acceptance

真实验收是可选且可能产生 TikHub 费用的发布检查。必须先运行：

```bash
python tests/live/run_acceptance.py --platform all --dry-run
```

只有用户明确同意输出中的平台、操作和最大调用次数后，才可运行非 dry-run。脚本不得打印请求头、密钥或原始个人标识；原始响应目录不能提交到 Git。
