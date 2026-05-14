#!/usr/bin/env python3
"""
向量查询接口测试脚本

两种测试:
  1. 本地直接调用 (需要 lancedb, openai, SGLang — 适合容器内)
  2. HTTP API 调用 (只需 requests — 适合容器外 / 宿主机)

环境变量:
  API_URL       - RAG API 地址，默认 http://localhost:9014/rag
  EMBEDDING_URL - 嵌入服务地址（仅本地模式），默认 http://127.0.0.1:30000/v1
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import requests

API_URL = os.getenv("API_URL", "http://localhost:9014/rag")

# 绕过系统 HTTP 代理（本地请求不需要走代理）
SESSION = requests.Session()
SESSION.trust_env = False


def test_local():
    """本地直接调用 vector_query 模块 (需要 lancedb + openai + SGLang)"""
    print("=" * 60)
    print("测试 1: 本地直接调用 vector_query 模块")
    print("=" * 60)

    try:
        from vector_query import VectorQuery
    except ModuleNotFoundError as e:
        print(f"[跳过] 缺少依赖 ({e})，本地测试仅适用于容器内环境")
        return

    vq = VectorQuery()
    query_text = "机器学习与深度学习"
    print(f"查询文本: {query_text}")

    # 1. 向量化
    print("\n[1] 向量化测试...")
    vec = vq.embed_text(query_text)
    print(f"  向量维度: {len(vec)}")
    print(f"  向量前5位: {vec[:5]}")

    # 2. 一站式搜索
    print("\n[2] 一站式搜索测试...")
    result = vq.search_by_text(query_text, count=3)
    print(f"  共找到 {result['total']} 条结果:\n")
    for i, item in enumerate(result["results"], 1):
        print(f"  --- 结果 {i} ---")
        print(f"    书名: {item['书名']}")
        print(f"    作者: {item['作者']}")
        print(f"    相似度: {item['similarity']:.4f}")
        print(f"    关键词: {item['关键词']}")
        print()


def test_api():
    """通过 HTTP API 调用 (只需 requests, 适合宿主机)"""
    print("=" * 60)
    print("测试 2: HTTP API 调用 /rag/search")
    print(f"API 地址: {API_URL}")
    print("=" * 60)

    # 检查 API 是否运行
    try:
        resp = SESSION.get(f"{API_URL}/", timeout=5)
        if resp.status_code != 200:
            print(f"API 异常 (状态码 {resp.status_code})")
            return
        print("API 连接成功")
    except requests.exceptions.ConnectionError:
        print(f"API 未运行，请先启动: docker compose -f rag/docker-compose.yml up -d --build")
        return

    # 调用 /search 端点
    query_data = {"text": "人工智能的未来发展趋势", "count": 5}
    print(f"\n查询文本: {query_data['text']}")
    print("正在请求 /rag/search ...")

    resp = SESSION.post(
        f"{API_URL}/search",
        json=query_data,
        headers={"Content-Type": "application/json"},
    )

    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"向量维度: {data['vector_dim']}")
        print(f"向量预览: {data['vector_preview']}")
        print(f"结果数量: {data['total']}\n")
        for i, item in enumerate(data["results"], 1):
            print(f"  --- 结果 {i} ---")
            print(f"    书名: {item['书名']}")
            print(f"    作者: {item['作者']}")
            print(f"    出版社: {item['出版社']}")
            print(f"    相似度: {item['similarity']:.4f}")
            print()
    else:
        print(f"错误: {resp.text}")


def main():
    print("\n" + "=" * 60)
    print("  向量查询接口测试")
    print("=" * 60 + "\n")

    test_local()
    print()
    test_api()


if __name__ == "__main__":
    main()
