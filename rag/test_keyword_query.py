#!/usr/bin/env python3
"""
书名关键字查询测试脚本

两种测试方式:
  1. 本地直接调用 (需要 lancedb — 适合容器内)
  2. HTTP API 调用 (只需 requests — 适合容器外 / 宿主机)

环境变量:
  API_URL - RAG API 地址，默认 http://localhost:9014/rag
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
    """本地直接调用 vector_query 模块 (需要 lancedb)"""
    print("=" * 60)
    print("测试 1: 本地直接调用 vector_query.keyword_search")
    print("=" * 60)

    try:
        from vector_query import VectorQuery
    except ModuleNotFoundError as e:
        print(f"[跳过] 缺少依赖 ({e})，本地测试仅适用于容器内环境")
        return

    vq = VectorQuery()

    # 测试多个关键字
    test_keywords = ["人工智能", "计算机", "Python"]

    for kw in test_keywords:
        print(f"\n查询关键字: '{kw}'")
        result = vq.keyword_search(kw, count=5)
        print(f"  共找到 {result['total']} 条结果:")
        for i, item in enumerate(result["results"], 1):
            print(f"    {i}. 《{item['书名']}》 - {item['作者']} / {item['出版社']}")


def test_api():
    """通过 HTTP API 调用 (只需 requests, 适合宿主机)"""
    print("=" * 60)
    print("测试 2: HTTP API 调用 /rag/keyword_search")
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

    # 测试关键字查询
    test_keywords = ["人工智能", "计算机", "Python", "深度学习"]

    for kw in test_keywords:
        print(f"\n查询关键字: '{kw}'")
        resp = SESSION.post(
            f"{API_URL}/keyword_search",
            json={"keyword": kw, "count": 5},
            headers={"Content-Type": "application/json"},
        )

        print(f"  状态码: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  共找到 {data['total']} 条结果:")
            for i, item in enumerate(data["results"], 1):
                print(f"    {i}. 《{item['书名']}》 - {item['作者']} / {item['出版社']}")
        else:
            print(f"  错误: {resp.text}")

    # 测试空关键字（应返回空结果）
    print(f"\n查询关键字: '' (空字符串，边界测试)")
    resp = SESSION.post(
        f"{API_URL}/keyword_search",
        json={"keyword": "", "count": 5},
        headers={"Content-Type": "application/json"},
    )
    print(f"  状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  共找到 {data['total']} 条结果 (空关键字应返回 0)")

    # 测试无匹配关键字
    print(f"\n查询关键字: 'zzzz不存在的书名zzzz' (无匹配测试)")
    resp = SESSION.post(
        f"{API_URL}/keyword_search",
        json={"keyword": "zzzz不存在的书名zzzz", "count": 5},
        headers={"Content-Type": "application/json"},
    )
    print(f"  状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  共找到 {data['total']} 条结果 (期望 0)")


def main():
    print("\n" + "=" * 60)
    print("  书名关键字查询测试")
    print("=" * 60 + "\n")

    test_local()
    print()
    test_api()

    print("\n测试完成!")


if __name__ == "__main__":
    main()
