#!/bin/bash
#
# start_voice_agent.sh — Voice Agent 启动脚本
#
# 使用方式:
#   ./start_voice_agent.sh                  # 构建并启动 Docker 服务
#   ./start_voice_agent.sh --kiosk          # 启动 Docker + HDMI 全屏 Kiosk
#   ./start_voice_agent.sh --kws            # 启动 Docker + 宿主机语音唤醒
#   ./start_voice_agent.sh --build          # 强制重新构建镜像后启动
#   ./start_voice_agent.sh --no-env         # 跳过 .env 检查
#   ./start_voice_agent.sh stop             # 停止服务
#   ./start_voice_agent.sh restart          # 重启服务
#   ./start_voice_agent.sh logs             # 查看日志
#   ./start_voice_agent.sh status           # 查看状态
#

set -e

# ── 颜色 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── 路径 ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Python 虚拟环境 ──────────────────────────────────
VENV_DIR="$SCRIPT_DIR/../.venv"
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}[OK]${NC} Python 虚拟环境已激活"
else
    echo -e "${YELLOW}[WARN]${NC} 未找到虚拟环境: $VENV_DIR"
fi

DOCKER_COMPOSE="docker-compose"
if ! command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker compose"
fi

# ── 后台进程追踪 (用于 Ctrl+C 清理) ──────────────────
_BG_PIDS=()
_cleanup() {
    local exit_code=$?
    echo ""
    info "清理后台进程..."
    # 杀语音服务
    pkill -f "voice_relay.py" 2>/dev/null || true
    pkill -f "kws_service.py" 2>/dev/null || true
    # 杀追踪的 PID
    for pid in "${_BG_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    _BG_PIDS=()
    # 停 Docker (非 stop/logs/status 模式才停)
    case "${1:-}" in
        stop|--kiosk|--kws|--all|--build|--no-env|"")
            info "停止 Docker 容器..."
            $DOCKER_COMPOSE down 2>/dev/null || true
            ;;
    esac
    ok "清理完成"
    exit $exit_code
}

# ── 辅助函数 ──────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()      { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()     { echo -e "${RED}[ERR]${NC} $1"; }

usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  (无参数)       构建并启动 Docker 服务"
    echo "  --kiosk        启动 Docker + HDMI 全屏 Kiosk 浏览器"
    echo "  --kws          启动 Docker + 语音唤醒服务 (KWS)"
    echo "  --all          启动所有服务 (Docker + Kiosk + 语音)"
    echo "  --build        强制重新构建镜像后启动"
    echo "  --no-env       跳过 .env 检查"
    echo "  stop           停止所有服务"
    echo "  restart        重启服务"
    echo "  logs           查看日志"
    echo "  status         查看状态"
    echo "  -h, --help     显示帮助"
    exit 0
}

# ── 前置检查 ──────────────────────────────────────────
check_prerequisites() {
    info "检查环境..."

    # 检查 Docker
    if ! command -v docker &>/dev/null; then
        err "Docker 未安装！请先安装 Docker。"
        exit 1
    fi
    ok "Docker 已安装"

    # 检查 Docker Compose
    if ! docker compose version &>/dev/null && ! docker-compose --version &>/dev/null; then
        err "Docker Compose 未安装！"
        exit 1
    fi
    ok "Docker Compose 可用 ($($DOCKER_COMPOSE version --short 2>/dev/null || echo 'unknown'))"
}

# ── .env 检查 ─────────────────────────────────────────
check_env() {
    if [ ! -f ".env" ]; then
        warn ".env 文件不存在！"
        if [ -f ".env.example" ]; then
            echo "正在从 .env.example 创建 .env ..."
            cp .env.example .env
            warn "请编辑 .env 文件，填入 DEEPSEEK_API_KEY 等配置后重新运行。"
            info "快速编辑: nano .env 或 vim .env"
            exit 1
        else
            err ".env.example 也不存在！请先创建配置文件。"
            exit 1
        fi
    fi

    # 检查必填项
    source .env 2>/dev/null || true
    if [ -z "$DEEPSEEK_API_KEY" ] || [ "$DEEPSEEK_API_KEY" = "sk-xxxxxxxx" ]; then
        warn "DEEPSEEK_API_KEY 未设置或仍为默认值。请在 .env 文件中配置。"
        warn "LLM 对话功能将不可用。"
    else
        ok "DEEPSEEK_API_KEY 已配置"
    fi

    if [ -z "$RAG_BASE_URL" ]; then
        warn "RAG_BASE_URL 未设置，默认使用 http://host.docker.internal:9014/rag"
    else
        ok "RAG_BASE_URL = $RAG_BASE_URL"
    fi

    ok ".env 检查通过"
}

