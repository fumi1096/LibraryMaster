# 图书馆智能助手 (Voice Agent)

基于 **DeepSeek API + Function Calling** 的图书馆查询智能体，通过调用远程 RAG 服务实现图书检索，支持流式输出（为 TTS 预留接口）。

## 架构

```
用户输入 (CLI / 语音)
    │
    ▼
┌─────────────────────────────────┐
│  LibraryAgent (agent.py)        │
│  ┌───────────┐ ┌──────────────┐ │
│  │ DeepSeek  │ │  Function    │ │
│  │   LLM     │─│  Calling     │ │
│  │ (llm.py)  │ │  (tools.py)  │ │
│  └───────────┘ └──────┬───────┘ │
│       │               │  HTTP   │
│       ▼               ▼         │
│  流式输出回调     远程 RAG API   │
│  (TTS预留)       (:9014)        │
└─────────────────────────────────┘
```

## 快速开始

### 方式一：本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 DeepSeek API Key
export DEEPSEEK_API_KEY='sk-xxxxxxxx'

# 3. 确保远程 RAG 服务已启动 (在另一台机器上)
# curl http://<远程IP>:9014/rag/

# 4. 启动智能助手
python3 main.py --rag-url http://<远程IP>:9014/rag
```

### 方式二：Docker 容器运行

```bash
# 1. 从模板创建 .env 文件，填入 DeepSeek API Key
cp .env.example .env
# 编辑 .env，修改 DEEPSEEK_API_KEY 和 RAG_BASE_URL

# 2. 构建并启动
docker compose up -d --build

# 3. 进入交互式终端
docker attach voice-agent

# 4. 退出容器 (Ctrl+P, Ctrl+Q 保持运行; Ctrl+C 停止)
docker compose down
```

> **注意**：若 RAG 服务在宿主机上，`RAG_BASE_URL` 使用 `http://host.docker.internal:9014/rag` 即可。若在另一台机器上，改为实际 IP。

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--rag-url` | 远程 RAG 服务地址 | `http://127.0.0.1:9014/rag` |
| `--no-stream` | 关闭流式输出 | 默认开启流式 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | (必填) |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-chat` |
| `RAG_BASE_URL` | 远程 RAG 地址 | `http://127.0.0.1:9014/rag` |

## 交互示例

```
$ python3 main.py --rag-url http://192.168.1.100:9014/rag

==================================================
  📚 图书馆智能助手
==================================================
  RAG 服务: http://192.168.1.100:9014/rag
  流式输出: ✅

  输入 'exit' 或 'quit' 退出
  输入 'reset' 重置对话
  输入 'help' 查看帮助
--------------------------------------------------

>>> 有没有关于深度学习的书？

🔧 调用工具: search_books({"query_text": "深度学习", "count": 5})
📋 search_books 返回: {"query": "深度学习", "total": 3, ...

为您找到以下关于深度学习的图书：

1. **《深度学习入门》** — 斋藤康毅 著，人民邮电出版社
   摘要：本书是深度学习真正意义上的入门书...

2. **《动手学深度学习》** — 阿斯顿·张 等著
   摘要：面向中文读者的深度学习教材...

>>> 第一本适合初学者吗？

根据检索到的信息，《深度学习入门》确实非常适合初学者...
```

## 文件说明

```
voice_agent/
├── main.py            # CLI 入口，支持 --rag-url / --no-stream 参数
├── agent.py           # Agent 主循环：ReAct 风格的对话 + 工具调用编排
├── llm.py             # DeepSeek LLM 封装：流式生成 + 回调接口 (TTS预留)
├── tools.py           # Function Calling 工具：search_books / get_library_info
├── config.py          # 配置管理：API Key、RAG 地址、系统提示词
├── requirements.txt   # Python 依赖
├── Dockerfile         # Docker 镜像构建
├── docker-compose.yml # Docker 编排
├── .env.example       # 环境变量模板
├── .gitignore         # Git 忽略规则
└── README.md          # 本文件
```

## TTS 扩展

流式输出通过 `StreamCallbacks` 抽象类预留了 TTS 扩展点。只需实现子类并传入即可：

```python
from llm import StreamCallbacks

class TTSCallbacks(StreamCallbacks):
    def on_text(self, text: str) -> None:
        # 将文本送入 TTS 引擎
        tts_engine.feed(text)

    def on_complete(self) -> None:
        tts_engine.flush()
```

## 许可证

与 LibraryMaster 主项目一致。