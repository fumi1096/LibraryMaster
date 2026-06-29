# 图书馆智能助手 (Voice Agent)

基于 **DeepSeek API + Function Calling** 的图书馆查询智能体，支持 **CLI / Web UI / 语音** 三种交互方式。适配 **RDK X5 ARM 嵌入式 Linux**，在 **Weston Wayland** 上以 Kiosk 全屏模式运行。

---

## 架构

```
──── RDK X5 (ARM Linux) — HDMI 屏幕 (1024×600 触摸) ───────────
                                            │
  ┌─────────────────────────────────────────┼──────────────────┐
  │  宿主机 (Python)                         │                  │
  │                                         ▼                  │
  │  voice_relay.py :9016                                      │
  │  ├── POST /record  (浏览器 🎤 → 录音 → 讯飞 ASR → 文本)   │
  │  └── GET  /health                                          │
  │                                                             │
  │  kws_service.py                                             │
  │  └── KWS 持续监听 "你好小图" → 唤醒 → 录音 → ASR           │
  │       └── POST → /api/voice/wakeup (Agent Server)          │
  └────────────────────────────────────────────────────────────┘
                                            │
  ┌─────────────────────────────────────────┼──────────────────┐
  │  kiosk.py (Python WebKit2GTK)            │                  │
  │    └── 全屏渲染 http://localhost:9015    │                  │
  │          └── SPA 前端 (static/)          │                  │
  │                │ WebSocket /ws/chat    │ HTTP /api/*       │
  ▼                ▼                        ▼                  │
  ┌──────────────────────────────────────────────────────────┐ │
  │  Docker: voice-agent (port 9015)                         │ │
  │  ┌─────────────────────────────────────────────────────┐ │ │
  │  │  agent_server.py  (FastAPI)                         │ │ │
  │  │  ├── 静态文件服务  /static/*                         │ │ │
  │  │  ├── WebSocket    /ws/chat  (流式对话 + KWS 推送)   │ │ │
  │  │  ├── POST /api/voice/record  (→ voice_relay :9016) │ │ │
  │  │  ├── POST /api/voice/wakeup  (KWS 唤醒 → WS 广播)  │ │ │
  │  │  ├── POST /api/chat          (非流式)               │ │ │
  │  │  ├── POST /api/rag/search    (关键词搜索)            │ │ │
  │  │  ├── POST /api/rag/semantic  (语义搜索)              │ │ │
  │  │  └── POST /api/navigate      (导航占位)              │ │ │
  │  └─────────────────────────────────────────────────────┘ │ │
  │  ┌─────────────────────────────────────────────────────┐ │ │
  │  │  agent.py  ←→  llm.py  ←→  DeepSeek API            │ │ │
  │  │     ↑           ↑                                  │ │ │
  │  │  tools.py  → 远程 RAG API (:9014)                   │ │ │
  │  └─────────────────────────────────────────────────────┘ │ │
  └──────────────────────────────────────────────────────────┘ │
                                                               │
  ┌──────────────────────────────────────────────────────────┐ │
  │  Docker: RAG API (port 9014)                             │ │
  │  FastAPI + LanceDB + SGLang Embedding                   │ │
  │  ├── /rag/search         (语义搜索)                      │ │
  │  ├── /rag/keyword_search (关键词匹配)                    │ │
  │  └── /rag/query          (向量检索)                     │ │
  └──────────────────────────────────────────────────────────┘ │
```

### 三种输入方式

| 方式 | 触发 | 流程 |
|------|------|------|
| ⌨️ 键盘 | 点击输入框 → 虚拟键盘输入 → Enter | 文本 → Agent |
| 🎤 语音按钮 | **长按** 底部 🎤 按钮 | voice_relay 录音 → 讯飞 ASR → Agent |
| 🔔 KWS 唤醒 | 说出 **"你好小图"** | kws_service 唤醒 → 录音 → ASR → Agent |

---

## 快速开始

### 前置条件

- RDK X5 已安装 Ubuntu Server + Weston（参考 `docs/rdk_x5_hdmi_display_setup.md`）
- Docker 和 docker-compose 已安装
- RAG API 服务已部署（参见 `rag/README.md`）

### 启动服务

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 2. 构建并启动 Agent Server（含 Web UI）
docker compose up -d --build

# 3. 验证服务
curl http://localhost:9015/api/health
# → {"status":"ok","agent":"LibraryAgent"}

# 4. 验证 Web UI
# 浏览器打开 http://localhost:9015
```

### Kiosk 全屏模式（RDK X5 + Weston）

```bash
# 1. 安装浏览器
sudo apt install surf -y