# ── RAG 连通性检查（可选） ────────────────────────────
check_rag() {
    local rag_url="${RAG_BASE_URL:-http://host.docker.internal:9014/rag}"
    local base_url="${rag_url%/rag*}"
    info "检查 RAG API 连通性 ($base_url) ..."

    if curl -s -o /dev/null -w "%{http_code}" "$base_url/" 2>/dev/null | grep -q "200"; then
        ok "RAG API 响应正常"
    else
        warn "RAG API 不可达 ($base_url)。图书搜索功能不可用。"
        warn "请确保 RAG 服务已启动，或检查 RAG_BASE_URL 配置。"
    fi
}

# ── Docker 构建与启动 ─────────────────────────────────
start_docker() {
    info "启动 Docker 服务..."

    if [ "$1" = "--build" ]; then
        info "强制重新构建镜像..."
        $DOCKER_COMPOSE build --no-cache
    elif ! $DOCKER_COMPOSE images | grep -q "voice-agent"; then
        info "首次运行，构建镜像..."
        $DOCKER_COMPOSE build
    fi

    info "启动容器..."
    $DOCKER_COMPOSE up -d

    # 等待服务就绪
    local max_retries=15
    local retry=0
    info "等待服务就绪..."

    while [ $retry -lt $max_retries ]; do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:9015/api/health 2>/dev/null | grep -q "200"; then
            ok "Agent Server 就绪! (http://localhost:9015)"
            break
        fi
        sleep 2
        retry=$((retry + 1))
        echo -n "."
    done

    if [ $retry -ge $max_retries ]; then
        warn "服务启动超时，请检查日志: $0 logs"
    fi
}

# ── 启动 Weston（HDMI 显示） ─────────────────────────
start_weston() {
    local weston_socket="${XDG_RUNTIME_DIR:-/tmp/run}/wayland-0"

    # 如果 Weston 已在运行且进程存活，跳过
    if sudo ls -la "$weston_socket" > /dev/null 2>&1 && \
       ps aux | grep -v grep | grep -q "weston.*drm-backend"; then
        ok "Weston 已在运行"
        return 0
    fi

    # 清理残留 socket 文件（Weston 已死但 socket 文件还在）
    if sudo ls -la "$weston_socket" > /dev/null 2>&1; then
        warn "发现残留 socket 文件，清理..."
        sudo rm -f "$weston_socket"
    fi

    info "初始化 HDMI 显示..."
    # 杀掉可能占用 DRM 的旧进程
    sudo pkill -f "modetest" 2>/dev/null || true
    sleep 1

    # 强制标记 HDMI 已连接
    if [ -e /sys/class/drm/card0-HDMI-A-1/status ]; then
        sudo sh -c 'echo "connected" > /sys/class/drm/card0-HDMI-A-1/status' 2>/dev/null || true
        sleep 1
    fi

    # 预分配 CRTC 31 (dc8000 显示控制器) — 关键！
    # Weston 默认会选 CRTC 63 (bt1120 摄像头通道) 导致 HDMI 无信号
    info "分配 CRTC 31 (dc8000 显示控制器)..."
    sudo timeout 3 modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1
    sleep 1

    # 启动 Weston（使用 GL 渲染器 → llvmpipe LLVM JIT 软件 OpenGL）
    # 注意: 不带 --use-pixman，让 Weston 使用 gl-renderer (llvmpipe)
    # llvmpipe 比 pixman 快很多（LLVM JIT 编译优化）
    info "启动 Weston (Wayland 合成器, llvmpipe GL 渲染)..."
    sudo mkdir -p /tmp/run
    sudo chmod 700 /tmp/run
    if [ -f "${SCRIPT_DIR}/weston.ini" ]; then
        sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so \
            --config="${SCRIPT_DIR}/weston.ini" &
    else
        sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &
    fi
    WESTON_PID=$!

    # 等待 Wayland socket 出现（最多 12 秒）
    # 注意：必须确保 Weston 完全初始化（GL/EGL 栈就绪）后再返回
    local max_wait=12
    local waited=0
    while [ $waited -lt $max_wait ]; do
        sudo ls -la "/tmp/run/wayland-0" > /dev/null 2>&1
        local socket_ok=$?
        # 同时检查 Weston 进程是否存活
        ps aux | grep -v grep | grep -q "weston.*drm-backend"
        local weston_alive=$?
        if [ $socket_ok -eq 0 ] && [ $weston_alive -eq 0 ]; then
            ok "Weston 就绪 (PID $(pgrep -f 'weston.*drm-backend' | head -1))"
            export XDG_RUNTIME_DIR=/tmp/run
            # 再等 1 秒确保显示输出完全建立
            sleep 1
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
        echo -n "."
    done

    # 超时检查
    warn "Weston 启动超时。尝试检查："
    warn "  - HDMI 线是否接好？"
    warn "  - 显示器是否通电？"
    warn "  - 运行 sudo modetest -M vs-drm 查看可用 CRTC"
    return 1
}

