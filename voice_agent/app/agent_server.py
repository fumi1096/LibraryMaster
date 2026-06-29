#!/usr/bin/env python3
"""
Agent HTTP + WebSocket Server — 基于 FastAPI

提供：
  - 静态文件服务（前端 SPA）
  - WebSocket /ws/chat — 流式 Agent 对话（结构化事件）
  - POST /api/chat — 非流式对话（兼容旧客户端 kws_wakeup.py）
  - POST /api/reset — 重置对话
  - POST /api/rag/search — 传统关键词搜索代理
  - POST /api/rag/semantic — RAG 语义搜索代理
  - POST /api/navigate — 导航占位（后续对接 ROS2）
  - GET /api/config — 前端配置
  - GET /api/health — 健康检查
"""

import json
import os
import sys
import time
import logging
from typing import Optional

import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# 将 app/ 上级目录加入 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agent import LibraryAgent
from config import AGENT_SERVER_HOST, AGENT_SERVER_PORT, get_rag_base_url

# ── 日志 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent_server")

# ── 全局 Agent 单例 ───────────────────────────────────
_agent: Optional[LibraryAgent] = None


def get_agent() -> LibraryAgent:
    global _agent
    if _agent is None:
        _agent = LibraryAgent()
    return _agent


# ── 请求/响应模型 ────────────────────────────────────
class ChatRequest(BaseModel):
    text: str


class RAGSearchRequest(BaseModel):
    text: str
    count: int = 20


class NavigateRequest(BaseModel):
    category: str = ""
    book_title: str = ""


# ── FastAPI 应用 ─────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="LibraryMaster Agent Server")

# ── WebSocket 客户端追踪（用于 KWS 唤醒推送） ────────
ws_clients: set = set()

# ── 打断标志（KWS 轮询） ────────────────────────────
_interrupt_flag: float = 0.0  # 时间戳，>0 表示有打断请求

# ── 最后回复存储（KWS 轮询获取 TTS 文本） ──────────
_last_reply_id: int = 0
_last_reply_text: str = ""


# ── 静态文件服务 ──────────────────────────────────────
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── 主页面 ────────────────────────────────────────────
@app.get("/")
async def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Agent Server Running</h1><p>Static frontend not found.</p>")


# ── 健康检查 ──────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "agent": "LibraryAgent"}


# ── 前端配置 ──────────────────────────────────────────
@app.get("/api/config")
async def config():
    return {
        "rag_url": get_rag_base_url(),
        "agent_version": "1.0",
        "voice_relay_url": "/api/voice/record",
    }


# ── 语音中继代理 → 宿主机 voice_relay.py:9016 ──────
@app.post("/api/voice/record")
async def voice_record(request: Request):
    import httpx
    relay_host = os.getenv("VOICE_RELAY_HOST", "host.docker.internal")
    relay_port = os.getenv("VOICE_RELAY_PORT", "9016")
    relay_url = f"http://{relay_host}:{relay_port}/record"

    try:
        body = await request.json() if request.headers.get("content-length") else {"duration": 5}
    except Exception:
        body = {"duration": 5}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(relay_url, json=body)
            return resp.json()
    except Exception as e:
        log.warning(f"Voice relay 不可达 ({relay_url}): {e}")
        return {"error": "语音服务未启动，请在宿主机运行: python3 src/voice_relay.py"}


# ── KWS 唤醒推送（宿主机 kws_service.py → 浏览器） ──
@app.post("/api/voice/wakeup")
async def voice_wakeup(request: Request):
    """接收宿主机 KWS 唤醒识别文本，广播到所有 WebSocket 客户端"""
    try:
        body = await request.json()
    except Exception:
        return {"error": "invalid json"}

    text = body.get("text", "").strip()
    if not text:
        return {"error": "text is required"}

    log.info(f"🔔 KWS 唤醒: \"{text}\"")

    # 广播到所有已连接的浏览器
    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send_json({
                "type": "wakeup_text",
                "text": text,
                "source": body.get("source", "kws"),
            })
        except Exception:
            disconnected.add(ws)

    ws_clients.difference_update(disconnected)
    return {"status": "ok", "clients": len(ws_clients)}


# ── KWS 状态推送（宿主机 → 浏览器：显示/隐藏打断按钮） ──
@app.post("/api/voice/state")
async def voice_state(request: Request):
    """接收宿主机 KWS 状态变化，广播到所有 WebSocket 客户端"""
    try:
        body = await request.json()
    except Exception:
        return {"error": "invalid json"}

    state = body.get("state", "").strip()
    if not state:
        return {"error": "state is required"}

    log.info(f"🔄 KWS 状态: {state}")

    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send_json({
                "type": "voice_state",
                "state": state,
            })
        except Exception:
            disconnected.add(ws)

    ws_clients.difference_update(disconnected)
    return {"status": "ok", "state": state, "clients": len(ws_clients)}