# 2. 启动 Weston + Kiosk
sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &
sleep 3
surf -f http://localhost:9015

# 或使用 systemd 服务开机自启（参见下方部署章节）
```

---

## Web UI 功能

### 顶部搜索栏

| 元素 | 功能 |
|------|------|
| 🔍 搜索按钮 | 执行搜索 |
| 输入框 | 传统模式：输入书名/作者关键词；RAG 模式：输入自然语言描述 |
| **传统** / **RAG** 切换 | 传统=关键词匹配，RAG=语义向量搜索 |
| ⚙ 配置按钮 | 弹出 RAG API 地址配置弹窗（保存到 localStorage） |

### 中部内容区

- **图书卡片** — 显示书名、作者、分类号，右侧有 📍 导航按钮
- **短按卡片** → 弹出详情弹窗（含摘要、出版社、出版年月等信息）
- **Agent 对话** — WebSocket 流式渲染，文本 + 图书卡片混合展示
- **搜索 / Agent 结果** — 使用相同图书卡片组件，统一视觉效果

### 底部输入栏

| 元素 | 交互方式 | 功能 |
|------|----------|------|
| 🎤 语音按钮 | **长按** (>500ms) | 开始录音 → 浏览器 ASR 转写 → 自动填入发送 |
| | **短按** (<300ms) | 聚焦文本输入框，弹出虚拟键盘 |
| 输入框 | 点击 | 弹出可拖拽虚拟键盘 |
| ➤ 发送按钮 | 点击 | 发送文本到 Agent，通过 WebSocket 流式返回 |

### 可拖拽虚拟键盘

- **英文模式**：标准 QWERTY 布局
- **中文模式**：拼音键盘，输入拼音后弹出候选汉字
- **拖拽**：触摸拖动可调节键盘位置（向上拖可上移）
- **功能键**：⌫ 退格 · ↵ 回车 · → 收起 · 中/EN 切换

---

## 导航功能

每个图书卡片右侧的 📍 导航按钮 → `POST /api/navigate`

当前为 **API 占位**，返回 `{"status":"accepted"}`，后续对接 ROS2 navigation stack：

```json
POST /api/navigate
{"category": "TP181", "book_title": "深度学习入门"}

→ {"status": "accepted", "message": "...", "category": "TP181", ...}
```

---

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 返回 SPA 首页 |
| GET | `/static/{path}` | 静态文件（CSS/JS） |
| WebSocket | `/ws/chat` | **流式 Agent 对话** — 结构化事件 + KWS 唤醒推送 |
| POST | `/api/chat` | 非流式对话（兼容旧 `kws_wakeup.py`） |
| POST | `/api/reset` | 重置对话历史 |
| POST | `/api/rag/search` | 传统关键词搜索 |
| POST | `/api/rag/semantic` | RAG 语义搜索 |
| POST | `/api/navigate` | 导航占位（后续对接 ROS2） |
| POST | `/api/voice/record` | 语音录音代理 → 宿主机 voice_relay:9016 |
| POST | `/api/voice/wakeup` | KWS 唤醒文本推送 → 广播到浏览器 |
| GET | `/api/config` | 前端配置 |
| GET | `/api/health` | 健康检查 |

### WebSocket 事件协议

服务端 → 客户端事件格式：

```json
{"type": "text",       "content": "为您找到以下图书："}
{"type": "tool_call",  "tool": "search_books", "args": {"query_text": "深度学习"}}
{"type": "tool_result","tool": "search_books", "result": "..."}
{"type": "books",      "books": [{"title":"...", "author":"...", "category":"..."}]}
{"type": "complete"}
{"type": "error",      "message": "..."}
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 **(必填)** |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `RAG_BASE_URL` | `http://host.docker.internal:9014/rag` | RAG API 地址 |
| `AGENT_SERVER_HOST` | `0.0.0.0` | 监听地址 |
| `AGENT_SERVER_PORT` | `9015` | 监听端口 |
| `DEFAULT_SEARCH_COUNT` | `5` | 默认搜索数量 |
| `MAX_TOOL_CALL_ROUNDS` | `3` | 最大工具调用轮数 |

---

## Docker 部署（RDK X5）

```bash
# 构建镜像
docker compose build

# 启动服务（守护模式）
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

容器启动后，Web UI 访问 `http://<RDK_IP>:9015`。

---

## Kiosk 部署（HDMI 全屏显示）

### 一键全栈启动（Docker + Kiosk + 语音唤醒）

```bash
# 启动全部服务
./start_voice_agent.sh --all
```

启动顺序：
1. Docker Agent Server (port 9015)
2. voice_relay (port 9016) — 浏览器 🎤 按钮录音
3. kws_service — 语音唤醒 "你好小图"
4. Weston Wayland 合成器
5. Kiosk 全屏浏览器

