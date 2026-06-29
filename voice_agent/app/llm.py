"""
DeepSeek LLM 封装模块

基于 OpenAI 兼容 SDK，支持流式输出和 Function Calling。
流式输出通过回调接口预留 TTS 扩展点。
"""

import json
from typing import Optional, Generator, Any
from dataclasses import dataclass, field
from openai import OpenAI

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)


# ============================================================
# 流式输出回调接口 (TTS 预留)
# ============================================================
class StreamCallbacks:
    """流式输出回调基类，子类化以接入 TTS 等下游"""

    def on_thinking(self) -> None:
        """LLM 开始思考（即将调用工具）"""
        pass

    def on_text(self, text: str) -> None:
        """逐 token 文本输出"""
        pass

    def on_tool_call(self, tool_name: str, arguments: dict) -> None:
        """工具调用通知"""
        pass

    def on_tool_result(self, tool_name: str, result: str) -> None:
        """工具返回结果"""
        pass

    def on_complete(self) -> None:
        """本轮回答完成"""
        pass

    def on_error(self, error: str) -> None:
        """发生错误"""
        pass


class PrintCallbacks(StreamCallbacks):
    """默认打印回调，将流式输出打印到终端"""

    def on_thinking(self) -> None:
        print("\n🤔 正在思考...", end="", flush=True)

    def on_text(self, text: str) -> None:
        print(text, end="", flush=True)

    def on_tool_call(self, tool_name: str, arguments: dict) -> None:
        args_str = json.dumps(arguments, ensure_ascii=False)
        print(f"\n🔧 调用工具: {tool_name}({args_str})")

    def on_tool_result(self, tool_name: str, result: str) -> None:
        preview = result[:100] + "..." if len(result) > 100 else result
        print(f"📋 {tool_name} 返回: {preview}")

    def on_complete(self) -> None:
        print()

    def on_error(self, error: str) -> None:
        print(f"\n❌ 错误: {error}")


# ============================================================
# 流式事件类型
# ============================================================
@dataclass
class StreamEvent:
    """流式输出事件"""

    type: str  # "text" | "tool_call" | "complete" | "error"
    text: str = ""
    tool_name: str = ""
    tool_arguments: dict = field(default_factory=dict)
    error: str = ""


# ============================================================
# DeepSeek LLM
# ============================================================
class DeepSeekLLM:
    """DeepSeek LLM 客户端，封装聊天补全与流式输出"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self.model = model or DEEPSEEK_MODEL

        if not self.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY 未设置，请设置环境变量或在代码中传入"
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> dict:
        """
        非流式聊天补全

        Returns:
            OpenAI 响应消息对象 (message dict)
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.model_dump()

    def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        callbacks: Optional[StreamCallbacks] = None,
    ) -> Generator[StreamEvent, None, None]:
        """
        流式聊天补全

        Yields:
            StreamEvent: 流式事件

        同时通过 callbacks 回调通知 (供 TTS 等下游使用)
        """
        if callbacks is None:
            callbacks = PrintCallbacks()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            stream = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = f"DeepSeek API 调用失败: {str(e)}"
            callbacks.on_error(msg)
            yield StreamEvent(type="error", error=msg)
            return

        # 流式解析状态
        accumulated_content = ""
        tool_calls_acc: dict[int, dict] = {}

        try:
            for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    accumulated_content += delta.content
                    callbacks.on_text(delta.content)
                    yield StreamEvent(type="text", text=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["function"]["arguments"] += (
                                    tc.function.arguments
                                )

                finish_reason = chunk.choices[0].finish_reason
                if finish_reason == "tool_calls":
                    for idx in sorted(tool_calls_acc.keys()):
                        tc = tool_calls_acc[idx]
                        try:
                            args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = {}
                        callbacks.on_tool_call(tc["function"]["name"], args)
                        yield StreamEvent(
                            type="tool_call",
                            tool_name=tc["function"]["name"],
                            tool_arguments=args,
                        )

                elif finish_reason == "stop":
                    callbacks.on_complete()
                    yield StreamEvent(type="complete")
                    break
        except Exception as e:
            msg = f"流式响应中断: {str(e)}"
            callbacks.on_error(msg)
            yield StreamEvent(type="error", error=msg)


# ============================================================
# 便捷函数
# ============================================================
def create_llm() -> DeepSeekLLM:
    """从环境变量创建 DeepSeekLLM 实例"""
    return DeepSeekLLM()
