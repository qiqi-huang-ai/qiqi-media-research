# 一句话完成首次准备

用户可通过安装包或 GitHub 地址安装 `qiqi-media-research`。安装完成后，不要让用户逐项输入 Python、pip 或诊断命令；代理应先定位包根目录，再执行本地、可回退的准备工作。

## 两种安装入口

| 入口 | 用户动作 | 适合场景 |
| --- | --- | --- |
| 安装包 | 将下载的 ZIP 解压或导入 WorkBuddy/Codex 的 Skill 安装页 | 用户已从奇其领取安装包，想离线保留一份 |
| GitHub 地址 | 在 Skill 安装入口粘贴仓库地址 `https://github.com/qiqi-huang-ai/qiqi-media-research` | 用户希望以后跟随 GitHub 更新 |

安装后应看到 Skill 名称 `qiqi-media-research`。不同客户端的按钮名称可能变化；不要编造固定点击路径。

## 代理初始化合同

用户说“帮我配置这个 Skill”“第一次使用 qiqi-media-research”或贴出安装包/地址时，代理应：

1. 定位 Skill 根目录并确认其中有 `pyproject.toml` 与 `SKILL.md`。
2. 在根目录执行 `python3 -m scripts.bootstrap --setup`，让脚本创建隔离的 `.venv` 并安装项目依赖。
3. 用 `.venv` 中的 Python 运行 `python -m scripts.doctor`；只反馈 `configured` / `missing` 等状态，不回显任何密钥。
4. 若 `TIKHUB_API_KEY` 缺失，告诉用户去 WorkBuddy/Codex 的安全环境变量或本机环境配置页面填写。不得要求用户把 Key 发送到对话，也不得写入 `.env`、提示词、日志或 GitHub。
5. 诊断通过后，用一个低成本、小样本研究验证安装；先展示调用计划，未获同意不得扩展到 20 次以上调用。

推荐用户只发送这一句：

> 请帮我完成 qiqi-media-research 的首次准备：定位当前安装包，创建隔离运行环境并安装依赖，运行安全诊断。不要向我索要、显示或保存 TikHub Key；如果缺 Key，只告诉我应该在哪个安全环境变量位置配置。完成后给我一个低成本的首跑建议。

## 边界

- `bootstrap --setup` 会安装 Python 依赖，但不会请求 TikHub、不会产生 TikHub 调用，也不会保存密钥。
- 如果当前环境没有 Python 3.11+、没有安装权限或网络受限，代理应报告具体原因并给用户最少的下一步，不要反复重试。
- Key 本身是唯一不能由聊天代理代填的步骤；这是为了不把用户凭证暴露在对话、日志或仓库中。
