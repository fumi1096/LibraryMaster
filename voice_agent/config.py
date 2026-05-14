"""
voice_agent 配置模块

所有配置项支持环境变量覆盖，便于容器化部署。
"""

import os


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
3. 根据检索结果，用自然语言总结和回答用户的问题
4. 如果检索结果不够精确，可以更换关键词再次检索

注意事项：
- 回答时请引用具体书名、作者等信息，不要凭空编造
- 如果检索无结果，诚实地告诉用户，并建议更换关键词
- 保持友好、专业的语气，回答简洁有条理
- 当用户只是闲聊（如打招呼、问你是谁），直接回复，无需调用工具"""