# ── 语音中继（浏览器 🎤 按钮录音代理） ──────────
start_voice_relay() {
    echo ""
    info "启动语音中继 (voice_relay.py, 端口 9016)..."

    if ! python3 -c "import sounddevice" 2>/dev/null; then
        warn "voice_relay 需要 sounddevice 库"
        warn "请安装: pip install sounddevice numpy"
        return 1
    fi

    # 检查是否已在运行
    if pgrep -f "voice_relay.py" > /dev/null 2>&1; then
        ok "voice_relay 已在运行"
        return 0
    fi

    python3 "$SCRIPT_DIR/src/voice_relay.py" &
    local pid=$!
    _BG_PIDS+=("$pid")
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        ok "voice_relay 已启动 (PID $pid)"
    else
        warn "voice_relay 启动失败"
        return 1
    fi
}

# ── KWS 语音唤醒服务 ─────────────────────────────
start_kws_service() {
    echo ""
    info "启动 KWS 唤醒服务 (kws_service.py)..."

    if ! python3 -c "import funasr" 2>/dev/null; then
        warn "kws_service 需要 funasr 库"
        warn "请安装: pip install funasr sounddevice numpy requests"
        return 1
    fi

    # 检查是否已在运行
    if pgrep -f "kws_service.py" > /dev/null 2>&1; then
        ok "kws_service 已在运行"
        return 0
    fi

    python3 "$SCRIPT_DIR/src/kws_service.py" &
    local pid=$!
    _BG_PIDS+=("$pid")
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        ok "kws_service 已启动 (PID $pid)"
    else
        warn "kws_service 启动失败"
        return 1
    fi
}

# ── 启动 KWS 语音唤醒（宿主机） ──────────────────────
start_kws() {
    start_voice_relay || return 1
    start_kws_service || return 1

    echo ""
    info "🎤 语音服务已就绪"
    info "  - voice_relay :9016 (浏览器 🎤 按钮录音)"
    info "  - kws_service 唤醒词: 你好小图 (说出后自动录音 → Agent)"
    info "按 Ctrl+C 停止所有语音服务"
}

# ── 显示状态 ──────────────────────────────────────────
show_status() {
    echo ""
    info "═══════════ 服务状态 ═══════════"
    echo ""

    # Weston 状态
    local ws="/tmp/run/wayland-0"
    if [ -e "$ws" ]; then
        ok "Weston         ✅  (HDMI 已就绪)"
    else
        warn "Weston         ❌  (未启动)"
    fi

    # Docker 状态
    if $DOCKER_COMPOSE ps 2>/dev/null | grep -q "Up"; then
        ok "voice-agent    ✅  容器运行中"
        $DOCKER_COMPOSE ps 2>/dev/null | tail -n +2

        local port=$(grep AGENT_SERVER_PORT .env 2>/dev/null | cut -d= -f2 || echo "9015")
        port=${port:-9015}
        echo ""
        echo "  Web UI:     ${GREEN}http://localhost:${port}${NC}"
        echo "  API:        ${GREEN}http://localhost:${port}/api/health${NC}"
        echo "  WebSocket:  ws://localhost:${port}/ws/chat"
        echo ""
    else
        warn "voice-agent    ❌  容器未运行"
        $DOCKER_COMPOSE ps 2>/dev/null || true
        echo ""
        info "启动命令: $0"
    fi

    # 语音服务状态
    if pgrep -f "voice_relay.py" > /dev/null 2>&1; then
        ok "voice_relay   ✅  运行中 (:9016)"
    else
        warn "voice_relay   ❌  (浏览器 🎤 按钮不可用)"
    fi
    if pgrep -f "kws_service.py" > /dev/null 2>&1; then
        ok "kws_service   ✅  运行中 (唤醒词: 你好小图)"
    else
        warn "kws_service   ❌  (语音唤醒不可用)"
    fi
    echo "═══════════════════════════════════"
    echo ""
}

