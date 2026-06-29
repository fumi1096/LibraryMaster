#!/bin/bash
#
# deploy-kiosk.sh — RDK X5 Kiosk 部署脚本
#
# 在 RDK X5 上运行，安装依赖并配置开机自启。
# 确保 voice-agent Docker 容器和 Weston 已配置好。
#
# 用法:
#   ./deploy/deploy-kiosk.sh              # 安装依赖并部署
#   ./deploy/deploy-kiosk.sh --uninstall  # 卸载
#   ./deploy/deploy-kiosk.sh --test       # 仅测试（不安装服务）
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        err "请使用 sudo 运行: sudo $0"
        exit 1
    fi
}

install_deps() {
    info "安装 Kiosk 依赖..."
    apt-get update -qq
    apt-get install -y -qq \
        python3-gi \
        gir1.2-webkit2-4.0 \
        gir1.2-gtk-3.0 \
        2>&1 | tail -3
    ok "依赖安装完成"
}

install_weston_service() {
    if [ -f /etc/systemd/system/weston.service ]; then
        ok "weston.service 已存在"
    else
        info "安装 weston.service（来自 HDMI 配置指南）..."
        cat > /etc/systemd/system/weston.service << 'EOF'
[Unit]
Description=Weston Wayland compositor
After=init-hdmi.service
Requires=init-hdmi.service

[Service]
Type=simple
Environment=XDG_RUNTIME_DIR=/tmp/run
ExecStartPre=/bin/mkdir -p /tmp/run
ExecStartPre=/bin/chmod 700 /tmp/run
ExecStart=/usr/bin/weston --tty=1 --backend=drm-backend.so
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        ok "weston.service 已安装"
    fi
    systemctl enable weston.service 2>/dev/null && ok "weston.service 已启用 (开机自启)"
}

install_init_hdmi_service() {
    if [ -f /etc/systemd/system/init-hdmi.service ]; then
        ok "init-hdmi.service 已存在"
        return
    fi

    info "安装 init-hdmi.service（HDMI 初始化）..."
    # 创建 init-hdmi.sh
    cat > /usr/local/bin/init-hdmi.sh << 'EOF'
#!/bin/bash
for i in $(seq 1 30); do
    if [ -e /sys/class/drm/card0-HDMI-A-1/status ]; then
        break
    fi
    sleep 1
done
echo "connected" > /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null
sleep 1
# 预分配 CRTC 31 (dc8000 显示控制器)，不要后台运行避免占用 DRM
timeout 3 modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1
echo "HDMI initialized"
EOF
    chmod +x /usr/local/bin/init-hdmi.sh

    cat > /etc/systemd/system/init-hdmi.service << 'EOF'
[Unit]
Description=Initialize HDMI display
After=multi-user.target
Wants=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/init-hdmi.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable init-hdmi.service
    ok "init-hdmi.service 已安装并启用"
}

install_kiosk_service() {
    info "安装 kiosk 脚本到 /usr/local/bin ..."
    cp "$SCRIPT_DIR/kiosk.py" /usr/local/bin/voice-agent-kiosk
    chmod +x /usr/local/bin/voice-agent-kiosk
    ok "kiosk 脚本已安装"

    info "安装 systemd 服务..."
    cp "$SCRIPT_DIR/kiosk.service" /etc/systemd/system/voice-agent-kiosk.service
    systemctl daemon-reload
    systemctl enable voice-agent-kiosk.service
    ok "voice-agent-kiosk.service 已启用 (开机自启)"

    echo ""
    info "══════════ 所有服务状态 ══════════"
    for svc in init-hdmi weston docker voice-agent-kiosk; do
        local s="${svc}.service"
        local active=$(systemctl is-enabled "$s" 2>/dev/null || echo "disabled")
        local running=$(systemctl is-active "$s" 2>/dev/null || echo "inactive")
        if [ "$running" = "active" ]; then
            printf "  %-20s ✅  enabled, running\n" "$svc"
        elif [ "$active" = "enabled" ]; then
            printf "  %-20s ⏸️  enabled, not running\n" "$svc"
        else
            printf "  %-20s ❌  disabled\n" "$svc"
        fi
    done
    echo "═══════════════════════════════════"
    echo ""

    info "重启后自动启动顺序:"
    echo "  1. init-hdmi.service    (强制 HDMI 连接)"
    echo "  2. weston.service       (Wayland 合成器)"
    echo "  3. docker.service       (Docker 守护进程)"
    echo "  4. voice-agent-kiosk    (全屏 Web UI)"
    echo ""
    info "立即启动: sudo systemctl start voice-agent-kiosk"
}

uninstall() {
    warn "卸载 Kiosk 服务..."
    systemctl stop voice-agent-kiosk.service 2>/dev/null || true
    systemctl disable voice-agent-kiosk.service 2>/dev/null || true
    rm -f /etc/systemd/system/voice-agent-kiosk.service
    rm -f /usr/local/bin/voice-agent-kiosk
    systemctl daemon-reload
    ok "已卸载"
}

test_kiosk() {
    echo ""
    info "══════════ 测试 Kiosk ══════════"
    echo ""
    echo "验证环境:"

    # 检查 Weston
    if [ -e "$XDG_RUNTIME_DIR/wayland-0" ] || [ -e "/tmp/run/wayland-0" ]; then
        ok "Weston Wayland socket 存在"
    else
        warn "Weston 未运行。先启动:"
        echo "  sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &"
        echo ""
    fi

    # 检查 Docker
    if docker ps 2>/dev/null | grep -q "voice-agent"; then
        ok "voice-agent 容器运行中 (http://localhost:9015)"
    else
        warn "voice-agent 未运行。先启动:"
        echo "  cd $SCRIPT_DIR && docker compose up -d"
        echo ""
    fi

    # 检查依赖
    python3 -c "import gi; gi.require_version('WebKit2','4.0'); from gi.repository import WebKit2" 2>/dev/null \
        && ok "Python WebKit2 可用" \
        || warn "Python WebKit2 不可用 (需要安装依赖)"

    echo ""
    info "测试命令:"
    echo "  sudo XDG_RUNTIME_DIR=/tmp/run $SCRIPT_DIR/kiosk.py"
    echo ""
}

case "${1:-}" in
    --uninstall) check_root; uninstall ;;
    --test)      test_kiosk ;;
    *)
        check_root
        echo ""
        echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║   RDK X5 Kiosk 部署脚本             ║${NC}"
        echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
        echo ""
        test_kiosk
        install_deps
        install_init_hdmi_service
        install_weston_service
        install_kiosk_service
        echo ""
        ok "部署完成！重启 RDK X5 即可看到 Web UI 全屏显示。"
        echo "  或立即启动: sudo systemctl start voice-agent-kiosk"
        echo ""
        ;;
esac
