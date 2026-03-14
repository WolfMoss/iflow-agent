# iFlow Agent Gateway

## 项目概述

在 iFlow CLI **手动模式**下，由 iFlow 原生负责模型 API 认证、Skill、MCP 与工具执行；本网关只做 **Web UI** 与 **多通道聊天接入**（REST/SSE API、Telegram、钉钉/飞书等可扩展），结构清晰、易于扩展。

## 技术栈

- **语言**: Python 3.12
- **Web**: FastAPI、uvicorn
- **iFlow**: iflow-cli-sdk（manual mode，连接已启动的 `iflow --experimental-acp --port 8090`）
- **配置**: pydantic-settings、.env

## 架构概览

- **核心层 (core/)**: 配置、会话存储（内存，可扩展 Redis）、IFlow 桥接（发消息、流式事件）。
- **应用层 (app/)**: FastAPI 路由（健康检查、会话、流式聊天）、聊天服务（会话解析 + 桥接调用）。
- **通道层 (channels/)**: 适配器抽象（入参标准化、按渠道回写），Web 由 API 直接服务，Telegram 已实现（默认 Long Polling 本地可用，可选 Webhook + Bot API 回发），钉钉为占位示例。
- **前端 (web/)**: 静态单页，会话管理 + SSE 流式对话。

### 数据流

1. 用户/渠道发消息 → 会话解析（或新建 session_id）→ IFlow 桥接 `stream_chat`。
2. iFlow 通过 WebSocket 返回 AssistantMessage / ToolCall / Plan / TaskFinish → 转为统一事件 → SSE 或渠道 API 回写。
3. 模型、认证、Skill、MCP 均在 iFlow CLI 侧配置，本服务不感知。

## 目录结构

```
iflow-agent/
├── core/                 # 核心：配置、会话、IFlow 桥接
│   ├── config.py         # 从 .env 加载配置
│   ├── session.py        # 会话存储抽象与内存实现
│   ├── iflow_bridge.py   # IFlow SDK 封装，流式事件
│   └── iflow_runner.py   # 启动时自动拉起 iFlow 进程（可选）
├── app/
│   ├── main.py           # FastAPI 应用、路由挂载、静态资源
│   ├── routes/
│   │   ├── health.py         # /health, /ready
│   │   ├── chat.py           # /api/sessions, /api/chat
│   │   └── telegram_webhook.py  # POST /channels/telegram (Telegram Webhook)
│   └── services/
│       └── chat_service.py  # 会话与流式回复
├── channels/             # 多通道适配器
│   ├── base.py           # ChannelAdapter、InboundEvent、Registry
│   ├── web.py            # Web 渠道占位
│   ├── telegram.py       # Telegram 适配器（Webhook 解析 + sendMessage 回发）
│   └── dingtalk_stub.py  # 钉钉扩展示例
├── web/                  # 前端静态
│   ├── index.html
│   └── static/
│       ├── style.css
│       └── app.js
├── run.py                # 启动入口
├── requirements.txt
├── .env.example
└── README.md
```

## 文件说明

### core/config.py

- **职责**: 应用配置。
- **逻辑**: `Settings` 从 .env 读取 `IFLOW_WS_URL`、`IFLOW_AUTO_START`（默认 true，启动时自动拉起 iFlow）、`HOST`、`PORT`、`SESSION_STORE_URL`、`LOG_LEVEL`、`iflow_timeout`；可选 Telegram 相关配置。

### core/session.py

- **职责**: 会话存储。
- **逻辑**: `SessionStore` 抽象 + `MemorySessionStore` 实现；`SessionInfo` 含 session_id、channel、channel_user_id、channel_session_id、时间戳；`get_session_store(redis_url)` 预留 Redis 扩展。

### core/iflow_runner.py

- **职责**: 启动网关时按配置自动拉起 iFlow 子进程（`iflow --experimental-acp --port N`）。
- **逻辑**: `start_iflow_process()` 在 `IFLOW_AUTO_START=true` 时通过 `shutil.which("iflow")` 查找可执行文件并 `Popen` 启动；应用 shutdown 时对子进程 `terminate()` / `wait()`。

### core/iflow_bridge.py

- **职责**: 与 iFlow 通信。
- **逻辑**: 使用 `IFlowOptions(auto_start_process=False, url=...)`；`stream_chat(message, session_id)` 异步生成事件 dict（assistant_chunk、tool_call、plan、task_finish、error）；`format_event_for_sse` 转 SSE 行。

### app/main.py

- **职责**: FastAPI 入口。
- **逻辑**: 注册 health、chat 路由；将 `web/` 挂载到 `/`（html=True 以支持根路径 index.html）；启动时配置日志。

### app/routes/chat.py

- **职责**: 会话与聊天 API。
- **逻辑**: `POST /api/sessions` 创建会话；`GET /api/sessions/{id}` 查询会话；`POST /api/chat` 接收 message、session_id 等，调用 `stream_reply`，以 SSE 流式返回事件。

### app/services/chat_service.py

