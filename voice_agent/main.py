#!/usr/bin/env python3
"""
图书馆智能助手 — CLI 入口

支持流式输出、远程 RAG 服务配置。
用法:
    python3 main.py                        # 默认配置
    python3 main.py --rag-url http://10.0.0.5:9014/rag  # 指定远程 RAG 地址
    python3 main.py --no-stream            # 关闭流式输出
"""

import sys
import argparse
import os

# 将 app/ 目录加入 sys.path，使主流程能正确导入 agent、llm、tools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from config import RAG_BASE_URL
from agent import LibraryAgent


def parse_args():
    parser = argparse.ArgumentParser(
        description="图书馆智能助手 — 基于 DeepSeek + RAG 的图书查询 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 main.py
  python3 main.py --rag-url http://192.168.1.100:9014/rag
  python3 main.py --no-stream
  python3 main.py --rag-url http://10.0.0.5:9014/rag --no-stream
        """,
    )
    parser.add_argument(
        "--rag-url",
        type=str,
        default=None,
        help=f"远程 RAG 服务地址 (默认: {RAG_BASE_URL})",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="关闭流式输出",
    )
    return parser.parse_args()


def check_config():
    """检查必要的配置"""
    issues = []

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        issues.append("❌ DEEPSEEK_API_KEY 环境变量未设置")
        issues.append("   export DEEPSEEK_API_KEY='sk-xxxxxxxx'")

    return issues


def main():
    args = parse_args()

    # 覆盖 RAG 地址
    if args.rag_url:
        os.environ["RAG_BASE_URL"] = args.rag_url

    # 配置检查
    issues = check_config()
    if issues:
        for line in issues:
            print(line)
        sys.exit(1)

    stream = not args.no_stream

    print("=" * 50)
    print("  📚 图书馆智能助手")
    print("=" * 50)
    print(f"  RAG 服务: {os.environ.get('RAG_BASE_URL', RAG_BASE_URL)}")
    print(f"  流式输出: {'✅' if stream else '❌'}")
    print()
    print("  输入 'exit' 或 'quit' 退出")
    print("  输入 'reset' 重置对话")
    print("  输入 'help' 查看帮助")
    print("-" * 50)
    print()

    agent = LibraryAgent()

    try:
        while True:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见！")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print("👋 再见！")
                break

            if user_input.lower() == "reset":
                agent.reset()
                print("🔄 对话已重置")
                continue

            if user_input.lower() == "help":
                print("""
使用说明:
  - 直接输入问题，如"有没有关于人工智能的书？"
  - 系统会自动判断是否需要检索数据库
  - 输入 'reset' 重置对话历史
  - 输入 'exit' 退出程序

示例:
  >>> 有没有关于深度学习的中文书？
  >>> 数据库里有多少本书？
  >>> 介绍一下《三体》这本书
                """.strip())
                continue

            print()  # 空行分隔
            try:
                response = agent.chat(user_input, stream=stream)
            except Exception as e:
                print(f"\n❌ 处理请求时出错: {e}")
                continue

            if not stream and response:
                print(response)
                print()

    except KeyboardInterrupt:
        print("\n👋 再见！")


if __name__ == "__main__":
    main()