# ── 主逻辑 ────────────────────────────────────────────
main() {
    ARG="${1:-}"

    case "$ARG" in
        stop)
            info "停止服务..."
            _cleanup "stop"
            ;;
        restart)
            info "重启服务..."
            $DOCKER_COMPOSE down
            $DOCKER_COMPOSE up -d
            ok "服务已重启"
            exit 0
            ;;
        logs)
            $DOCKER_COMPOSE logs -f
            exit 0
            ;;
        status)
            show_status
            exit 0
            ;;
        -h|--help)
            usage
            ;;
    esac

    # ── Ctrl+C 清理陷阱 ────────────────────────────
    # 拦截 Ctrl+C / kill, 杀掉后台语音进程 + 停 Docker
    trap '_cleanup "$ARG"' INT TERM

    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   📚 图书馆智能助手 - 启动脚本      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
    echo ""

    # 1. 前置检查
    check_prerequisites

    # 2. .env 检查
    if [ "$ARG" != "--no-env" ]; then
        check_env
    fi

    # 3. 可选: RAG 连通性检查
    check_rag

    # 4. 启动 Docker
    if [ "$ARG" = "--build" ]; then
        start_docker --build
    else
        start_docker
    fi

    # 5. 显示状态
    show_status

    # 6. 使用提示
    echo "───────────────────────────────────────────"
    echo "  📖  Web UI:      http://localhost:9015"
    echo "  📋  API 健康:    http://localhost:9015/api/health"
    echo "  🛑  停止服务:    $0 stop"
    echo "  📜  查看日志:    $0 logs"
    echo "  🔄  重启服务:    $0 restart"
    echo "───────────────────────────────────────────"
    echo ""

    # 7. 可选: KWS / Kiosk / All
    case "$ARG" in
        --kws)
            start_kws
            info "语音服务运行中，Ctrl+C 停止"
            wait
            ;;
        --kiosk)
            info "启动 Kiosk 浏览器..."
            if [ ! -f "$SCRIPT_DIR/kiosk.py" ]; then
                warn "kiosk.py 不存在！"
                exit 1
            fi
            # 使用系统 Python 检查 GI 依赖（避免 venv 屏蔽系统包）
            local _py_cmd="python3"
            if /usr/bin/python3 -c "import gi" 2>/dev/null; then
                _py_cmd="/usr/bin/python3"
            fi
            if ! $_py_cmd -c "import gi; gi.require_version('WebKit2','4.0'); from gi.repository import WebKit2" 2>/dev/null; then
                warn "Kiosk 依赖未安装，请先在 RDK X5 上运行:"
                warn "  sudo apt install -y python3-gi gir1.2-webkit2-4.0 gir1.2-gtk-3.0"
                exit 1
            fi
            # 自动启动 Weston（如果未运行）
            start_weston || exit 1
            echo ""
            info "Kiosk 浏览器将显示在 HDMI 屏幕上"
            info "按 Ctrl+C 退出"
            echo ""
            sudo XDG_RUNTIME_DIR=/tmp/run GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0 \
                $_py_cmd "$SCRIPT_DIR/kiosk.py"
            ;;
        --all)
            start_kws
            info "启动 Kiosk 浏览器..."
            if [ ! -f "$SCRIPT_DIR/kiosk.py" ]; then
                warn "kiosk.py 不存在！"
                exit 1
            fi
            local _py_cmd="python3"
            if /usr/bin/python3 -c "import gi" 2>/dev/null; then
                _py_cmd="/usr/bin/python3"
            fi
            if ! $_py_cmd -c "import gi; gi.require_version('WebKit2','4.0'); from gi.repository import WebKit2" 2>/dev/null; then
                warn "Kiosk 依赖未安装，请先在 RDK X5 上运行:"
                warn "  sudo apt install -y python3-gi gir1.2-webkit2-4.0 gir1.2-gtk-3.0"
                exit 1
            fi
            start_weston || exit 1
            echo ""
            info "全栈启动完成！Kiosk + 语音唤醒运行中"
            echo ""
            sudo XDG_RUNTIME_DIR=/tmp/run GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0 \
                $_py_cmd "$SCRIPT_DIR/kiosk.py"
            ;;
        *)
            info "提示: 添加 --kws 参数启动语音唤醒"
            info "      添加 --kiosk 参数启动 HDMI 全屏显示"
            info "      添加 --all 参数启动全部服务"
            ;;
    esac
}

main "$@"
