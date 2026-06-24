#!/usr/bin/env python3
"""
Agent HTTP API Server — 在 Docker 容器内运行

提供 REST API 供宿主机 kws_wakeup.py 调用：
  POST /chat   — 发送用户文本，返回 Agent JSON 回复
  POST /reset  — 重置对话历史
  GET  /health — 健康检查
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from agent import LibraryAgent
from config import AGENT_SERVER_HOST, AGENT_SERVER_PORT


# 全局 Agent 实例（单例）
_agent: LibraryAgent | None = None


def get_agent() -> LibraryAgent:
    global _agent
    if _agent is None:
        _agent = LibraryAgent()
    return _agent


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def log_message(self, format, *args):
        """简洁日志"""
        print(f"[{self.log_date_time_string()}] {args[0]}", flush=True)

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "agent": "LibraryAgent"})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/chat":
            self._handle_chat()
        elif self.path == "/reset":
            self._handle_reset()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_chat(self):
        try:
            body = self._read_body()
            text = body.get("text", "").strip()
            if not text:
                self._send_json({"error": "text is required"}, 400)
                return

            agent = get_agent()
            reply = agent.chat(text, stream=False)

            self._send_json({"reply": reply})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_reset(self):
        try:
            agent = get_agent()
            agent.reset()
            self._send_json({"status": "reset"})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


def main():
    host = AGENT_SERVER_HOST
    port = AGENT_SERVER_PORT

    server = HTTPServer((host, port), AgentHandler)
    print(f"🚀 Agent HTTP Server 启动")
    print(f"   地址: http://{host}:{port}")
    print(f"   API:  POST /chat  |  POST /reset  |  GET /health")
    print("-" * 50, flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