### 单独启动

```bash
# 仅 Docker + Kiosk（无语音）
./start_voice_agent.sh --kiosk

# 仅 Docker + 语音唤醒（无 Kiosk）
./start_voice_agent.sh --kws

# 仅 Docker
./start_voice_agent.sh
```

### 开机自启（systemd）

部署脚本会自动安装 kiosk 服务：

```bash
# 在 RDK X5 上运行
sudo bash deploy/deploy-kiosk.sh
```

重启后启动顺序：
1. `init-hdmi.service` — 强制 HDMI 连接
2. `weston.service` — Wayland 合成器
3. `docker.service` — Docker 守护进程
4. `voice-agent-kiosk.service` — 全屏 Web UI

### 卸载

```bash
sudo bash deploy/deploy-kiosk.sh --uninstall
```

### kiosk.py 参数

```bash
./kiosk.py                                   # 默认 http://localhost:9015
./kiosk.py http://192.168.1.100:9015         # 指定 URL
./kiosk.py --touch                           # 启用触摸调试（点击显示坐标）
```

---

## 文件说明

```
voice_agent/
├── main.py                    # CLI 入口
├── config.py                  # 共享配置
├── docker-compose.yml         # Docker 编排 (restart: unless-stopped)
│
├── app/
│   ├── agent_server.py        # ★ FastAPI 服务 (WebSocket + 静态文件 + API)
│   ├── agent.py               # Agent 主循环 (ReAct + 结构化事件)
│   ├── llm.py                 # DeepSeek LLM 封装 (流式 + Function Calling)
│   ├── tools.py               # Function Calling 工具
│   ├── Dockerfile             # Docker 镜像构建
│   ├── requirements.txt       # Python 依赖
│   │
│   └── static/                # ★ 前端 SPA
│       ├── index.html         # 主页面
│       ├── css/
│       │   └── style.css      # 扁平化设计样式 (主色 #4A90D9)
│       └── js/
│           ├── app.js         # 全局状态 + WebSocket 管理
│           ├── search.js      # 传统/RAG 搜索切换
│           ├── books.js       # 图书卡片 + 详情弹窗 + 导航
│           ├── keyboard.js    # 可拖拽虚拟键盘 (中英文拼音)
│           └── voice.js       # 长按录音 + ASR 转写
│
├── src/
│   ├── kws_service.py           # ★ KWS 语音唤醒服务
│   ├── voice_relay.py           # ★ 语音录音中继
│   ├── kws_asr_detector.py      # KWS 唤醒词检测模块
│   ├── kws_wakeup.py            # 旧版语音主流程（保留备用）
│   ├── xunfei_asr.py            # 讯飞流式 ASR
│   ├── xunfei_tts.py            # 讯飞超拟人 TTS
│   └── test_asr_api.py          # ASR 测试程序
│
├── kiosk.py                    # ★ 极简 Kiosk 浏览器 (Python WebKit2GTK)
├── kiosk.service               # ★ Systemd 服务文件 (开机自启)
│
└── deploy/
    ├── deploy-kiosk.sh         # ★ Kiosk 部署/卸载脚本
    └── ...
```

---

## CLI 交互（备用）

除 Web UI 外，仍可通过 CLI 交互：

```bash
# 本地运行
python3 main.py --rag-url http://<RAG_IP>:9014/rag

# Docker 内
docker attach voice-agent
```

---

## 语音交互

### 方式 1：长按 🎤 按钮（浏览器内）

需要宿主机运行 `voice_relay.py`:

```bash
# 由 --kws 或 --all 自动启动，或手动启动:
python3 src/voice_relay.py &
```

流程：长按 🎤 → 录音 5s → 讯飞 ASR → 填入输入框自动发送

### 方式 2：KWS 语音唤醒

需要宿主机运行 `kws_service.py`:

```bash
# 由 --kws 或 --all 自动启动，或手动启动:
python3 src/kws_service.py &
```

流程：说 **"你好小图"** → 唤醒 → 录音 → ASR → Agent 回复

### 依赖安装

```bash
pip install funasr sounddevice numpy requests websocket-client
```

---

## TTS 扩展

流式输出通过 `StreamCallbacks` 抽象类预留了 TTS 扩展点：

```python
from llm import StreamCallbacks

class TTSCallbacks(StreamCallbacks):
    def on_text(self, text: str) -> None:
        tts_engine.feed(text)
    def on_complete(self) -> None:
        tts_engine.flush()
```

---

## 许可证

与 LibraryMaster 主项目一致。