# ── 打断查询（宿主机 kws_service 轮询） ──────────────
@app.get("/api/voice/interrupt")
async def voice_interrupt_check():
    """kws_service 轮询此接口，检查是否需要打断"""
    global _interrupt_flag
    should_interrupt = _interrupt_flag > 0
    _interrupt_flag = 0.0  # 读取后清除
    return {"interrupt": should_interrupt}


# ── 回复查询（宿主机 kws_service 轮询获取 TTS 文本） ──
@app.get("/api/voice/last-reply")
async def voice_last_reply(since: int = 0):
    """kws_service 轮询此接口，获取最新的 Agent 回复文本（用于 TTS）"""
    global _last_reply_id, _last_reply_text
    if _last_reply_id > since:
        return {
            "reply_id": _last_reply_id,
            "text": _last_reply_text,
        }
    return {"reply_id": _last_reply_id, "text": ""}


# ── 非流式 Chat API（兼容旧客户端） ──────────────────
@app.post("/api/chat")
async def chat_api(req: ChatRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    agent = get_agent()
    try:
        reply = agent.chat(text, stream=False)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 重置对话 ──────────────────────────────────────────
@app.post("/api/reset")
async def reset_api():
    agent = get_agent()
    agent.reset()
    return {"status": "reset"}


# ── WebSocket 流式 Chat ──────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    log.info(f"🔌 WebSocket 已连接 (共 {len(ws_clients)} 个客户端)")

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "无效的 JSON"})
                continue

            # ── 打断请求（浏览器 → KWS） ────────────
            if msg.get("type") == "interrupt":
                global _interrupt_flag
                _interrupt_flag = time.time()
                log.info("⏹️ 收到打断请求 (来自浏览器)")
                await ws.send_json({"type": "interrupt_ack"})
                continue

            text = msg.get("text", "").strip()
            if not text:
                await ws.send_json({"type": "error", "message": "text 不能为空"})
                continue

            agent = get_agent()
            agent.messages.append({"role": "user", "content": text})
            agent._trim_history()

            # 收集完整回复文本（供 KWS TTS 使用）
            full_reply_parts: list[str] = []

            try:
                async for event in agent.chat_stream_events_async():
                    if event.get("type") == "text":
                        full_reply_parts.append(event.get("content", ""))
                    await ws.send_json(event)
                    if event.get("type") == "complete":
                        break

                # 存储完整回复供 KWS 轮询
                global _last_reply_id, _last_reply_text
                _last_reply_id += 1
                _last_reply_text = "".join(full_reply_parts).strip()
                log.info(f"💾 回复 #{_last_reply_id}: \"{_last_reply_text[:40]}...\"")

            except Exception as e:
                log.error(f"Agent 处理错误: {e}")
                await ws.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        log.info("🔌 WebSocket 已断开")
    except Exception as e:
        log.error(f"WebSocket 错误: {e}")
    finally:
        ws_clients.discard(ws)


# ── RAG 传统关键词搜索代理 ──────────────────────────
@app.post("/api/rag/search")
async def rag_keyword_search(req: RAGSearchRequest):
    """关键词搜索代理 → RAG API /rag/keyword_search"""
    rag_url = get_rag_base_url().rstrip("/rag").rstrip("/")
    try:
        resp = requests.post(
            f"{rag_url}/rag/keyword_search",
            json={"keyword": req.text, "count": req.count},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail=f"无法连接 RAG 服务 ({rag_url})")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="RAG 服务响应超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── RAG 语义搜索代理 ─────────────────────────────────
@app.post("/api/rag/semantic")
async def rag_semantic_search(req: RAGSearchRequest):
    """语义搜索代理 → RAG API /rag/search"""
    rag_url = get_rag_base_url().rstrip("/rag").rstrip("/")
    try:
        resp = requests.post(
            f"{rag_url}/rag/search",
            json={"text": req.text, "count": req.count},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail=f"无法连接 RAG 服务 ({rag_url})")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="RAG 服务响应超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 导航占位（后续对接 ROS2） ───────────────────────
@app.post("/api/navigate")
async def navigate(req: NavigateRequest):
    """导航 API 占位 — 后续对接 ROS2 navigation stack"""
    log.info(f"📍 导航请求: category={req.category}, book={req.book_title}")
    return {
        "status": "accepted",
        "message": f"导航到分类 {req.category} 的请求已接收",
        "category": req.category,
        "book_title": req.book_title,
    }


# ── 入口 ──────────────────────────────────────────────
def main():
    import uvicorn

    host = os.getenv("AGENT_SERVER_HOST", AGENT_SERVER_HOST)
    port = int(os.getenv("AGENT_SERVER_PORT", AGENT_SERVER_PORT))

    log.info(f"🌐 监听地址: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
