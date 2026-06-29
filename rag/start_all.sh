#!/bin/bash
# ============================================
# LibraryMaster RAG — 一键启动脚本
# 1. 启动 SGLang 嵌入服务（宿主机）
# 2. 启动 Docker 容器（含 main.py）
# ============================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SGLANG_PORT=30000
SGLANG_URL="http://127.0.0.1:${SGLANG_PORT}/v1"

echo "========================================"
echo " LibraryMaster RAG 一键启动"
echo "========================================"

# ---- 检查目录 ----
if [ ! -f "${PROJECT_DIR}/docker-compose.yml" ]; then
    echo "[错误] 请在 rag 目录下运行此脚本"
    exit 1
fi

# ---- 1. 启动 SGLang 嵌入服务 ----
echo ""
echo "[1/3] 启动 SGLang 嵌入服务..."

# 检查是否已经在运行
if curl -s -o /dev/null -w "%{http_code}" "${SGLANG_URL}/models" 2>/dev/null | grep -q 200; then
    echo "  → SGLang 服务已在运行，跳过启动"
else
    # 后台启动，日志写到文件
    nohup python3 -m sglang.launch_server \
        --model-path ~/model/Qwen3_embedding-0.6b \
        --host 0.0.0.0 \
        --port ${SGLANG_PORT} \
        --is-embedding \
        > "${PROJECT_DIR}/sglang_server.log" 2>&1 &
    SGLANG_PID=$!
    echo "  → SGLang 已后台启动 (PID: ${SGLANG_PID})，日志: sglang_server.log"
fi

# 等待 SGLang 就绪
echo "  → 等待 SGLang 服务就绪..."
for i in $(seq 1 60); do
    if curl -s -o /dev/null -w "%{http_code}" "${SGLANG_URL}/models" 2>/dev/null | grep -q 200; then
        echo "  ✓ SGLang 服务就绪 ($(date +%H:%M:%S))"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[错误] SGLang 启动超时，请检查 sglang_server.log"
        exit 1
    fi
    sleep 3
done

# ---- 2. 构建并启动 Docker 容器 ----
echo ""
echo "[2/3] 构建 Docker 镜像..."

cd "${PROJECT_DIR}"
docker compose build

echo ""
echo "[3/3] 启动 Docker 容器..."
docker compose up -d

echo ""
echo "  → 等待容器就绪..."
sleep 3

# ---- 检查服务状态 ----
echo ""
echo "========================================"
echo " 服务状态"
echo "========================================"
docker compose ps

# 测试 API
echo ""
echo "--- 测试 API ---"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9014/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✓ RAG API 启动成功! (HTTP ${HTTP_CODE})"
else
    echo "  ⚠ RAG API 返回 HTTP ${HTTP_CODE}，请稍后检查日志: docker compose logs"
fi

echo ""
echo "========================================"
echo " ✅ 全部启动完成！"
echo "========================================"
echo "  SGLang 嵌入服务:  http://localhost:${SGLANG_PORT}/v1"
echo "  RAG API:          http://localhost:9014/"
echo "  API 文档:         http://localhost:9014/docs"
echo ""
echo "  查看日志:"
echo "    SGLang:  tail -f ${PROJECT_DIR}/sglang_server.log"
echo "    容器:    docker compose logs -f"
echo ""
echo "  停止服务:"
echo "    docker compose down"
echo "    kill <sglang_pid>   # 或 pkill -f sglang.launch_server"
echo "========================================"
