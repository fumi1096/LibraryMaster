"""
Function Calling 工具定义

定义 Agent 可用的工具（OpenAI tool schema 格式），
以及对应的执行函数（调用远程 RAG API）。
"""

import json
import os
import requests
from typing import Any

from config import get_rag_base_url, DEFAULT_SEARCH_COUNT

# 绕过系统 HTTP 代理（本地/内网请求不需要走代理）
SESSION = requests.Session()
SESSION.trust_env = False


# ============================================================
# 工具 Schema 定义 (OpenAI Function Calling 格式)
# ============================================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "根据用户描述的自然语言文本，在图书馆数据库中检索相关图书。"
            "支持中文关键词、主题描述、问题等任意自然语言输入。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "description": "检索查询文本，可以是关键词、主题描述或自然语言问题",
                    },
                    "count": {
                        "type": "integer",
                        "description": f"返回结果数量，默认为 {DEFAULT_SEARCH_COUNT}",
                        "default": DEFAULT_SEARCH_COUNT,
                    },
                },
                "required": ["query_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_library_info",
            "description": "获取当前图书馆数据库的基本信息，包括数据表名称、"
            "图书总数、字段结构等。用于回答用户关于数据库概况的问题。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# ============================================================
# 工具执行函数
# ============================================================

def execute_search_books(query_text: str, count: int = DEFAULT_SEARCH_COUNT) -> str:
    """
    调用远程 RAG API 的 /rag/search 端点进行图书检索

    Args:
        query_text: 自然语言查询文本
        count: 返回结果数量

    Returns:
        JSON 格式的检索结果字符串
    """
    base_url = get_rag_base_url()
    try:
        resp = SESSION.post(
            f"{base_url}/search",
            json={"text": query_text, "count": count},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # 精简结果，去掉向量数据只保留关键信息
        results = data.get("results", [])
        simplified = []
        for r in results:
            simplified.append(
                {
                    "书名": r.get("书名", ""),
                    "作者": r.get("作者", ""),
                    "出版社": r.get("出版社", ""),
                    "关键词": r.get("关键词", ""),
                    "摘要": r.get("摘要", ""),
                    "中国图书分类号": r.get("中国图书分类号", ""),
                    "出版年月": r.get("出版年月", ""),
                    "相似度": round(r.get("similarity", 0), 4),
                }
            )

        return json.dumps(
            {
                "query": data.get("query", query_text),
                "total": len(simplified),
                "results": simplified,
            },
            ensure_ascii=False,
        )
    except requests.ConnectionError:
        return json.dumps(
            {"error": f"无法连接到图书检索服务 ({base_url})，请检查服务是否运行"},
            ensure_ascii=False,
        )
    except requests.Timeout:
        return json.dumps(
            {"error": "图书检索服务响应超时，请稍后重试"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"检索失败: {str(e)}"},
            ensure_ascii=False,
        )


def execute_get_library_info() -> str:
    """
    调用远程 RAG API 获取数据库概况信息
    """
    base_url = get_rag_base_url()
    try:
        # 获取表信息
        resp = SESSION.get(f"{base_url}/table_info", timeout=10)
        resp.raise_for_status()
        table_info = resp.json()

        # 获取表列表
        resp2 = SESSION.get(f"{base_url}/tables", timeout=10)
        resp2.raise_for_status()
        tables_data = resp2.json()

        return json.dumps(
            {
                "table_name": table_info.get("table_name", "unknown"),
                "row_count": table_info.get("row_count", 0),
                "fields": table_info.get("sample_columns", []),
                "data_types": table_info.get("data_types", {}),
                "all_tables": tables_data.get("tables", {}).get("tables", []),
            },
            ensure_ascii=False,
        )
    except requests.ConnectionError:
        return json.dumps(
            {"error": f"无法连接到图书检索服务 ({base_url})，请检查服务是否运行"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"获取数据库信息失败: {str(e)}"},
            ensure_ascii=False,
        )


# ============================================================
# 工具注册表：函数名 → 执行函数
# ============================================================

TOOL_EXECUTORS: dict[str, Any] = {
    "search_books": execute_search_books,
    "get_library_info": execute_get_library_info,
}


def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    根据工具名称和参数执行工具，返回结果字符串

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        工具执行结果 (JSON 字符串)
    """
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    try:
        return executor(**arguments)
    except TypeError as e:
        return json.dumps(
            {"error": f"工具参数错误: {str(e)}"},
            ensure_ascii=False,
        )
