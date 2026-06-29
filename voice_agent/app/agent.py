"""
Agent 主循环

实现 ReAct 风格的 Agent：
用户输入 → LLM 判断 → 执行工具调用 → 回传结果 → 流式输出最终回答
"""

import json
import copy
from typing import Optional, Generator

from config import (
    SYSTEM_PROMPT,
    MAX_TOOL_CALL_ROUNDS,
    MAX_HISTORY_MESSAGES,
)
from llm import DeepSeekLLM, StreamCallbacks, PrintCallbacks, StreamEvent, create_llm
from tools import TOOLS_SCHEMA, execute_tool


class LibraryAgent:
    """图书馆查询智能体"""

    def __init__(
        self,
        llm: Optional[DeepSeekLLM] = None,
        system_prompt: Optional[str] = None,
    ):
        self.llm = llm or create_llm()
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.messages: list[dict] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def reset(self) -> None:
        """重置对话历史"""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    def _trim_history(self) -> None:
        """控制对话历史长度，保留 system prompt + 最近 N 条消息"""
        if len(self.messages) > MAX_HISTORY_MESSAGES + 1:
            # 保留 system prompt (index 0) + 最近 MAX_HISTORY_MESSAGES 条
            self.messages = [
                self.messages[0]
            ] + self.messages[-(MAX_HISTORY_MESSAGES):]

    def chat(
        self,
        user_input: str,
        stream: bool = True,
    ) -> str:
        """
        处理用户输入并返回回复

        Args:
            user_input: 用户输入文本
            stream: 是否流式输出

        Returns:
            Agent 的完整回复文本
        """
        self.messages.append({"role": "user", "content": user_input})
        self._trim_history()

        if stream:
            return self._chat_stream()
        else:
            return self._chat_sync()

    def _chat_sync(self) -> str:
        """非流式对话（带工具调用循环）"""
        for _ in range(MAX_TOOL_CALL_ROUNDS):
            response = self.llm.chat(self.messages, tools=TOOLS_SCHEMA)

            # 检查是否有工具调用
            if response.get("tool_calls"):
                tool_results = self._handle_tool_calls(response)
                if tool_results is None:
                    return "抱歉，工具调用处理失败。"

                # 将助手消息和工具结果加入历史
                self.messages.append(response)
                for tr in tool_results:
                    self.messages.append(tr)

                # 继续下一轮，让 LLM 基于工具结果生成回答
                continue

            # 没有工具调用，这是最终回答
            content = response.get("content", "")
            self.messages.append(response)
            self._trim_history()
            return content or "抱歉，我无法理解你的问题。"

        return "抱歉，我尝试了多次查询但未能找到相关信息。"

    def _chat_stream(self) -> str:
        """
        流式对话（带工具调用循环）

        流式模式下，由调用方通过 callbacks 接收输出。
        这里使用内部 PrintCallbacks 简化处理，
        同时返回完整文本供 CLI 使用。
        """
        callbacks = PrintCallbacks()
        full_response = ""

        for round_idx in range(MAX_TOOL_CALL_ROUNDS):
            tool_calls_in_round: list[dict] = []
            current_text = ""

            for event in self.llm.chat_stream(
                self.messages, tools=TOOLS_SCHEMA, callbacks=callbacks
            ):
                if event.type == "text":
                    current_text += event.text
                elif event.type == "tool_call":
                    tool_calls_in_round.append(
                        {
                            "name": event.tool_name,
                            "arguments": event.tool_arguments,
                        }
                    )
                elif event.type == "error":
                    return full_response or event.error

            # 如果有工具调用
            if tool_calls_in_round:
                # 构建 assistant 消息 (含 tool_calls)
                assistant_msg = {
                    "role": "assistant",
                    "content": current_text or None,
                    "tool_calls": [],
                }

                for i, tc in enumerate(tool_calls_in_round):
                    assistant_msg["tool_calls"].append(
                        {
                            "id": f"call_{round_idx}_{i}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(
                                    tc["arguments"], ensure_ascii=False
                                ),
                            },
                        }
                    )

                self.messages.append(assistant_msg)

                # 执行工具并加入结果
                for i, tc in enumerate(tool_calls_in_round):
                    result = execute_tool(tc["name"], tc["arguments"])
                    callbacks.on_tool_result(tc["name"], result)
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": f"call_{round_idx}_{i}",
                            "content": result,
                        }
                    )

                # 继续循环，让 LLM 基于结果生成回答
                continue

            # 没有工具调用，这是最终回答
            full_response = current_text
            self.messages.append(
                {"role": "assistant", "content": full_response}
            )
            self._trim_history()
            return full_response

        return "抱歉，我尝试了多次查询但未能找到相关信息。"

    async def chat_stream_events_async(self):
        """
        Async generator yielding structured dict events for WebSocket push.

        Yields:
            {"type": "text", "content": "..."}
            {"type": "tool_call", "tool": "...", "args": {...}}
            {"type": "tool_result", "tool": "...", "result": "..."}
            {"type": "books", "books": [...], "tool": "..."}
            {"type": "complete"}
            {"type": "error", "message": "..."}
        """
        import asyncio
        import threading

        queue: asyncio.Queue = asyncio.Queue()

        def _produce():
            try:
                for round_idx in range(MAX_TOOL_CALL_ROUNDS):
                    tool_calls_in_round: list[dict] = []
                    current_text = ""

                    try:
                        events = self.llm.chat_stream(
                            self.messages,
                            tools=TOOLS_SCHEMA,
                            callbacks=PrintCallbacks(),
                        )
                    except Exception as llm_err:
                        err_msg = str(llm_err)
                        # 如果第一轮工具已执行（已有结果显示），给出友好提示
                        if round_idx > 0:
                            queue.put_nowait(
                                {"type": "text", "content": "\n(图书已显示在上方，如需进一步了解请再次提问)"}
                            )
                        else:
                            queue.put_nowait(
                                {"type": "error", "message": f"API 调用失败: {err_msg[:200]}"}
                            )
                        queue.put_nowait({"type": "complete"})
                        return

                    for event in events:
                        if event.type == "text":
                            current_text += event.text
                            queue.put_nowait(
                                {"type": "text", "content": event.text}
                            )
                        elif event.type == "tool_call":
                            tool_calls_in_round.append(
                                {
                                    "name": event.tool_name,
                                    "arguments": event.tool_arguments,
                                }
                            )
                            queue.put_nowait(
                                {
                                    "type": "tool_call",
                                    "tool": event.tool_name,
                                    "args": event.tool_arguments,
                                }
                            )
                        elif event.type == "error":
                            queue.put_nowait(
                                {"type": "error", "message": event.error}
                            )
                            queue.put_nowait({"type": "complete"})
                            return

                    if not tool_calls_in_round:
                        # Final answer — no tools needed
                        self.messages.append(
                            {
                                "role": "assistant",
                                "content": current_text,
                            }
                        )
                        self._trim_history()
                        queue.put_nowait({"type": "complete"})
                        return

                    # Has tool calls — build assistant message
                    assistant_msg: dict = {
                        "role": "assistant",
                        "content": current_text or None,
                        "tool_calls": [],
                    }
                    for i, tc in enumerate(tool_calls_in_round):
                        assistant_msg["tool_calls"].append(
                            {
                                "id": f"call_{round_idx}_{i}",
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(
                                        tc["arguments"], ensure_ascii=False
                                    ),
                                },
                            }
                        )
                    self.messages.append(assistant_msg)

                    # Execute tools and collect results
                    for i, tc in enumerate(tool_calls_in_round):
                        result = execute_tool(tc["name"], tc["arguments"])
                        self.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": f"call_{round_idx}_{i}",
                                "content": result,
                            }
                        )

                        # Parse tool result → structured books event
                        try:
                            result_data = json.loads(result)
                            if (
                                "results" in result_data
                                and isinstance(result_data["results"], list)
                            ):
                                books = []
                                for r in result_data["results"]:
                                    books.append(
                                        {
                                            "title": r.get("书名", ""),
                                            "author": r.get("作者", ""),
                                            "publisher": r.get("出版社", ""),
                                            "category": r.get(
                                                "中国图书分类号", ""
                                            ),
                                            "summary": r.get("摘要", ""),
                                            "keywords": r.get("关键词", ""),
                                            "publish_date": r.get(
                                                "出版年月", ""
                                            ),
                                            "similarity": r.get(
                                                "similarity", 0
                                            ),
                                        }
                                    )
                                queue.put_nowait(
                                    {
                                        "type": "books",
                                        "books": books,
                                        "tool": tc["name"],
                                    }
                                )
                        except (json.JSONDecodeError, AttributeError):
                            pass

                        queue.put_nowait(
                            {
                                "type": "tool_result",
                                "tool": tc["name"],
                                "result": result,
                            }
                        )

                queue.put_nowait({"type": "complete"})
            except Exception as e:
                queue.put_nowait({"type": "error", "message": str(e)})
                queue.put_nowait({"type": "complete"})

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        while True:
            event = await queue.get()
            yield event
            if event.get("type") == "complete":
                break

    def _handle_tool_calls(self, response: dict) -> Optional[list[dict]]:
        """
        处理非流式响应中的工具调用

        Returns:
            tool result messages 列表，失败返回 None
        """
        tool_results = []
        for tc in response.get("tool_calls", []):
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            result = execute_tool(name, arguments)
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", "unknown"),
                    "content": result,
                }
            )
        return tool_results