- **职责**: 聊天业务。
- **逻辑**: `ensure_session` 获取或创建会话；`stream_reply` 委托 `iflow_bridge.stream_chat` 并逐条 yield 事件。

### channels/base.py

- **职责**: 通道抽象。
- **逻辑**: `InboundEvent` 标准化入参；`ChannelAdapter` 定义 `channel_id`、`parse_request`、`send_stream`；`AdapterRegistry` 按 channel_id 注册与查找。

### channels/telegram.py

- **职责**: Telegram 渠道适配器（参考 [nanobot](https://github.com/HKUDS/nanobot)）。
- **逻辑**: `parse_request` 从 Telegram Update 中解析 `message`/`edited_message`，得到 chat_id、user_id、text；`send_stream` 聚合 assistant_chunk，按 4096 字符分段后调用 Bot API `sendMessage` 回发；`get_updates` 为 Long Polling 拉取新消息（本地无需公网/域名）。

### channels/dingtalk_stub.py

- **职责**: 钉钉扩展示例。
- **逻辑**: 占位实现 `parse_request`（从 dict 取 sender、conversation、text）与 `send_stream`（占位），便于复制为真实钉钉回调路由。

## 如何运行

1. **安装 iFlow CLI**（若未安装），并确保 `iflow` 在 PATH 中。

2. **复制环境变量并安装依赖**

   ```bash
   cp .env.example .env
   pip install -r requirements.txt
   ```

3. **启动网关**（默认会**自动启动** iFlow 进程，无需另开终端）

   ```bash
   python run.py
   ```

   若在 `.env` 中设置 `IFLOW_AUTO_START=false`，则需先手动启动 iFlow：`iflow --experimental-acp --port 8090`，再启动网关。

4. 打开浏览器访问 `http://localhost:8000`，即可使用 Web 聊天界面；或调用 `POST /api/chat`（body: `message`, `session_id` 等）获取 SSE 流式回复。

### 进程与关闭

- **正常关闭网关时**（在运行 `python run.py` 的终端按 **Ctrl+C**，或对进程发 **SIGTERM**）：应用会执行 shutdown 钩子，自动对自动启动的 iFlow 子进程执行 `terminate()`，**网关和 iFlow 都会一起退出**。

- **强制杀死网关时**（如 Windows 任务管理器「结束任务」、或 `kill -9`）：进程会立即退出，来不及执行 shutdown，iFlow 可能变成**孤儿进程**继续在后台运行，需要本机手动结束 iFlow 进程（任务管理器里结束对应进程，或 `taskkill /F /IM iflow.exe` / `kill <iflow 的 PID>`）。

- **Windows**：iFlow 以**独立控制台窗口**启动（`CREATE_NEW_CONSOLE`），便于管理员在该窗口查看 iFlow 日志；也可直接关闭该窗口来结束 iFlow。

- **Linux 下关闭方式**：
  - **前台运行**：在运行网关的终端按 **Ctrl+C**，网关与 iFlow 会一起退出。
  - **后台运行**：先查网关进程 PID（`ps aux | grep -E "run.py|uvicorn"`），再执行 `kill <网关的 PID>`（不要用 `kill -9`，以便网关能执行 shutdown 并关掉 iFlow）。若之前已用 `kill -9` 强杀过网关，iFlow 可能仍在运行，需单独结束：`ps aux | grep iflow` 找到 PID 后 `kill <iflow 的 PID>`。

### Telegram 渠道（可选）

**本地使用（推荐，与 nanobot 一致）：无需服务器、域名或 ngrok。**

1. 在 Telegram 中找 [@BotFather](https://t.me/BotFather)，发送 `/newbot` 创建机器人，获取 **Bot Token**。
2. 在 `.env` 中配置：
   - `TELEGRAM_BOT_TOKEN=你的 token`
   - `TELEGRAM_ALLOW_FROM=*`（允许所有人）或 `TELEGRAM_ALLOW_FROM=123456789`（仅允许该用户 ID）。用户 ID 可通过 [@userinfobot](https://t.me/userinfobot) 等获取。
3. 启动 iFlow 与网关后，在 Telegram 中向机器人发消息即可。网关默认使用 **Long Polling**（本机主动向 Telegram 拉取新消息），无需公网 IP 或 HTTPS。若该 Bot 曾设置过 Webhook，需先删除：访问 `https://api.telegram.org/bot<token>/deleteWebhook`。

**部署到公网时（可选）：** 若将服务部署到有域名的服务器，可设置 `TELEGRAM_USE_WEBHOOK=true` 并配置 Telegram Webhook（`setWebhook` 指向 `https://你的域名/channels/telegram`），由 Telegram 主动推送消息，此时不再运行 Long Polling。

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 存活探针 |
| GET | /ready | 就绪探针（含 iflow_url） |
| POST | /api/sessions | 创建会话，返回 session_id |
| GET | /api/sessions/{session_id} | 获取会话信息 |
| POST | /api/chat | 流式聊天，请求体含 message、session_id 等，响应 SSE |
| POST | /channels/telegram | Telegram Bot Webhook（Telegram 服务器调用，需配置 setWebhook） |
