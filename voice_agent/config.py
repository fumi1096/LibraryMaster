"""
voice_agent 配置模块

所有配置项支持环境变量覆盖，便于容器化部署。
.env 文件中的配置会自动加载到环境变量。
"""

import os

# 自动加载 .env 文件
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value


# ============================================================
# DeepSeek API 配置
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============================================================
# 远程 RAG 服务配置 (另一台机器上的图书检索服务)
# ============================================================
_DEFAULT_RAG_BASE_URL = "http://127.0.0.1:9014/rag"


def get_rag_base_url() -> str:
    """动态获取 RAG 服务地址（每次调用时从环境变量读取，确保 --rag-url 生效）"""
    return os.getenv("RAG_BASE_URL", _DEFAULT_RAG_BASE_URL)


# 兼容旧代码的模块级变量（已废弃，请使用 get_rag_base_url()）
RAG_BASE_URL = _DEFAULT_RAG_BASE_URL

# ============================================================
# Agent 行为配置
# ============================================================
DEFAULT_SEARCH_COUNT = int(os.getenv("DEFAULT_SEARCH_COUNT", "5"))
MAX_TOOL_CALL_ROUNDS = int(os.getenv("MAX_TOOL_CALL_ROUNDS", "3"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
STREAM_ENABLED = os.getenv("STREAM_ENABLED", "true").lower() == "true"

# ============================================================
# 系统提示词
# ============================================================
SYSTEM_PROMPT = """你是一个专业的图书馆助手，帮助用户查找图书信息。

你的能力：
- 根据用户描述的主题、关键词或问题，检索相关图书
- 介绍图书的作者、出版社、摘要等信息
- 回答用户关于图书的各种问题

工作流程：
1. 当用户询问与图书相关的问题时，使用 search_books 工具检索
2. 如果需要了解数据库概况，使用 get_library_info 工具
3. 根据检索结果，用自然语言回复用户

⚠️ 关键规则：
- 检索结果中的图书会以交互卡片形式展示给用户，包含书名、作者、出版社、
  分类号、摘要等完整信息，用户点击可查看详情或导航到该书位置
- 因此你的文字回复中**不要逐本罗列图书细节**（书名、作者等已由卡片展示）
- 你只需要简要总结检索情况（如"为您找到3本相关图书"），
  然后提供选择建议或回答用户的具体问题
- 不要凭空编造不存在的图书信息
- 如果检索无结果，诚实地告诉用户，并建议更换关键词
- 当用户只是闲聊（如打招呼、问你是谁），直接回复，无需调用工具
- 🎙️ 你的回复会通过语音朗读给用户听，请尽量简洁，控制在2-3句话以内，
  避免长篇大论，不要使用列表、序号、Markdown格式"""

# ============================================================
# Agent HTTP Server 配置
# ============================================================
AGENT_SERVER_HOST = os.getenv("AGENT_SERVER_HOST", "127.0.0.1")
AGENT_SERVER_PORT = int(os.getenv("AGENT_SERVER_PORT", "9015"))

# ============================================================
# KWS 唤醒词配置
# ============================================================
KWS_WAKEUP_KEYWORD = os.getenv("KWS_WAKEUP_KEYWORD", "你好小图")
KWS_SILENCE_TIMEOUT_S = float(os.getenv("KWS_SILENCE_TIMEOUT_S", "2.0"))
KWS_MAX_RECORD_S = float(os.getenv("KWS_MAX_RECORD_S", "30.0"))

# ============================================================
# 讯飞语音识别 (ASR) 配置
# ============================================================
XUNFEI_ASR_APP_ID = os.getenv("XUNFEI_ASR_APP_ID", "")
XUNFEI_ASR_API_KEY = os.getenv("XUNFEI_ASR_API_KEY", "")
XUNFEI_ASR_API_SECRET = os.getenv("XUNFEI_ASR_API_SECRET", "")
XUNFEI_ASR_HOST = os.getenv("XUNFEI_ASR_HOST", "iat.xf-yun.com")
XUNFEI_ASR_PATH = os.getenv("XUNFEI_ASR_PATH", "/v1")

# ============================================================
# 讯飞超拟人语音合成 (TTS) 配置
# ============================================================
XUNFEI_TTS_APP_ID = os.getenv("XUNFEI_TTS_APP_ID", "")
XUNFEI_TTS_API_KEY = os.getenv("XUNFEI_TTS_API_KEY", "")
XUNFEI_TTS_API_SECRET = os.getenv("XUNFEI_TTS_API_SECRET", "")
XUNFEI_TTS_HOST = os.getenv("XUNFEI_TTS_HOST", "cbm01.cn-huabei-1.xf-yun.com")
XUNFEI_TTS_PATH = os.getenv("XUNFEI_TTS_PATH", "/v1/private/mcd9m97e6")
XUNFEI_TTS_VOICE = os.getenv("XUNFEI_TTS_VOICE", "x5_lingxiaoxuan_flow")  # 聆小璇(免费)
